"""Native worker adapters; receipts are recomputed from retained provider events."""
from __future__ import annotations

import base64
import hashlib
import importlib
import json
import mimetypes
import os
from pathlib import Path
import re
import signal
import subprocess
import uuid

EXECUTABLES = {"codex":"codex", "claude-code":"claude", "antigravity":"agy", "mistral-vibe":"vibe-acp"}


def read_events(path):
    events = []
    for line in Path(path).read_text().split("\n"):
        if line.strip():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    events.append(value)
            except ValueError:
                pass
    return events


def prepare_invocation(selection, prompt, images, search, directory):
    directory = Path(directory)
    backend = selection.get("backend", "codex")
    model, effort = selection.get("model"), selection.get("effort")
    if backend in {"antigravity", "mistral-vibe"}:
        module = importlib.import_module("orchestra_antigravity" if backend == "antigravity" else "orchestra_vibe")
        return {"backend":backend, **module.prepare(selection, prompt, images, search, directory)}
    if backend == "codex":
        command = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                   "--json", "--color", "never", "--cd", str(directory), "-o", str(directory / "response.txt"),
                   "-c", 'web_search="live"' if search else 'web_search="disabled"']
        if model:
            command += ["--model", model]
        if effort is not None:
            command += ["-c", "model_reasoning_effort=" + json.dumps(effort)]
        for image in images:
            command += ["--image", image]
        return {"backend":backend, "command":command + ["-"], "stdin":prompt, "env":{}}
    if backend != "claude-code":
        raise ValueError(f"Unknown execution backend: {backend}")
    command = ["claude", "--print", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--safe-mode", "--restricted", "--strict-mcp-config", "--disable-slash-commands",
               "--no-chrome", "--no-session-persistence", "--session-id", str(uuid.uuid4()),
               "--tools", "WebSearch" if search else ""]
    if search:
        command += ["--allowedTools", "WebSearch"]
    if model:
        command += ["--model", model]
    if effort is not None:
        command += ["--effort", effort]
    content = [{"type":"text", "text":prompt}]
    for image in images:
        path = Path(image)
        mime = mimetypes.guess_type(path.name)[0]
        if mime not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
            raise ValueError(f"Unsupported Claude image attachment: {path.name}")
        content.append({"type":"image", "source":{"type":"base64", "media_type":mime,
                        "data":base64.b64encode(path.read_bytes()).decode("ascii")}})
    payload = {"type":"user", "message":{"role":"user", "content":content}}
    return {"backend":backend, "command":command, "stdin":json.dumps(payload) + "\n", "env":{}}


