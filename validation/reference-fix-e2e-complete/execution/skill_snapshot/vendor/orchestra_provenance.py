"""Selected figure provenance and deterministic manuscript source references.

User-authorized output adaptation. Original controllers and their decision rules
remain unchanged; effective manuscript artifacts are assembled before consumption.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import shutil

BEGIN = "% PAPER_ORCHESTRA_PROVENANCE_BEGIN"
END = "% PAPER_ORCHESTRA_PROVENANCE_END"
SCHEMA = 1


class ProvenanceError(RuntimeError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inside(base, name):
    base = Path(base).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise ProvenanceError(f"Figure source path escapes its artifact directory: {name}")
    return path


def verify_files(base, manifest, *, originals=False, original_base=None):
    if manifest.get("schema_version") != SCHEMA:
        raise ProvenanceError("Unsupported figure provenance schema")
    for item in manifest["figures"]:
        for name, expected in item["files"].items():
            path = _inside(base, name)
            if not path.is_file() or sha(path) != expected:
                raise ProvenanceError(f"Selected figure provenance mismatch: {name}")
            if originals:
                original = _inside(original_base or base, item["original_directory"]) / path.name
                if not original.is_file() or sha(original) != expected:
                    raise ProvenanceError(f"Published source differs from actual renderer artifact: {name}")


def build_manifest(base, destination=None):
    """Resolve the selected preview, including upstream last-valid-image retention."""
    base = Path(base).resolve()
    destination = Path(destination).resolve() if destination is not None else base
    destination.mkdir(parents=True, exist_ok=True)
    run = json.loads((base / "run.json").read_text()) if (base / "run.json").is_file() else {}
    events = [json.loads(line) for line in (base / "execution/trace.jsonl").read_text().split("\n") if line.strip()]
    results = json.loads((base / "plotting_results.json").read_text())
    items, aliases = [], set()
    for result in results:
        if not result.get("image_path"):
            continue
        figure_id = result["figure_id"]
        alias = figure_id.replace(" ", "_").lower()
        if not re.fullmatch(r"[\w-]+", alias) or alias in aliases:
            raise ProvenanceError(f"Unsafe or duplicated figure ID: {figure_id}")
        aliases.add(alias)
        image = _inside(base, result["image_path"])
        preview_hash = sha(image)
        matching = [e for e in events if e["event"] == "render_end"
                    and e.get("figure_id") == figure_id and e.get("preview_sha256") == preview_hash]
        if not matching:
            raise ProvenanceError(f"Selected figure lacks a successful source-backed render: {figure_id}")
        render = matching[-1]
        original_dir = Path("figure_sources") / Path(render["directory"]).name
        original = _inside(base, original_dir)
        metadata = json.loads((original / "render.json").read_text())
        expected_source = {"ggplot2":"source.R", "tikz":"source.tex"}.get(metadata.get("backend"))
        if (not expected_source or metadata.get("source") != expected_source
                or metadata.get("status") != "rendered" or metadata.get("figure_id") != figure_id
                or metadata.get("source_sha256") != render["source_sha256"]
                or metadata.get("preview_sha256") != preview_hash
                or sha(original / metadata["source"]) != render["source_sha256"]
                or sha(original / "figure.pdf") != render["pdf_sha256"]
                or sha(original / "preview.jpg") != preview_hash):
            raise ProvenanceError(f"Selected renderer metadata differs: {figure_id}")
        for name, expected in metadata["files_sha256"].items():
            if sha(_inside(original, name)) != expected:
                raise ProvenanceError(f"Selected renderer input changed: {name}")
        directory = Path("figure_code") / alias
        target = _inside(destination, directory)
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        names = [metadata["source"], "render.json", "figure.pdf", "preview.jpg"]
        names += [name for name in ("worker.R", "sessionInfo.txt") if (original / name).is_file()]
        files = {}
        for name in names:
            if run.get("artifacts") and run["artifacts"].get((original_dir / name).as_posix()) != sha(original / name):
                raise ProvenanceError(f"Original renderer artifact differs from completed run: {name}")
            shutil.copy2(_inside(original, name), target / name)
            files[(directory / name).as_posix()] = sha(target / name)
        items.append({"figure_id":figure_id, "image_path":result["image_path"],
                      "backend":metadata["backend"], "original_directory":original_dir.as_posix(),
                      "source":(directory / metadata["source"]).as_posix(),
                      "source_sha256":metadata["source_sha256"], "preview_sha256":preview_hash,
                      "files":files})
    manifest = {"schema_version":SCHEMA, "policy":"selected-worker-code-v1",
                "figures":sorted(items, key=lambda item:item["figure_id"])}
    verify_files(destination, manifest, originals=True, original_base=base)
    (destination / "figure_provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def publish_workspace(base, workspace):
    base, workspace = Path(base).resolve(), Path(workspace).resolve()
    manifest = json.loads((base / "figure_provenance.json").read_text())
    verify_files(base, manifest, originals=True)
    workspace.mkdir(parents=True, exist_ok=True)
    for item in manifest["figures"]:
        for name in item["files"]:
            destination = _inside(workspace, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_inside(base, name), destination)
    shutil.copy2(base / "figure_provenance.json", workspace / "figure_provenance.json")
    verify_files(workspace, manifest)
    return manifest


def worker_context(base, manifest, *, validate_originals=True):
    verify_files(base, manifest, originals=validate_originals)
    parts = ["[SELECTED FIGURE SOURCE PROVENANCE — USER-AUTHORIZED ADAPTATION]",
             "These exact worker sources produced the selected figure previews. Their copies are bundled "
             "beside the manuscript at the listed relative paths. Reference them; do not reconstruct, "
             "embed, rename or replace R/ggplot2 or TikZ figure recipes. Preserve numerical/algorithm "
             "discussion. The runtime maintains a visible Figure source provenance section before "
             "compilation and review; preserve that section and the supplied figure images. "
             "The manifest, source checksums and renderer inputs are authoritative.",
             json.dumps(manifest, indent=2)]
    for item in manifest["figures"]:
        names = [item["source"]] + [name for name in item["files"] if name.endswith("/worker.R")]
        for name in names:
            parts.append(f"--- EXACT ARTIFACT: {name}; SHA256 {sha(_inside(base, name))} ---\n"
                         + _inside(base, name).read_text())
    return "\n\n".join(parts)


def _text(value):
    # OT1's \\_ can draw a rule instead of an extractable underscore. Use the
    # typewriter glyph so PDF filenames remain exact and copyable as well.
    escaped = "".join({"_":r"\char95{}", "%":r"\%", "#":r"\#", "&":r"\&", "{":r"\{",
                       "}":r"\}", "\\":r"\textbackslash{}"}.get(c, c) for c in value)
    return r"\texttt{" + escaped.replace("/", r"/\allowbreak{}") + "}"


def _hash_text(value):
    return r"\texttt{" + r"\allowbreak{}".join(value[i:i+8] for i in range(0, len(value), 8)) + "}"


def _figure_reference(tex, image_path):
    filename = Path(image_path).name
    for match in re.finditer(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", tex, re.S):
        paths = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}", match.group())
        labels = re.findall(r"\\label\{([\w:.-]+)\}", match.group())
        if any(Path(path).name == filename for path in paths) and labels:
            return r"Figure~\ref{" + labels[-1] + "} (" + _text(filename) + ")"
    return "Figure file " + _text(filename)


def canonical_block(manifest, tex=""):
    lines = [BEGIN, r"\clearpage", r"\section*{Figure source provenance}",
             "The files below are the exact sources that produced the embedded figure previews. "
             "Paths are relative to this manuscript's source directory. "
             "The accompanying " + _text("figure_provenance.json") + r" records all artifact checksums.\par"]
    for item in manifest["figures"]:
        lines += [r"\medskip\noindent\textbf{" + _figure_reference(tex, item["image_path"]) + r".}\par",
                  r"\noindent " + ("R/ggplot2" if item["backend"] == "ggplot2" else "LaTeX/TikZ")
                  + " source: " + _text(item["source"]) + r".\par",
                  r"\noindent Source SHA256: " + _hash_text(item["source_sha256"]) + r".\par"]
        for name in item["files"]:
            if name.endswith("/worker.R"):
                lines += [r"\noindent Exact export wrapper: " + _text(name) + r".\par",
                          r"\noindent Wrapper SHA256: " + _hash_text(item["files"][name]) + r".\par"]
            elif name.endswith(("/render.json", "/sessionInfo.txt")):
                lines.append(r"\noindent Rendering metadata: " + _text(name) + r".\par")
    return "\n".join(lines + [END])


_FILE_CONTENTS = re.compile(r"\\begin\{filecontents(?P<star>\*?)\}(?:\[[^\]]*\])?\s*"
                            r"\{(?P<name>[^{}\n]+)\}(?P<body>.*?)\\end\{filecontents(?P=star)\}", re.S)
_RENDER_CODE = re.compile(r"ggplot\s*\(|ggsave\s*\(|geom_\w+\s*\(|\\begin\{tikzpicture\}", re.I)


def normalize_latex(tex, manifest):
    """Preserve failed/empty responses; assemble provenance before any scoring."""
    if not isinstance(tex, str) or not tex.strip() or not manifest.get("figures"):
        return tex, []
    if r"\begin{document}" not in tex or r"\end{document}" not in tex:
        return tex, []
    tex = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", tex, flags=re.S)
    removed = []
    figures = {item["figure_id"].replace(" ", "_").lower() for item in manifest["figures"]}
    def strip_file(match):
        name, body = match["name"], match["body"]
        if Path(name).suffix.lower() in {".cls", ".sty", ".bst", ".bib"}:
            return match.group()
        if (Path(name).suffix.lower() == ".tikz"
                or _RENDER_CODE.search(body) or Path(name).stem.lower() in figures):
            removed.append(name)
            return ""
        return match.group()
    tex = _FILE_CONTENTS.sub(strip_file, tex)
    # A prose comment left behind by filecontents removal must not claim that
    # compiling the manuscript extracts a replacement recipe.
    def strip_comments(match):
        text = match.group()
        if removed and not re.search(r"copyright|licen[cs]e|SPDX", text, re.I) and (
                "filecontents" in text or any(name in text for name in removed)):
            return ""
        return text
    tex = re.sub(r"(?m)(?:^[ \t]*%[^\n]*\n)+", strip_comments, tex)
    for environment in ("verbatim", "Verbatim", "lstlisting", "minted"):
        pattern = re.compile(r"\\begin\{" + environment + r"\}.*?\\end\{" + environment + r"\}", re.S)
        def strip_listing(match):
            if _RENDER_CODE.search(match.group()):
                removed.append("inline " + environment + " figure recipe")
                return ""
            return match.group()
        tex = pattern.sub(strip_listing, tex)
    # Package setup and prose such as \\texttt{ggplot()} are not recipes. Only
    # executable inline TikZ in the document body needs a remaining-code guard.
    uncommented = re.sub(r"(?m)(?<!\\)%[^\n]*", "", _FILE_CONTENTS.sub("", tex))
    body = uncommented.rsplit(r"\begin{document}", 1)[-1]
    if re.search(r"\\begin\s*\{tikzpicture\}|\\tikz(?=\s|\[|\{)", body):
        raise ProvenanceError("Inline figure rendering code remains; reference the selected source artifacts")
    body, ending = tex.rsplit(r"\end{document}", 1)
    body = body.rstrip()
    return body + "\n\n" + canonical_block(manifest, body) + "\n" + r"\end{document}" + ending, removed


def _replace_latex(raw, effective):
    pattern = re.compile(r"(```latex\s*)(.*?)(\s*```)", re.S)
    if pattern.search(raw):
        return pattern.sub(lambda match:match[1] + effective + match[3], raw, count=1)
    return effective


def transform_result(result, manifest):
    """Keep original formats/worklog, including the format editor's raw channel."""
    updated = copy.deepcopy(result)
    parsed = updated.get("parsed_response")
    kind, tex, container = None, None, None
    if isinstance(parsed, str):
        try:
            container = json.loads(parsed)
        except (ValueError, TypeError):
            container = None
        if isinstance(container, dict) and "latex" in container:
            kind, tex = "content", container["latex"]
        else:
            kind, tex = "section", parsed
    elif isinstance(parsed, dict) and "raw_response" in parsed:
        kind = "format"
        raw = updated.get("raw_response", "")
        match = re.search(r"```latex\s*(.*?)\s*```", raw, re.S)
        tex = match[1] if match else raw.strip()
    effective, removed = normalize_latex(tex, manifest)
    if effective == tex:
        return updated, None
    if kind == "content":
        container["latex"] = effective
        updated["parsed_response"] = json.dumps(container)
    elif kind == "section":
        updated["parsed_response"] = effective
    else:
        updated["parsed_response"]["raw_response"] = _replace_latex(updated["raw_response"], effective)
    updated["raw_response"] = _replace_latex(updated["raw_response"], effective)
    return updated, {"kind":kind, "removed_recipes":removed,
                     "effective_tex_sha256":hashlib.sha256(effective.encode()).hexdigest()}


def verify_manuscript(tex, manifest):
    effective, removed = normalize_latex(tex, manifest)
    if not tex or not isinstance(tex, str) or r"\end{document}" not in tex:
        raise ProvenanceError("Manuscript is incomplete")
    if removed or effective != tex or (manifest["figures"] and BEGIN not in tex):
        raise ProvenanceError("Manuscript source provenance is missing, changed, or contains an alternative recipe")
