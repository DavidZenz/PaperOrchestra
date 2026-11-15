"""Separate-process Codex transport for the pinned PaperOrchestra controller.

No agent role is executed by this Python process. It transports original prompts,
attachments and tool requests to fresh Codex sessions and records their evidence.
"""
from __future__ import annotations

import functools
import contextvars
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from types import SimpleNamespace
import uuid

_call_id = contextvars.ContextVar("paper_orchestra_call", default=None)
role_override = contextvars.ContextVar("paper_orchestra_role", default=None)
figure_context = contextvars.ContextVar("paper_orchestra_figure", default=None)


class CapabilityError(RuntimeError):
    pass


def executed_search(events):
    """Require a completed tool item, never prose mentioning a tool name."""
    for event in events:
        item = event.get("item", {})
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        if (item.get("type") == "web_search" and item.get("status") != "failed"
                and not item.get("error") and not (item.get("result") or {}).get("isError")):
            return True
        if (item.get("type") == "mcp_tool_call" and item.get("server") == "codex_apps"
                and item.get("tool") == "search_service.web_run" and item.get("status") == "completed"
                and not item.get("error") and not (item.get("result") or {}).get("isError")):
            return True
    return False


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def origin():
    """Identify the original role/callsite without changing its prompt."""
    stack = inspect.stack()
    paths = []
    for frame in stack:
        path = Path(frame.filename)
        if "methods" in path.parts or "autoraters" in path.parts or path.name in {"paper_banana_utils.py", "orchestra_visuals.py"}:
            paths.append(f"{path.name}:{frame.function}:{frame.lineno}")
    if role_override.get():
        return role_override.get(), paths
    role = "unknown"
    joined = " ".join(paths)
    for marker, label in [
        ("get_meta_review", "area-chair"),
        ("perform_review_agentreview", "peer-reviewer"),
        ("_get_formatting_review", "format-reviewer"),
        ("outline_agent.py", "outline"),
        ("_discover_candidates", "literature-discovery"),
        ("_synthesize_content", "literature-synthesis"),
        ("section_writing_agent.py", "section-writer"),
        ("retrieve_few_shot_examples", "figure-retriever"),
        ("predict_figure_content", "figure-planner"),
        ("style_figure_content", "figure-stylist"),
        ("critique_and_revise_figure", "figure-critic"),
        ("generate_figure_caption", "figure-captioner"),
        ("generate_figure_visuals", "figure-visualizer"),
        ("content_refinement_agent.py", "content-or-format-editor"),
    ]:
        if marker in joined:
            role = label
            break
    return role, paths