def _claude(directory, request):
    events = read_events(Path(directory) / "events.jsonl")
    initial = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    results = [e for e in events if e.get("type") == "result"]
    sessions = [e["session_id"] for e in initial if isinstance(e.get("session_id"), str)]
    errors = []
    if len(initial) != 1 or len(sessions) != 1:
        errors.append("Claude Code did not report one independent session init")
    if len(results) != 1 or results[-1].get("subtype") != "success" or results[-1].get("is_error"):
        errors.append("Claude Code did not report one successful result")
        # Preserve the original retry helper's nonretryable input/400 checks
        # without copying provider error bodies or possible credentials to stdout.
        provider_error = json.dumps(results[-1].get("errors", []) if results else [])
        if re.search(r"\b400\b", provider_error):
            errors.append("400 bad request from native provider")
        if "input token count" in provider_error.lower():
            errors.append("native provider exceeded maximum number of tokens allowed")
    if any(e.get("type") == "error" for e in events):
        errors.append("Claude Code emitted a native error")
    if results and results[-1].get("session_id") != (sessions[0] if sessions else None):
        errors.append("Claude Code result does not belong to its independent session")
    result = results[-1] if results else {}
    response = result.get("result")
    if not isinstance(response, str):
        errors.append("Claude Code final result text is missing")
        response = ""
    searches, completed = set(), set()
    for event in events:
        blocks = event.get("message", {}).get("content", [])
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and "search_required" in request:
                allowed = {"WebSearch"} if request["search_required"] else set()
                if block.get("name") not in allowed:
                    errors.append("Claude Code attempted a tool outside the isolated role policy")
            if (block.get("type") == "tool_use" and block.get("name") == "WebSearch"
                    and isinstance(block.get("id"), str) and block["id"]):
                searches.add(block.get("id"))
            if (block.get("type") == "tool_result" and block.get("is_error") is not True and block.get("content")
                    and isinstance(block.get("tool_use_id"), str) and block["tool_use_id"]):
                completed.add(block.get("tool_use_id"))
    observed_model = initial[0].get("model") if initial else None
    expected_model = request.get("model_routing", {}).get("model")
    if expected_model and expected_model.startswith("claude-") and observed_model != expected_model:
        errors.append("Claude Code reported a different model from the selected full ID")
    observed_effort = initial[0].get("effort") if initial else None
    expected_effort = request.get("model_routing", {}).get("effort")
    if expected_effort is not None and observed_effort is not None and expected_effort != observed_effort:
        errors.append("Claude Code reported a different effort from the selected setting")
    images_delivered = []
    if request.get("images"):
        try:
            plan = json.loads((Path(directory) / "transport.json").read_text())
            payload = json.loads(plan["stdin"])
            blocks = payload["message"]["content"]
            prompt = (Path(directory) / "prompt.txt").read_bytes().decode("utf-8")
            if len(blocks) != len(request["images"]) + 1 or blocks[0] != {"type":"text", "text":prompt}:
                raise ValueError("Claude native input does not preserve the full prompt/image count")
            for path, block in zip(request["images"], blocks[1:]):
                source = block["source"]
                expected = request.get("image_sha256", {}).get(path)
                actual = hashlib.sha256(base64.b64decode(source["data"], validate=True)).hexdigest()
                if block.get("type") != "image" or source.get("type") != "base64" or not expected or actual != expected:
                    raise ValueError("Claude native image bytes differ from the supplied attachment")
                images_delivered.append(path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
    return {"backend":"claude-code", "sessions":sessions, "completed":not errors, "failed":bool(errors),
            "searched":bool(searches & completed), "response":response, "observed_model":observed_model,
            "observed_effort":observed_effort,
            "errors":errors, "images_delivered":images_delivered}


def inspect_invocation(directory, request):
    backend = request.get("backend", "codex")
    if backend == "claude-code":
        return _claude(directory, request)
    if backend in {"antigravity", "mistral-vibe"}:
        module = importlib.import_module("orchestra_antigravity" if backend == "antigravity" else "orchestra_vibe")
        return module.inspect(Path(directory), request)
    events = read_events(Path(directory) / "events.jsonl")
    from orchestra_runtime import executed_search
    sessions = [e["thread_id"] for e in events if e.get("type") == "thread.started"]
    failed = any(e.get("type") in {"turn.failed", "error"} for e in events)
    texts = [e["item"].get("text", "") for e in events if e.get("type") == "item.completed"
             and e.get("item", {}).get("type") == "agent_message"]
    return {"backend":"codex", "sessions":sessions,
            "completed":len(sessions) == 1 and any(e.get("type") == "turn.completed" for e in events) and not failed,
            "failed":failed, "searched":executed_search(events), "response":texts[-1] if texts else None,
            "observed_model":None, "observed_effort":None, "errors":[], "images_delivered":request.get("images", [])}


def validate_invocation_plan(directory, request, command, selection):
    """Bind selected settings and input bytes to the actual native launch plan."""
    directory = Path(directory)
    backend = selection.get("backend", "codex")
    if "transport_plan_sha256" not in request:
        if backend == "codex" and "backend" not in selection:
            return []  # Explicit backward compatibility for pre-adapter evidence.
        return ["Native invocation has no anchored transport plan"]
    errors = []
    try:
        path = directory / "transport.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != request["transport_plan_sha256"]:
            raise ValueError("Native transport plan hash differs")
        plan = json.loads(path.read_text())
        # Universal-newline reads change CRLF from the original prompt, which
        # can come from external reference metadata or caller-supplied material.
        prompt = (directory / "prompt.txt").read_bytes().decode("utf-8")
        if plan["backend"] != backend or request.get("backend", "codex") != backend:
            raise ValueError("Native execution backend differs from selected runtime")
        if command != plan["command"] or Path(command[0]).name != EXECUTABLES[backend]:
            raise ValueError("Native executable/argv differs from the selected runtime")
        forbidden = {"--resume", "--continue", "--conversation", "--fork-session", "--fallback-model",
                     "--dangerously-skip-permissions", "--auto-approve", "--yolo"}
        if any(flag in command for flag in forbidden):
            raise ValueError("Native launch resumes, substitutes, or bypasses the independent worker policy")
        model, effort = selection.get("model"), selection.get("effort")
        if backend in {"codex", "claude-code"}:
            if model is None:
                if "--model" in command:
                    raise ValueError("Model argv overrides an explicitly inherited model")
            elif command.count("--model") != 1 or command[command.index("--model") + 1] != model:
                raise ValueError("Native model argv differs from selected model")
            if backend == "codex":
                settings = [command[i + 1] for i, arg in enumerate(command[:-1]) if arg == "-c"]
                efforts = [s for s in settings if s.startswith("model_reasoning_effort=")]
                expected = [] if effort is None else ["model_reasoning_effort=" + json.dumps(effort)]
                if efforts != expected:
                    raise ValueError("Codex effort configuration differs from selected effort")
                required = {"--ephemeral", "--sandbox", "read-only"}
                if not required.issubset(command):
                    raise ValueError("Codex worker is not ephemeral/read-only")
                if plan["stdin"] != prompt:
                    raise ValueError("Codex stdin differs from retained prompt")
            else:
                effort_flags = [command[i + 1] for i, arg in enumerate(command[:-1]) if arg == "--effort"]
                if effort_flags != ([] if effort is None else [effort]):
                    raise ValueError("Claude effort argv differs from selected effort")
                required = {"--print", "--safe-mode", "--restricted", "--no-session-persistence", "--strict-mcp-config"}
                if not required.issubset(command):
                    raise ValueError("Claude worker lacks its scoped execution flags")
                allowed = "WebSearch" if request["search_required"] else ""
                if command.count("--tools") != 1 or command[command.index("--tools") + 1] != allowed:
                    raise ValueError("Claude tools differ from the discovery-only search policy")
                payload = json.loads(plan["stdin"])
                content = payload["message"]["content"]
                if payload["type"] != "user" or content[0] != {"type":"text", "text":prompt}:
                    raise ValueError("Claude native input differs from retained prompt")
        else:
            if plan["acp"]["model"] != model or plan["acp"]["effort"] != effort:
                raise ValueError("ACP settings differ from selected model/effort")
            if plan["stdin"] != prompt:
                raise ValueError("ACP prompt differs from retained prompt")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        errors.append(str(exc))
    return errors


def execute_invocation(plan, directory, timeout, process_started):
    backend = plan["backend"]
    if backend in {"antigravity", "mistral-vibe"}:
        module = importlib.import_module("orchestra_antigravity" if backend == "antigravity" else "orchestra_vibe")
        return module.execute(plan, Path(directory), timeout, process_started)
    directory = Path(directory)
    with (directory / "events.jsonl").open("w") as out, (directory / "stderr.log").open("w") as err:
        process = subprocess.Popen(plan["command"], stdin=subprocess.PIPE, stdout=out, stderr=err,
                                   text=True, cwd=directory, env={**os.environ, **plan.get("env", {})}, start_new_session=True)
        process_started(process.pid)
        try:
            process.communicate(input=plan["stdin"], timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
    request = json.loads((directory / "request.json").read_text())
    receipt = inspect_invocation(directory, request)
    if process.returncode or not receipt["completed"]:
        raise RuntimeError(f"{backend} worker exited {process.returncode}: " + "; ".join(receipt["errors"]) + "; inspect native events/stderr")
    return receipt["response"]
