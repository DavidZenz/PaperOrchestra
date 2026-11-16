"""Code-based rendering adapters; the authors' figure controller stays intact.

Only the visualizer task/output language changes. Planning, styling, critique,
captioning, concurrency and critic stopping execute the pinned upstream code.
"""
from __future__ import annotations

import base64
from contextvars import ContextVar
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from google.genai import types
from orchestra_runtime import digest, get_runtime, role_override, figure_context


def extract_code(response, language):
    labels = "r|R" if language == "r" else "latex|tex"
    match = re.search(r"```(?:" + labels + r")\s*\n(.*?)```", response, re.DOTALL)
    return match.group(1).strip() if match else response.strip()


def dimensions(aspect_ratio):
    width, height = [float(x) for x in aspect_ratio.split(":")]
    if width <= 0 or height <= 0:
        raise ValueError("Aspect ratio must be positive")
    scale = 6.4 / max(width, height)
    return width * scale, height * scale


def render_saved(directory, *, rscript="Rscript", timeout=60):
    """Render saved sources without any model call. Used by live and replay modes."""
    directory = Path(directory).resolve()
    meta = json.loads((directory / "render.json").read_text())
    for name, expected in meta.get("files_sha256", {meta["source"]:meta["source_sha256"]}).items():
        if digest(directory / name) != expected:
            raise ValueError(f"Saved renderer input hash mismatch: {name}")
    if meta["backend"] == "tikz":
        source = (directory / meta["source"]).read_text()
        uncommented = re.sub(r"(?<!\\)%[^\n]*", "", source)
        if not re.search(r"\\documentclass\s*(?:\[[^]]*\])?\s*\{standalone\}", uncommented):
            raise ValueError("TikZ source must use the standalone document class")
        if not re.search(r"\\begin\s*\{tikzpicture\}|\\tikz\b", uncommented):
            raise ValueError("TikZ source must contain an editable TikZ picture")
    env = dict(os.environ)
    # Fixed seeds are also set by worker.R. PDF metadata can still vary by engine.
    env.setdefault("SOURCE_DATE_EPOCH", "946684800")
    env.setdefault("FORCE_SOURCE_DATE", "1")
    if meta["backend"] == "ggplot2":
        command = [rscript, "--vanilla", "worker.R"]
    elif meta["backend"] == "tikz":
        command = ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "source.tex"]
    else:
        raise ValueError(f"Unsupported saved renderer {meta['backend']}")
    # Stale outputs can never masquerade as a successful replay.
    for name in ["figure.pdf", "preview.jpg", "source.pdf"]:
        (directory / name).unlink(missing_ok=True)
    with (directory / "render.log").open("w") as log:
        completed = subprocess.run(command, cwd=directory, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, timeout=timeout)
    if completed.returncode:
        raise RuntimeError(f"{meta['backend']} rendering failed; see {directory / 'render.log'}")
    if meta["backend"] == "tikz":
        pdf = directory / "source.pdf"
        if not pdf.is_file():
            raise RuntimeError("TikZ compiler produced no PDF")
        pdf.replace(directory / "figure.pdf")
    from PIL import Image
    if not (directory / "figure.pdf").is_file():
        raise RuntimeError("Renderer produced no vector PDF")
    # Render the one native PDF for both backends. Rebuilding an R plot for a
    # second export could resample stochastic geoms despite a fixed initial seed.
    import pymupdf
    with pymupdf.open(directory / "figure.pdf") as document:
        if len(document) != 1:
            raise ValueError("A figure must produce exactly one page")
        pix = document[0].get_pixmap(matrix=pymupdf.Matrix(300/72,300/72),alpha=False)
        pix.set_dpi(300,300)
        pix.save(directory / "preview.jpg")
    with Image.open(directory / "preview.jpg") as im:
        im.verify()
    return command


def write_sources(directory, code, backend, aspect_ratio):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / ("source.R" if backend == "ggplot2" else "source.tex")
    source.write_text(code)
    width, height = dimensions(aspect_ratio)
    if backend == "ggplot2":
        # The model defines p; the deterministic wrapper controls export and seed.
        (directory / "worker.R").write_text(
            'options(warn=1)\nset.seed(0)\nlibrary(ggplot2)\nsource("source.R", local=TRUE)\n'
            'if (!exists("p") || !inherits(p, "ggplot")) stop("source.R must define ggplot object p")\n'
            f'ggsave("figure.pdf", plot=p, width={width!r}, height={height!r}, units="in", bg="white")\n'
            'writeLines(capture.output(sessionInfo()), "sessionInfo.txt")\n')
    meta = {"backend":backend, "aspect_ratio":aspect_ratio, "source":source.name,
            "source_sha256":digest(source), "figure_id":figure_context.get(),
            "seed":0 if backend == "ggplot2" else None, "status":"source_saved"}
    meta["files_sha256"] = {source.name:digest(source)}
    if backend == "ggplot2":
        meta["files_sha256"]["worker.R"] = digest(directory / "worker.R")
    (directory / "render.json").write_text(json.dumps(meta, indent=2))
    return meta