class Runtime:
    def __init__(self, trace_dir, *, model=None, model_map=None, timeout=600,
                 image_command=None, executor=None, plot_backend="ggplot2", diagram_backend="tikz",
                 rscript="Rscript", render_timeout=60, manuscript_provenance=False):
        self.root = Path(trace_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.model_map = model_map or {}
        self.timeout = timeout
        self.image_command = image_command
        self.executor = executor or self._execute
        self.lock = threading.Lock()
        self.sequence = 0
        self.fatal = []
        self.pending_search = set()
        self.sessions = set()
        self.plot_backend = plot_backend
        self.diagram_backend = diagram_backend
        self.rscript = rscript
        self.render_timeout = render_timeout
        self.manuscript_provenance = manuscript_provenance
        self.figure_provenance = None

    def event(self, kind, **fields):
        with self.lock:
            self.sequence += 1
            event = dict(seq=self.sequence, time=time.time(), event=kind, **fields)
            with (self.root / "trace.jsonl").open("a") as f:
                f.write(json.dumps(event, default=str) + "\n")
        return event

    def unavailable(self, message):
        self.fatal.append(message)
        self.event("capability_failure", message=message)
        raise CapabilityError(message)

    def _execute(self, command, prompt, directory):
        # argv, never a shell. Fresh invocation, never exec resume/fork.
        with (directory / "events.jsonl").open("w") as out, (directory / "stderr.log").open("w") as err:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out,
                                       stderr=err, text=True, cwd=directory)
            self.event("process_started", invocation=directory.name, pid=process.pid)
            try:
                process.communicate(input=prompt, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise TimeoutError(f"Separate agent exceeded {self.timeout}s")
            except BaseException:
                process.kill()
                process.communicate()
                raise
            if process.returncode:
                # Preserve provider error text needed by upstream's nonretryable
                # input/400 checks; do not dump host stderr or authentication data.
                details = []
                for line in (directory / "events.jsonl").read_text().split("\n"):
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type") in {"turn.failed", "error"}:
                        details.append(str(event.get("error", event.get("message", ""))))
                raise RuntimeError(f"Separate agent exited {process.returncode}; {'; '.join(details)}; see {directory / 'stderr.log'}")
        return (directory / "response.txt").read_text()

    def generate(self, contents, config, requested_model):
        role, callsite = origin()
        if requested_model == "runtime-probe":
            role = "runtime-probe"
        invocation = uuid.uuid4().hex
        directory = self.root / "invocations" / invocation
        directory.mkdir(parents=True)
        config = describe(config) or {}
        if config.get("response_modalities") and "IMAGE" in config["response_modalities"]:
            return self.generate_image(contents, config, requested_model, directory, role, callsite)

        text_parts, images, media = [], [], []
        def consume(part):
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, (list, tuple)):
                for item in part:
                    consume(item)
            elif getattr(part, "parts", None):
                consume(part.parts)
            elif getattr(part, "text", None) is not None:
                text_parts.append(part.text)
            elif getattr(part, "inline_data", None):
                data = part.inline_data
                suffix = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}.get(data.mime_type)
                if not suffix:
                    self.unavailable(f"Unsupported upstream attachment type: {data.mime_type}")
                path = directory / f"attachment-{len(media)}{suffix}"
                path.write_bytes(data.data)
                media.append(dict(path=str(path), mime_type=data.mime_type, sha256=digest(path)))
                if suffix == ".pdf":
                    import pymupdf
                    with pymupdf.open(path) as doc:
                        # Preserve visual and textual PDF context, without truncation.
                        text_parts.append("[PDF attachment extracted text]\n" + "\n".join(p.get_text() for p in doc))
                        for index, page in enumerate(doc):
                            image = directory / f"pdf-{len(media)}-page-{index + 1}.png"
                            page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(image)
                            images.append(str(image))
                else:
                    images.append(str(path))
            else:
                self.unavailable(f"Unsupported upstream content part: {type(part).__name__}")
        consume(contents)
        system = config.get("system_instruction", "")
        if not isinstance(system, str):
            self.unavailable("Nontext system_instruction needs an explicit transport implementation")
        search = bool(config.get("tools"))
        prompt = ("Execute only this independent PaperOrchestra invocation. Do not delegate or run the whole pipeline. "
                  "Use only the supplied task inputs; return its requested output format verbatim. "
                  "Do not read other invocation folders. Do not write workspace files.\n\n"
                  + ("[UPSTREAM SYSTEM INSTRUCTION]\n" + system + "\n\n" if system else "")
                  + "\n\n".join(text_parts))
        if search:
            prompt += "\n\n[TRANSPORT TOOL REQUIREMENT] Use live web search for this discovery task before answering."
        provenance_fields = {}
        if self.figure_provenance and role in {"section-writer", "content-or-format-editor"}:
            from orchestra_provenance import publish_workspace, worker_context
            base = self.root.parent
            publish_workspace(base, directory)
            prompt += "\n\n" + worker_context(base, self.figure_provenance)
            provenance_fields = {
                "figure_provenance_sha256":digest(directory / "figure_provenance.json"),
                "figure_provenance_files":{
                    name:digest(directory / name)
                    for item in self.figure_provenance["figures"] for name in item["files"]}}
        (directory / "prompt.txt").write_text(prompt)
        search_key = hashlib.sha256(prompt.encode()).hexdigest()
        if search:
            with self.lock:
                self.pending_search.add(search_key)
        effective_model = self.model_map.get(requested_model, self.model)
        request = dict(invocation=invocation, call=_call_id.get(), role=role, callsite=callsite,
                       figure_id=figure_context.get(),
                       requested_model=requested_model, effective_model=effective_model or "Codex configured default",
                       config=config, search_required=search, media=media, images=images,
                       prompt_sha256=digest(directory / "prompt.txt"), **provenance_fields)
        (directory / "request.json").write_text(json.dumps(request, indent=2, default=str))
        command = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                   "--json", "--color", "never", "--cd", str(directory),
                   "-o", str(directory / "response.txt")]
        # No search for authors, reviewers, or editors. Discovery alone gets live search.
        command.extend(["-c", 'web_search="live"' if search else 'web_search="disabled"'])
        if effective_model:
            command.extend(["--model", effective_model])
        for image in images:
            command.extend(["--image", image])
        command.append("-")
        self.event("agent_start", **request, command=command)
        try:
            raw = self.executor(command, prompt, directory)
            (directory / "response.txt").write_text(raw)
            events_path = directory / "events.jsonl"
            events = []
            if events_path.exists():
                for line in events_path.read_text().split("\n"):
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        pass
            sessions = [e["thread_id"] for e in events if e.get("type") == "thread.started"]
            searched = executed_search(events)
            failed_turn = any(e.get("type") in {"turn.failed", "error"} for e in events)
            if failed_turn:
                raise RuntimeError("Codex emitted a failed turn; inspect events.jsonl")
            if self.executor == self._execute:
                if len(sessions) != 1 or not any(e.get("type") == "turn.completed" for e in events):
                    raise RuntimeError("Codex produced no single completed independent session evidence")
                with self.lock:
                    if sessions[0] in self.sessions:
                        raise RuntimeError("Codex reused an existing session")
                    self.sessions.add(sessions[0])
            if search and not searched:
                self.event("search_evidence_missing", invocation=invocation, task=search_key)
                raise RuntimeError("Discovery agent provided no completed live web_search execution evidence")
            if search:
                with self.lock:
                    self.pending_search.discard(search_key)
            self.event("agent_end", invocation=invocation, role=role, sessions=sessions,
                       searched=searched, response_sha256=digest(directory / "response.txt"))
            return SimpleNamespace(text=raw)
        except Exception as exc:
            self.event("agent_error", invocation=invocation, error=str(exc))
            raise

    def generate_image(self, contents, config, requested_model, directory, role, callsite):
        if not self.image_command:
            self.unavailable("Diagram generation requires a separately configured image-tool command; Codex text execution cannot generate image bytes")
        payload = dict(contents=[describe(p) for p in contents], config=config,
                       requested_model=requested_model, output_path=str(directory / "image.png"))
        request_path = directory / "image-request.json"
        request_path.write_text(json.dumps(payload, default=str, indent=2))
        # Contract: executable argv receives request JSON path; writes output_path.
        command = list(self.image_command) + [str(request_path)]
        self.event("image_start", invocation=directory.name, role=role, callsite=callsite, command=command)
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout, cwd=directory)
        (directory / "image-tool.log").write_text(completed.stdout + completed.stderr)
        image_path = directory / "image.png"
        if completed.returncode or not image_path.exists():
            raise RuntimeError("Image tool failed or did not produce output_path")
        from PIL import Image
        with Image.open(image_path) as im:
            im.verify()
        self.event("image_end", invocation=directory.name, image_sha256=digest(image_path))
        part = SimpleNamespace(inline_data=SimpleNamespace(data=image_path.read_bytes()))
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


