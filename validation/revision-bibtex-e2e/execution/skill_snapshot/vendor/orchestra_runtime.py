"""Separate-process worker transport for the pinned PaperOrchestra controller.

No agent role is executed by this Python process. It transports original prompts,
attachments and tool requests to fresh native sessions and records their evidence.
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
_routing_role = contextvars.ContextVar("paper_orchestra_model_role", default=None)


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
                 rscript="Rscript", render_timeout=60, manuscript_provenance=False,
                 model_profile=None, role_models=None, backend=None, effort=None,
                 bibliography_required=False, formatting_scope_required=False):
        self.root = Path(trace_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.model_map = model_map or {}
        from orchestra_execution import execution_policy
        self.model_policy = execution_policy(model=model, model_map=model_map,
                                             profile=model_profile, role_models=role_models,
                                             backend=backend, effort=effort)
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
        self.bibliography_required = bibliography_required
        self.revision_bibliography_style = None
        self.formatting_scope_required = formatting_scope_required

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
        plan_path = directory / "transport.json"
        if plan_path.is_file():
            plan = json.loads(plan_path.read_text())
            if plan["backend"] != "codex":
                from orchestra_transports import execute_invocation
                return execute_invocation(plan, directory, self.timeout,
                    lambda pid:self.event("process_started", invocation=directory.name,
                                           pid=pid, backend=plan["backend"]))
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
                  "You are an already dispatched role worker; model selection is complete. "
                  "Do not invoke the PaperOrchestra setup flow or ask which model to use. "
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
        routing_role = _routing_role.get() or role
        if routing_role == "content-editor" and self.revision_bibliography_style:
            from orchestra_bibliography import revision_bibliography_rule
            prompt += "\n\n" + revision_bibliography_rule(self.revision_bibliography_style)
            provenance_fields["revision_bibliography_style"] = self.revision_bibliography_style
        if self.formatting_scope_required:
            from orchestra_formatting import FORMAT_EDITOR_RULE, FORMAT_REVIEW_RULE
            if routing_role == "format-editor":
                prompt += "\n\n" + FORMAT_EDITOR_RULE
            elif routing_role == "format-reviewer":
                prompt += "\n\n" + FORMAT_REVIEW_RULE
        (directory / "prompt.txt").write_bytes(prompt.encode("utf-8"))
        search_key = hashlib.sha256(prompt.encode()).hexdigest()
        if search:
            with self.lock:
                self.pending_search.add(search_key)
        selection = self.model_policy.resolve(_routing_role.get() or role, requested_model, legacy_role=role)
        effective_model = selection["model"]
        from orchestra_execution import configured_default
        from orchestra_transports import prepare_invocation, inspect_invocation
        backend = selection.get("backend", "codex")
        try:
            plan = prepare_invocation(selection, prompt, images, search, directory)
        except (ValueError, OSError) as exc:
            self.unavailable(f"{backend} worker cannot accept this invocation: {exc}")
        (directory / "transport.json").write_text(json.dumps(plan, indent=2))
        request = dict(invocation=invocation, call=_call_id.get(), role=role, callsite=callsite,
                       figure_id=figure_context.get(),
                       requested_model=requested_model, effective_model=effective_model or configured_default(backend),
                       config=config, search_required=search, media=media, images=images,
                       image_sha256={path:digest(path) for path in images}, backend=backend,
                       transport_plan_sha256=digest(directory / "transport.json"),
                       prompt_sha256=digest(directory / "prompt.txt"), model_routing=selection, **provenance_fields)
        (directory / "request.json").write_text(json.dumps(request, indent=2, default=str))
        command = plan["command"]
        self.event("agent_start", **request, command=command)
        try:
            raw = self.executor(command, prompt, directory)
            (directory / "response.txt").write_text(raw)
            events_path = directory / "events.jsonl"
            receipt = inspect_invocation(directory, request) if events_path.exists() else {
                "sessions":[], "searched":False, "failed":False, "completed":False, "errors":[]}
            sessions, searched = receipt["sessions"], receipt["searched"]
            if receipt["failed"]:
                raise RuntimeError(f"{backend} emitted a failed turn; inspect native events: " + "; ".join(receipt.get("errors", [])))
            if self.executor == self._execute or backend != "codex":
                if len(sessions) != 1 or not receipt["completed"]:
                    raise RuntimeError(f"{backend} produced no single completed independent session evidence")
                if receipt.get("response") is not None and receipt["response"] != raw:
                    raise RuntimeError(f"{backend} native final response differs from its returned artifact")
                with self.lock:
                    session_key = (backend, sessions[0])
                    if session_key in self.sessions:
                        raise RuntimeError(f"{backend} reused an existing session")
                    self.sessions.add(session_key)
            if search and not searched:
                self.event("search_evidence_missing", invocation=invocation, task=search_key)
                raise RuntimeError("Discovery agent provided no completed live web_search execution evidence")
            if search:
                with self.lock:
                    self.pending_search.discard(search_key)
            self.event("agent_end", invocation=invocation, role=role, sessions=sessions,
                       backend=backend, searched=searched, response_sha256=digest(directory / "response.txt"))
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
        role = origin()[0]
        route = role
        if role == "content-or-format-editor":
            parser = inspect.signature(function).bind_partial(*args, **kwargs).arguments.get("result_parsing_func")
            name = getattr(parser, "__name__", "")
            if name == "parse_gemini_json_latex_response":
                route = "content-editor"
            elif name == "<lambda>":
                route = "format-editor"
        route_token = _routing_role.set(route)
        runtime.event("llm_call_start", call=call, role=role, routing_role=route, figure_id=figure_context.get())
        try:
            result = function(*args, **kwargs)
            bibliography_style = runtime.revision_bibliography_style if route == "content-editor" else None
            if bibliography_style or (runtime.figure_provenance and role in {"section-writer", "content-or-format-editor"}):
                from orchestra_provenance import transform_result
                original_path = runtime.root / "manuscripts" / f"{call}.upstream.json"
                original_path.parent.mkdir(exist_ok=True)
                original_path.write_text(json.dumps(result, default=str, indent=2))
                result, details = transform_result(result, runtime.figure_provenance, bibliography_style)
                effective_path = runtime.root / "manuscripts" / f"{call}.effective.json"
                effective_path.write_text(json.dumps(result, default=str, indent=2))
                runtime.event("manuscript_result", call=call, role=role,
                              original_path=str(original_path), original_sha256=digest(original_path),
                              effective_path=str(effective_path), effective_sha256=digest(effective_path),
                              provenance_sha256=(digest(runtime.root.parent / "figure_provenance.json")
                                                 if runtime.figure_provenance else None),
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
            _routing_role.reset(route_token)
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
    runtime = get_runtime()
    if runtime.bibliography_required:
        import methods.agents.literature_review_agent as literature
        from orchestra_references import ReferenceRetriever
        def record_reference(event, **fields):
            record = {"event": event, **fields}
            destination = runtime.root / "reference_retrieval" / (uuid.uuid4().hex + ".json")
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(json.dumps(record, indent=2, default=str))
            runtime.event("reference_retrieval", path=str(destination), sha256=digest(destination))
        retriever = ReferenceRetriever(recorder=record_reference,
                                       get=lambda *a, **kw: requests.get(*a, **kw))
        literature.s2_title_search = retriever.lookup
        original_bibtex = HybridLiteratureAgent._generate_bibtex
        if not getattr(original_bibtex, "_orchestra_metadata_escape", False):
            @functools.wraps(original_bibtex)
            def escaped_bibtex(self, papers):
                from orchestra_bibliography import escape_bibtex_fields
                return escape_bibtex_fields(original_bibtex(self, papers))
            escaped_bibtex._orchestra_metadata_escape = True
            HybridLiteratureAgent._generate_bibtex = escaped_bibtex
    original_get = requests.get
    if not getattr(original_get, "_orchestra_observer", False):
        @functools.wraps(original_get)
        def observed_get(url, *args, **kwargs):
            runtime = get_runtime()
            request_id = uuid.uuid4().hex
            safe_params = {key: ("[REDACTED]" if key.lower() in {"api_key", "apikey", "token", "key"} else value)
                           for key, value in (kwargs.get("params") or {}).items()}
            runtime.event("http_start", request=request_id, url=url, params=safe_params)
            try:
                result = original_get(url, *args, **kwargs)
                runtime.event("http_end", request=request_id, status=result.status_code,
                              response_sha256=hashlib.sha256(result.content).hexdigest())
                return result
            except Exception as exc:
                # Requests exceptions can embed URLs containing API-key query
                # parameters; retain the failure type without credential text.
                runtime.event("http_error", request=request_id, error_type=type(exc).__name__)
                raise
        observed_get._orchestra_observer = True
        requests.get = observed_get
    original_compile = refinement.compile_latex
    if not getattr(original_compile, "_orchestra_observer", False):
        @functools.wraps(original_compile)
        def observed_compile(cwd, pdf_file, texfile_name="template", timeout=30):
            runtime = get_runtime()
            tex_path = Path(cwd) / f"{texfile_name}.tex"
            if texfile_name == "initial_draft":
                runtime.revision_bibliography_style = None
            def compile_start():
                runtime.event("compile_start", tex=str(tex_path), pdf=pdf_file,
                              tex_sha256=digest(tex_path) if tex_path.is_file() else None)

            if runtime.formatting_scope_required and texfile_name.startswith("formatted_candidate_v"):
                from orchestra_formatting import FormattingScopeError, validate_formatting
                try:
                    validate_formatting(cwd, tex_path)
                except FormattingScopeError as exc:
                    # Retain both sources and let the original controller keep
                    # its last accepted PDF through the compile-failure branch.
                    Path(pdf_file).unlink(missing_ok=True)
                    runtime.event("formatting_scope", tex=str(tex_path), valid=False, error=str(exc))
                    print(f" >> Formatting rejected: {exc}. Keeping the last accepted manuscript.")
                    return
                runtime.event("formatting_scope", tex=str(tex_path), valid=True)
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
            compile_start()
            result = original_compile(cwd, pdf_file, texfile_name, timeout)
            if runtime.bibliography_required and Path(pdf_file).is_file():
                from orchestra_bibliography import validate_manuscript, BibliographyError
                try:
                    audit = validate_manuscript(cwd, texfile_name,
                        runtime.root.parent / "literature_agent_output" / "citation_map.json", pdf_path=pdf_file)
                    if texfile_name == "initial_draft":
                        runtime.revision_bibliography_style = audit["bibliography_style"]
                    elif (texfile_name.startswith("refined_paper_v") and
                          audit["bibliography_style"] != runtime.revision_bibliography_style):
                        raise BibliographyError("Content revision changed the verified BibTeX style")
                    runtime.event("bibliography_compile", tex=str(tex_path), audit=audit)
                except BibliographyError as exc:
                    # Feed the original compile-failure branch; do not accept a
                    # citation-dropping revision on PDF existence alone.
                    Path(pdf_file).unlink(missing_ok=True)
                    runtime.event("bibliography_compile_failure", tex=str(tex_path), error=str(exc))
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
                    if label == "HybridLiteratureAgent" and runtime.bibliography_required:
                        from orchestra_bibliography import validate_library
                        audit = validate_library(args[0].output_dir)
                        runtime.event("bibliography_library", audit=audit)
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