def generate_figure_visuals(task_name, figure_description, model_name="gemini-3.1-pro-preview",
                            image_model_name="gemini-3-pro-image-preview", aspect_ratio="16:9"):
    runtime = get_runtime()
    backend = runtime.plot_backend if task_name == "plot" else runtime.diagram_backend
    if backend in {"matplotlib", "image"}:
        return _original_visualizer(task_name, figure_description, model_name, image_model_name, aspect_ratio)
    from utils.gemini_utils import call_gemini_with_contents
    from utils.paper_banana_utils import PLOT_VISUALIZER_AGENT_SYSTEM_PROMPT, DIAGRAM_VISUALIZER_AGENT_SYSTEM_PROMPT, identity_parse
    if backend == "ggplot2":
        task = ("Use R with ggplot2 to generate a statistical plot based on the following detailed description: "
                + figure_description + "\nReturn R code only. Define the final ggplot object as p. "
                "Do not save files: the rendering wrapper exports p to PDF and JPEG. "
                "Use only base R and ggplot2, with built-in serif, sans or mono font families. "
                "Use the supplied numeric data exactly; do not simulate or invent observations. "
                "Do not install packages or download data. The runtime sets set.seed(0). "
                f"Requested canvas aspect ratio: {aspect_ratio}. Code:")
        system = PLOT_VISUALIZER_AGENT_SYSTEM_PROMPT
    elif backend == "tikz":
        task = ("Write a complete standalone LaTeX/TikZ document rendering the following detailed description: "
                + figure_description + "\nReturn LaTeX code only. Use \\documentclass[tikz,border=5pt]{standalone}, "
                "\\usepackage{amsmath} and any required standard TikZ libraries. "
                "The renderer is pdfLaTeX. Use its built-in TeX fonts; do not load fontspec, "
                "select system fonts, or require XeLaTeX/LuaLaTeX. Match the requested font style "
                "with a standard TeX serif, sans or mono family. "
                "Produce one diagram on one page, with no figure title or caption in the drawing. "
                "Use editable TikZ nodes, paths and math; do not embed external images, invoke shell commands, "
                "or download assets. Preserve the described scientific content and labels. "
                f"Requested canvas aspect ratio: {aspect_ratio}. Code:")
        system = DIAGRAM_VISUALIZER_AGENT_SYSTEM_PROMPT
    else:
        raise ValueError(f"Unsupported backend {backend}")
    role_token = role_override.set(f"{backend}-visualizer")
    try:
        response = call_gemini_with_contents(
            contents=[types.Part.from_text(text=system), types.Part.from_text(text=task)],
            model_name=model_name, result_parsing_func=identity_parse)
    finally:
        role_override.reset(role_token)
    directory = runtime.root.parent / "figure_sources" / uuid.uuid4().hex
    code = extract_code(response["parsed_response"], "r" if backend == "ggplot2" else "latex")
    meta = write_sources(directory, code, backend, aspect_ratio)
    runtime.event("render_start", backend=backend, figure_id=figure_context.get(),
                  directory=str(directory), source_sha256=meta["source_sha256"])
    try:
        command = render_saved(directory, rscript=runtime.rscript, timeout=runtime.render_timeout)
        meta.update(status="rendered", command=command, pdf_sha256=digest(directory / "figure.pdf"),
                    preview_sha256=digest(directory / "preview.jpg"))
        (directory / "render.json").write_text(json.dumps(meta, indent=2))
        runtime.event("render_end", backend=backend, figure_id=figure_context.get(),
                      directory=str(directory), source=meta["source"], source_sha256=meta["source_sha256"],
                      pdf_sha256=meta["pdf_sha256"], preview_sha256=meta["preview_sha256"])
        return base64.b64encode((directory / "preview.jpg").read_bytes()).decode()
    except Exception as exc:
        meta.update(status="failed", error=str(exc))
        (directory / "render.json").write_text(json.dumps(meta, indent=2))
        runtime.event("render_error", backend=backend, figure_id=figure_context.get(),
                      directory=str(directory), error=str(exc))
        # Exactly the upstream rendering-failure signal: the critic may repair it.
        return None


_original_visualizer = None


def install():
    """Inject only renderer hooks; original controller files remain byte-identical."""
    global _original_visualizer
    import utils.paper_banana_utils as banana
    import methods.agents.plotting_agent as plotting
    if _original_visualizer is None:
        _original_visualizer = banana.generate_figure_visuals
    banana.generate_figure_visuals = generate_figure_visuals
    plotting.generate_figure_visuals = generate_figure_visuals
    original = plotting.process_single_figure
    if getattr(original, "_orchestra_visuals", False):
        return
    @functools.wraps(original)
    def observed(plan, *args, **kwargs):
        token = figure_context.set(plan.get("figure_id", "unknown"))
        runtime = get_runtime()
        runtime.event("figure_start", figure_id=figure_context.get(), plan=plan)
        try:
            result = original(plan, *args, **kwargs)
            data = result.get("base64_img")
            preview_sha = hashlib.sha256(base64.b64decode(data)).hexdigest() if data else None
            runtime.event("figure_end", figure_id=figure_context.get(), task_name=result.get("task_name"),
                          preview_sha256=preview_sha, caption=result.get("caption"))
            return result
        except Exception as exc:
            runtime.event("figure_error", figure_id=figure_context.get(), error=str(exc))
            raise
        finally:
            figure_context.reset(token)
    observed._orchestra_visuals = True
    plotting.process_single_figure = observed