_runtime = None


def configure(runtime):
    global _runtime
    _runtime = runtime


def get_runtime():
    if _runtime is None:
        raise CapabilityError("Configure the separate-agent runtime via scripts/run.py; no inline agent fallback exists")
    return _runtime


class CodexModels:
    def generate_content(self, *, model, contents, config):
        return get_runtime().generate(contents, config, model)


class CodexClient:
    models = CodexModels()


def trace_call(function):
    """Observe parse results while leaving the upstream five-attempt loop intact."""
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        runtime = get_runtime()
        call = uuid.uuid4().hex
        token = _call_id.set(call)
        runtime.event("llm_call_start", call=call, role=origin()[0], figure_id=figure_context.get())
        try:
            result = function(*args, **kwargs)
            if runtime.figure_provenance and origin()[0] in {"section-writer", "content-or-format-editor"}:
                from orchestra_provenance import transform_result
                original_path = runtime.root / "manuscripts" / f"{call}.upstream.json"
                original_path.parent.mkdir(exist_ok=True)
                original_path.write_text(json.dumps(result, default=str, indent=2))
                result, details = transform_result(result, runtime.figure_provenance)
                effective_path = runtime.root / "manuscripts" / f"{call}.effective.json"
                effective_path.write_text(json.dumps(result, default=str, indent=2))
                runtime.event("manuscript_result", call=call, role=origin()[0],
                              original_path=str(original_path), original_sha256=digest(original_path),
                              effective_path=str(effective_path), effective_sha256=digest(effective_path),
                              provenance_sha256=digest(runtime.root.parent / "figure_provenance.json"),
                              adaptation=details)
            path = runtime.root / "parsed" / f"{call}.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(result["parsed_response"], default=str, indent=2))
            runtime.event("llm_call_end", call=call, parsed_path=str(path), sha256=digest(path))
            return result
        except Exception as exc:
            runtime.event("llm_call_error", call=call, error=str(exc))
            raise
        finally:
            _call_id.reset(token)
    return wrapped


def trace_image_call(function):
    """Let upstream exhaust its image retries, then report missing required output."""
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        result = function(*args, **kwargs)
        if not result:
            get_runtime().unavailable("Required image tool exhausted upstream retries without producing a valid image")
        return result
    return wrapped


def artifacts(base):
    result = {}
    for path in sorted(Path(base).rglob("*")):
        if path.is_file() and path.name != "run.json" and path.suffix.lower() in {".json", ".tex", ".bib", ".md", ".pdf", ".png", ".jpg", ".r", ".txt"}:
            if "execution" not in path.relative_to(base).parts:
                result[str(path.relative_to(base))] = digest(path)
    return result


def instrument(base):
    """Observe actual controller stages and handoff file hashes, not another DAG."""
    from methods.agents.outline_agent import OutlineAgent
    from methods.agents.literature_review_agent import HybridLiteratureAgent
    from methods.agents.section_writing_agent import SectionWritingAgent
    from methods.agents.content_refinement_agent import ContentRefinementAgent
    from methods.agents.plotting_agent import PlottingAgent
    import methods.agents.content_refinement_agent as refinement
    import requests
    original_get = requests.get
    if not getattr(original_get, "_orchestra_observer", False):
        @functools.wraps(original_get)
        def observed_get(url, *args, **kwargs):
            runtime = get_runtime()
            request_id = uuid.uuid4().hex
            runtime.event("http_start", request=request_id, url=url, params=kwargs.get("params"))
            try:
                result = original_get(url, *args, **kwargs)
                runtime.event("http_end", request=request_id, status=result.status_code,
                              response_sha256=hashlib.sha256(result.content).hexdigest())
                return result
            except Exception as exc:
                runtime.event("http_error", request=request_id, error=str(exc))
                raise
        observed_get._orchestra_observer = True
        requests.get = observed_get
    original_compile = refinement.compile_latex
    if not getattr(original_compile, "_orchestra_observer", False):
        @functools.wraps(original_compile)
        def observed_compile(cwd, pdf_file, texfile_name="template", timeout=30):
            runtime = get_runtime()
            tex_path = Path(cwd) / f"{texfile_name}.tex"
            if runtime.figure_provenance:
                from orchestra_provenance import publish_workspace, verify_files, verify_manuscript, ProvenanceError
                try:
                    verify_files(cwd, runtime.figure_provenance)
                    source = tex_path.read_text()
                    # Ordinary incomplete LaTeX still reaches upstream's compile-
                    # failure handling; do not turn it into an appendix-only paper.
                    if r"\begin{document}" in source and r"\end{document}" in source:
                        verify_manuscript(source, runtime.figure_provenance)
                        snapshot = runtime.root / "compiled" / uuid.uuid4().hex
                        publish_workspace(runtime.root.parent, snapshot)
                        source_snapshot = snapshot / "source.tex"
                        source_snapshot.write_text(source)
                        runtime.event("compile_provenance", tex=str(tex_path), tex_sha256=digest(tex_path),
                                      source_snapshot=str(source_snapshot), source_snapshot_sha256=digest(source_snapshot),
                                      provenance_snapshot=str(snapshot / "figure_provenance.json"),
                                      provenance_sha256=digest(Path(cwd) / "figure_provenance.json"))
                except ProvenanceError as exc:
                    runtime.fatal.append(str(exc))
                    runtime.event("provenance_error", error=str(exc))
                    raise
            runtime.event("compile_start", tex=str(tex_path), pdf=pdf_file,
                          tex_sha256=digest(tex_path) if tex_path.is_file() else None)
            result = original_compile(cwd, pdf_file, texfile_name, timeout)
            exists = Path(pdf_file).is_file()
            runtime.event("compile_end", pdf=pdf_file, exists=exists,
                          sha256=digest(pdf_file) if exists else None)
            return result
        observed_compile._orchestra_observer = True
        refinement.compile_latex = observed_compile
    for cls in [OutlineAgent, HybridLiteratureAgent, PlottingAgent, SectionWritingAgent, ContentRefinementAgent]:
        original = cls.run
        if getattr(original, "_orchestra_observer", False):
            continue
        def wrap(fn, label):
            @functools.wraps(fn)
            def observed(*args, **kwargs):
                runtime = get_runtime()
                stage_base = runtime.root.parent
                if runtime.manuscript_provenance:
                    from orchestra_provenance import build_manifest, publish_workspace
                    if label == "SectionWritingAgent":
                        runtime.figure_provenance = build_manifest(stage_base)
                        bound = inspect.signature(fn).bind(*args, **kwargs)
                        publish_workspace(stage_base, Path(bound.arguments["output_path"]).parent)
                        runtime.event("provenance_published", stage=label,
                                      sha256=digest(stage_base / "figure_provenance.json"))
                    elif label == "ContentRefinementAgent" and runtime.figure_provenance:
                        publish_workspace(stage_base, args[0].work_dir)
                        runtime.event("provenance_published", stage=label,
                                      sha256=digest(stage_base / "figure_provenance.json"))
                span = uuid.uuid4().hex
                runtime.event("stage_start", stage=label, span=span, inputs=artifacts(stage_base))
                try:
                    result = fn(*args, **kwargs)
                    if label == "ContentRefinementAgent":
                        for key, decision in args[0].worklogs.items():
                            runtime.event("revision_decision", version=key, **decision)
                        for key, decision in args[0].format_worklogs.items():
                            runtime.event("format_decision", version=key, **decision)
                    runtime.event("stage_end", stage=label, span=span, outputs=artifacts(stage_base))
                    return result
                except Exception as exc:
                    runtime.event("stage_error", stage=label, span=span, error=str(exc))
                    raise
            observed._orchestra_observer = True
            return observed
        cls.run = wrap(original, cls.__name__)
