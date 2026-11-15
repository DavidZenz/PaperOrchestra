"""One fresh ACP-v1 process/session/turn per PaperOrchestra model attempt.

Native JSON-RPC messages are retained, not translated into Codex events. The
inspector replays the actual wire receipt, including inline media and tool policy.
"""
from __future__ import annotations

import base64
from collections import Counter
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time


class ACPError(RuntimeError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    values = []
    for line in Path(path).read_text().split("\n"):
        if line.strip():
            values.append(json.loads(line))
    return values


def options(value):
    return {item["id"]: item for item in value.get("configOptions", []) if isinstance(item, dict) and "id" in item}


def values(option):
    found = []
    for item in option.get("options", []):
        if "options" in item:
            found.extend(values(item))
        elif "value" in item:
            found.append(item["value"])
    return found


def tool_name(tool):
    """Canonical native metadata only; prose and a generic search kind aren't proof."""
    candidates = [tool, tool.get("_meta", {}), tool.get("rawInput", {})]
    meta = tool.get("_meta", {})
    if isinstance(meta, dict):
        candidates += [meta.get("antigravity", {}), meta.get("vibe", {})]
    for item in candidates:
        if isinstance(item, dict):
            for key in ("tool_name", "toolName", "name"):
                if isinstance(item.get(key), str):
                    return item[key]
    return None


def permission_reply(params, allowed, known_tools=None):
    supplied = params.get("toolCall", {})
    tool = dict((known_tools or {}).get(supplied.get("toolCallId"), {}))
    tool.update(supplied)
    safe = tool_name(tool) in allowed
    desired = "allow_once" if safe else "reject_once"
    selected = next((item for item in params.get("options", []) if item.get("kind") == desired), None)
    if selected is None and not safe:
        selected = next((item for item in params.get("options", []) if item.get("kind") == "reject_always"), None)
    return {"outcome": {"outcome": "selected", "optionId": selected["optionId"]}} if selected else {"outcome": {"outcome": "cancelled"}}


def native_search_status(backend, start, finish):
    """Antigravity 1.5.9 emits search identity/status but no result payload.

    This is deliberately backend-specific: require the exact observed native
    name, kind and unchanged query on a matched start/completed call. It proves
    native search completion; it does not claim a retained search-result body.
    """
    if backend != "antigravity" or not start or not finish:
        return False
    query = start.get("rawInput", {}).get("query")
    return (isinstance(query, str) and bool(query.strip())
            and start.get("name") == finish.get("name") == "search_web"
            and start.get("kind") == finish.get("kind") == "search"
            and start.get("status") in {"pending", "in_progress"}
            and finish.get("status") == "completed"
            and start.get("args", {}).get("query") == query
            and finish.get("args", {}).get("query") == query
            and finish.get("rawInput", {}).get("query") == query
            and not start.get("error") and not finish.get("error"))


def final_text(messages):
    """Return the final native assistant message, preserving streamed chunks.

    ACP messageId identifies separate public messages where supplied (Vibe).
    Otherwise a native tool-call start delimits pre-tool narration from the final
    response. Every original chunk remains in the wire/event artifacts.
    """
    epoch, groups, order = 0, {}, []
    for message in messages:
        if message.get("method") != "session/update":
            continue
        update = message.get("params", {}).get("update", {})
        kind = update.get("sessionUpdate")
        if kind == "tool_call":
            epoch += 1
        elif kind == "agent_message_chunk":
            block = update.get("content", {})
            if block.get("type") != "text":
                continue
            identifier = update.get("messageId")
            key = ("message", identifier) if identifier is not None else ("tool-epoch", epoch)
            if key not in groups:
                groups[key] = []
                order.append(key)
            elif order[-1] != key:
                order.remove(key)
                order.append(key)
            groups[key].append(block.get("text", ""))
    return "".join(groups[order[-1]]) if order else ""


def execute(plan, directory, timeout, process_started):
    """Run a fresh native server; set-options is session-only, preconfigured is read-only."""
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    policy = plan["acp"]
    transport = directory / "transport.json"
    if transport.exists():
        if json.loads(transport.read_text()) != plan:
            raise ACPError("Recorded ACP transport plan differs from execution plan")
    else:
        transport.write_text(json.dumps(plan, indent=2))
    deadline = time.monotonic() + timeout
    search_tools = set(policy.get("allowed_search_tools", []))
    auxiliary = set(policy.get("allowed_auxiliary_tools", []))
    if auxiliary and (plan.get("backend") != "mistral-vibe" or not search_tools or not auxiliary <= {"search_tool_functions"}):
        raise ACPError("Unsupported ACP auxiliary tool policy")
    allowed = search_tools | auxiliary
    incoming = queue.Queue()
    responses = {}
    sequence = 0
    sid = None
    completed = False
    cleanup = None
    error = None
    received_updates = {}
    turn_messages = []
    with (directory / "acp-wire.jsonl").open("w") as wire, (directory / "events.jsonl").open("wb") as events, (directory / "stderr.log").open("w") as stderr:
        process = subprocess.Popen(plan["command"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=stderr, cwd=directory, env={**os.environ, **plan.get("env", {})},
                                   start_new_session=True)
        process_started(process.pid)
        def reader():
            try:
                for line in process.stdout:
                    incoming.put(line)
            except (OSError, ValueError):
                pass
            finally:
                incoming.put(None)
        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()
        def record(direction, message):
            wire.write(json.dumps({"direction": direction, "message": message}) + "\n")
            wire.flush()
        def send(message):
            record("send", message)
            process.stdin.write((json.dumps(message) + "\n").encode())
            process.stdin.flush()
        def receive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{plan['backend']} ACP attempt exceeded {timeout}s")
            try:
                line = incoming.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f"{plan['backend']} ACP attempt exceeded {timeout}s") from exc
            if line is None:
                raise ACPError("ACP server closed before the requested protocol response")
            events.write(line)
            events.flush()
            try:
                message = json.loads(line)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ACPError("ACP stdout contained malformed JSON; see retained wire") from exc
            record("receive", message)
            if message.get("method") == "session/update":
                params = message.get("params", {})
                if sid and params.get("sessionId") != sid:
                    raise ACPError("Native ACP update belongs to another session")
                update = params.get("update", {})
                kind = update.get("sessionUpdate")
                turn_messages.append(message)
                if kind in {"tool_call", "tool_call_update"}:
                    key = update.get("toolCallId")
                    state = received_updates.setdefault(key, {})
                    state.update(update)
                    if tool_name(state) not in allowed:
                        raise ACPError("Native ACP worker attempted a disallowed tool")
            if "method" in message and "id" in message:
                if message["method"] == "session/request_permission":
                    send({"jsonrpc": "2.0", "id": message["id"], "result": permission_reply(message.get("params", {}), allowed, received_updates)})
                else:
                    send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Client tool capability disabled for isolated role worker"}})
            elif "id" in message:
                responses[message["id"]] = message
            return message
        def rpc(method, params):
            nonlocal sequence
            sequence += 1
            number = sequence
            send({"jsonrpc": "2.0", "id": number, "method": method, "params": params})
            while number not in responses:
                receive()
            response = responses.pop(number)
            if "error" in response:
                raise ACPError(f"{method} failed: {response['error'].get('message', 'native protocol error')}")
            return response.get("result", {})
        try:
            initial = rpc("initialize", {"protocolVersion": 1,
                "clientInfo": {"name": "paper-orchestra", "version": "1"},
                "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}})
            if initial.get("protocolVersion") != 1:
                raise ACPError("ACP server did not negotiate protocol version 1")
            if plan.get("images") and not initial.get("agentCapabilities", {}).get("promptCapabilities", {}).get("image"):
                raise ACPError("ACP server cannot accept all required inline images")
            session = rpc("session/new", {"cwd": str(directory), "mcpServers": []})
            sid = session.get("sessionId")
            if not isinstance(sid, str) or not sid:
                raise ACPError("ACP server supplied no independent session ID")
            configured = options(session)
            if policy.get("config_strategy") == "session-options":
                for key, requested in ((policy.get("model_option", "model"), policy.get("model")),
                                       (policy.get("effort_option", "thought_level"), policy.get("effort"))):
                    if requested is None:
                        continue
                    if key not in configured or requested not in values(configured[key]):
                        raise ACPError(f"Requested {key} {requested!r} is not advertised by this ACP session")
                    result = rpc("session/set_config_option", {"sessionId": sid, "configId": key, "value": requested})
                    configured = options(result)
                    if configured.get(key, {}).get("currentValue") != requested:
                        raise ACPError(f"ACP session did not acknowledge requested {key}")
            for key, requested in ((policy.get("model_option", "model"), policy.get("model")),
                                   (policy.get("effort_option", "thought_level"), policy.get("effort"))):
                if requested is not None and configured.get(key, {}).get("currentValue") != requested:
                    raise ACPError(f"Native ACP {key} differs from selected value {requested!r}")
            if policy.get("expected_mode") is not None and configured.get("mode", {}).get("currentValue") != policy["expected_mode"]:
                raise ACPError("ACP execution mode differs from the isolated role policy")
            content = [{"type": "text", "text": plan["stdin"]}]
            for name in plan.get("images", []):
                path = Path(name)
                data = path.read_bytes()
                mime = mimetypes.guess_type(path.name)[0]
                if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                    raise ACPError(f"Unsupported inline ACP image: {path.name}")
                if policy.get("image_max_bytes") and len(data) > policy["image_max_bytes"]:
                    raise ACPError("ACP image exceeds the backend's documented size limit")
                content.append({"type": "image", "mimeType": mime, "data": base64.b64encode(data).decode("ascii")})
            if policy.get("image_limit") and len(content) - 1 > policy["image_limit"]:
                raise ACPError("ACP attempt exceeds the backend's documented image count limit; no images were omitted")
            result = rpc("session/prompt", {"sessionId": sid, "prompt": content})
            if result.get("stopReason") != "end_turn":
                raise ACPError(f"ACP turn did not complete: {result.get('stopReason')}")
            completed = True
            if initial.get("agentCapabilities", {}).get("sessionCapabilities", {}).get("close") is not None:
                rpc("session/close", {"sessionId": sid})
        except BaseException as exc:
            error = str(exc)
            raise
        finally:
            if process.poll() is None:
                try:
                    process.stdin.close()
                    process.wait(timeout=min(3, max(.1, deadline - time.monotonic())))
                except (subprocess.TimeoutExpired, BrokenPipeError):
                    cleanup = "terminated_after_completed_turn" if completed else "terminated_failed_attempt"
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            reader_thread.join(timeout=.5)
            process.stdout.close()
            if not process.stdin.closed:
                process.stdin.close()
            (directory / "acp-exit.json").write_text(json.dumps({"returncode": process.returncode, "completed_turn": completed,
                                                                 "cleanup": cleanup, "error": error}, indent=2))
    if process.returncode and cleanup != "terminated_after_completed_turn":
        raise ACPError(f"ACP server exited {process.returncode}; inspect native events and stderr")
    response = final_text(turn_messages)
    (directory / "response.txt").write_text(response)
    return response


def inspect(directory, request, backend):
    """Recompute receipts solely from actual wire plus anchored request/plan bytes."""
    directory = Path(directory)
    errors, sessions, images_delivered = [], [], []
    response, observed_model, observed_effort = "", None, None
    searched = False
    try:
        plan_path = directory / "transport.json"
        plan = json.loads(plan_path.read_text())
        policy = plan["acp"]
        if request.get("transport_plan_sha256") != digest(plan_path):
            errors.append("ACP transport plan is not anchored to the request")
        if plan.get("backend") != backend or request.get("backend", backend) != backend:
            errors.append("ACP backend differs from requested backend")
        if request.get("command") is not None and request["command"] != plan.get("command"):
            errors.append("ACP command differs from recorded plan")
        for key in ("model", "effort"):
            if key in request.get("model_routing", {}) and request["model_routing"][key] != policy.get(key):
                errors.append(f"ACP selected {key} differs from request routing")
        records = read_jsonl(directory / "acp-wire.jsonl")
        sends = [(index, row["message"]) for index, row in enumerate(records) if row.get("direction") == "send"]
        receives = [(index, row["message"]) for index, row in enumerate(records) if row.get("direction") == "receive"]
        native = [message for _, message in receives]
        if read_jsonl(directory / "events.jsonl") != native:
            errors.append("Native ACP event file differs from the retained incoming wire")
        # Client requests and server responses share one request-ID namespace.
        # Server permission requests/client answers use the opposite namespace;
        # they may legitimately reuse an ID and must not be folded into this one.
        client_requests = [(index, message) for index, message in sends if "method" in message and "id" in message]
        server_replies = [(index, message) for index, message in receives if "id" in message and "method" not in message]
        request_ids = [message["id"] for _, message in client_requests]
        response_ids = [message["id"] for _, message in server_replies]
        if len(request_ids) != len(set(request_ids)):
            errors.append("ACP wire contains duplicate client request IDs")
        if len(response_ids) != len(set(response_ids)):
            errors.append("ACP wire contains duplicate server responses")
        requests = {message["id"]: (index, message) for index, message in client_requests}
        replies = {message["id"]: (index, message) for index, message in server_replies}
        forbidden = {"session/load", "session/resume", "session/fork"}
        if any(message.get("method") in forbidden for _, message in sends):
            errors.append("ACP worker resumed or forked prior context")
        init = [(message["id"], (index, message)) for index, message in client_requests if message.get("method") == "initialize"]
        fresh = [(message["id"], (index, message)) for index, message in client_requests if message.get("method") == "session/new"]
        prompts = [(message["id"], (index, message)) for index, message in client_requests if message.get("method") == "session/prompt"]
        if len(init) != 1 or len(fresh) != 1 or len(prompts) != 1:
            errors.append("ACP attempt requires exactly one initialize, fresh session, and prompt")
        if not init or not fresh or not prompts:
            raise ACPError("Incomplete native ACP lifecycle")
        init_id, (_, init_message) = init[0]
        new_id, (new_index, new_message) = fresh[0]
        prompt_id, (prompt_index, prompt_message) = prompts[0]
        initial = replies.get(init_id, (0, {}))[1].get("result", {})
        session = replies.get(new_id, (0, {}))[1].get("result", {})
        sid = session.get("sessionId")
        if initial.get("protocolVersion") != 1 or not isinstance(sid, str) or not sid:
            errors.append("ACP protocol/session initialization was not acknowledged")
        else:
            sessions = [sid]
        if new_message.get("params", {}).get("mcpServers") != []:
            errors.append("ACP worker inherited unrequested MCP servers")
        if prompt_message.get("params", {}).get("sessionId") != sid:
            errors.append("ACP prompt does not belong to its fresh session")
        if not (replies.get(init_id, (10**12,))[0] < new_index < replies.get(new_id, (10**12,))[0] < prompt_index):
            errors.append("ACP initialization/session/prompt ordering is invalid")
        configured = options(session)
        changes = [(number, index, message) for number, (index, message) in requests.items()
                   if message.get("method") == "session/set_config_option"]
        if policy.get("config_strategy") == "preconfigured" and changes:
            errors.append("Preconfigured ACP backend mutated session/global configuration")
        configuration_ready = replies.get(new_id, (0, {}))[0]
        for number, index, message in sorted(changes, key=lambda value: value[1]):
            answer_index, answer = replies.get(number, (10**12, {}))
            params = message.get("params", {})
            if not (index < answer_index < prompt_index) or params.get("sessionId") != sid or "error" in answer:
                errors.append("ACP configuration update lacks a before-prompt session acknowledgment")
            update = options(answer.get("result", {}))
            if update.get(params.get("configId"), {}).get("currentValue") != params.get("value"):
                errors.append("ACP configuration acknowledgment differs from requested value")
            configured = update
            configuration_ready = max(configuration_ready, answer_index)
        observed_model = configured.get(policy.get("model_option", "model"), {}).get("currentValue")
        observed_effort = configured.get(policy.get("effort_option", "thought_level"), {}).get("currentValue")
        if policy.get("expected_mode") is not None and configured.get("mode", {}).get("currentValue") != policy["expected_mode"]:
            errors.append("ACP native execution mode differs from its isolated role policy")
        for expected, observed, label in ((policy.get("model"), observed_model, "model"), (policy.get("effort"), observed_effort, "effort")):
            if expected is not None and expected != observed:
                errors.append(f"ACP observed {label} differs from selection")
        content = prompt_message.get("params", {}).get("prompt", [])
        text = "".join(item.get("text", "") for item in content if item.get("type") == "text")
        if text != plan.get("stdin") or (directory / "prompt.txt").exists() and text != (directory / "prompt.txt").read_text():
            errors.append("ACP native prompt differs from the original recorded task")
        expected_paths = request.get("images", plan.get("images", []))
        expected_hashes = request.get("image_sha256", {})
        expected = []
        for name in expected_paths:
            checksum = digest(name)
            if expected_hashes.get(str(name)) != checksum:
                errors.append("Requested ACP image is not anchored or changed")
            expected.append(checksum)
        actual = []
        for item in content:
            if item.get("type") == "image":
                data = base64.b64decode(item.get("data", ""), validate=True)
                actual.append(hashlib.sha256(data).hexdigest())
                if policy.get("image_max_bytes") and len(data) > policy["image_max_bytes"]:
                    errors.append("ACP native image exceeds the backend size limit")
                if item.get("mimeType") not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                    errors.append("ACP native image has unsupported MIME type")
            elif item.get("type") != "text":
                errors.append("Unexpected native ACP prompt content type")
        if Counter(expected) != Counter(actual):
            errors.append("ACP native prompt omitted, replaced, or added an image")
        elif expected and not initial.get("agentCapabilities", {}).get("promptCapabilities", {}).get("image"):
            errors.append("ACP server did not advertise inline image support")
        else:
            images_delivered = list(expected_paths)
        if policy.get("image_limit") and len(actual) > policy["image_limit"]:
            errors.append("ACP image count exceeds native backend limit")
        final_index, final = replies.get(prompt_id, (0, {}))
        if final.get("result", {}).get("stopReason") != "end_turn" or final_index <= prompt_index:
            errors.append("ACP turn has no successful native end_turn result")
        allowed = set(policy.get("allowed_search_tools", []))
        auxiliary = set(policy.get("allowed_auxiliary_tools", []))
        if auxiliary and (backend != "mistral-vibe" or not request.get("search_required") or not auxiliary <= {"search_tool_functions"}):
            errors.append("Unsupported ACP auxiliary tool policy")
        permitted = allowed | auxiliary
        if bool(allowed) != bool(request.get("search_required")):
            errors.append("ACP search tool policy differs from the role request")
        tools = {}
        tool_starts = {}
        tool_completions = {}
        tool_start_metadata = {}
        tool_complete_metadata = {}
        response_messages = []
        for index, message in receives:
            if "error" in message and "id" in message:
                errors.append("ACP server emitted a native protocol/turn error")
            if message.get("method") == "session/update":
                params = message.get("params", {})
                update = params.get("update", {})
                if params.get("sessionId") != sid:
                    errors.append("ACP update belongs to another session")
                kind = update.get("sessionUpdate")
                if prompt_index < index < final_index:
                    response_messages.append(message)
                if kind in {"tool_call", "tool_call_update"}:
                    key = update.get("toolCallId")
                    if not isinstance(key, str) or not key:
                        errors.append("Native ACP tool call has no valid call ID")
                    if not prompt_index < index < final_index:
                        errors.append("Native ACP tool call/result lies outside its prompt turn")
                    if kind == "tool_call":
                        if key in tool_starts:
                            errors.append("Native ACP tool call ID was reused")
                        tool_starts[key] = index
                        tool_start_metadata[key] = dict(update)
                    elif key not in tool_starts:
                        errors.append("Native ACP tool result has no matching call start")
                    state = tools.setdefault(key, {})
                    prior_failure = state.get("_failed", False)
                    state.update(update)
                    raw_failure = isinstance(update.get("rawOutput"), dict) and (
                        bool(update["rawOutput"].get("error")) or update["rawOutput"].get("isError") is True)
                    state["_failed"] = prior_failure or update.get("status") == "failed" or bool(update.get("error")) or raw_failure
                    if update.get("status") == "completed":
                        tool_completions[key] = index
                        tool_complete_metadata[key] = dict(update)
                    if tool_name(state) not in permitted:
                        errors.append("ACP worker invoked a tool outside its isolated role policy")
                # Setter notifications can report an old value while the next
                # setter is pending (observed on AG 1.5.9). Once the final setter
                # is ACKed, later notifications must match pinned values, even
                # if they arrive just before the prompt is sent.
                if kind in {"config_option_update", "config_options_update"} and configuration_ready < index < final_index:
                    changed = options(update)
                    model_key = policy.get("model_option", "model")
                    effort_key = policy.get("effort_option", "thought_level")
                    if model_key in changed:
                        observed_model = changed[model_key].get("currentValue")
                    if effort_key in changed:
                        observed_effort = changed[effort_key].get("currentValue")
                    for key, expected in ((policy.get("model_option", "model"), policy.get("model")),
                                          (policy.get("effort_option", "thought_level"), policy.get("effort"))):
                        if expected is not None and key in changed and changed[key].get("currentValue") != expected:
                            errors.append("Native ACP model/effort changed during the selected turn")
                    if policy.get("expected_mode") is not None and "mode" in changed and changed["mode"].get("currentValue") != policy["expected_mode"]:
                        errors.append("Native ACP mode changed during its isolated role turn")
            if message.get("method") == "session/request_permission":
                answers = [sent for _, sent in sends if sent.get("id") == message.get("id") and "method" not in sent]
                expected_answer = permission_reply(message.get("params", {}), permitted, tools)
                if len(answers) != 1 or answers[0].get("result") != expected_answer:
                    errors.append("ACP permission response does not enforce its search-only policy")
        for key, tool in tools.items():
            output = tool.get("rawOutput") or tool.get("content")
            failed = tool.get("_failed") or tool.get("status") == "failed" or bool(tool.get("error"))
            if isinstance(tool.get("rawOutput"), dict):
                failed = failed or tool["rawOutput"].get("isError") is True or bool(tool["rawOutput"].get("error"))
            matched = (key in tool_starts and key in tool_completions
                       and prompt_index < tool_starts[key] <= tool_completions[key] < final_index)
            native_status = native_search_status(backend, tool_start_metadata.get(key), tool_complete_metadata.get(key))
            if matched and tool_name(tool) in allowed and tool.get("status") == "completed" and (output or native_status) and not failed:
                searched = True
        if request.get("search_required") and not searched:
            errors.append("ACP discovery has no completed native search result")
        response = final_text(response_messages)
        if (directory / "response.txt").exists() and (directory / "response.txt").read_text() != response:
            errors.append("Retained ACP response differs from the final native assistant message")
        exit_state = json.loads((directory / "acp-exit.json").read_text())
        if exit_state.get("error") or exit_state.get("returncode") and exit_state.get("cleanup") != "terminated_after_completed_turn":
            errors.append("ACP process did not terminate after a successful native turn")
    except Exception as exc:
        errors.append(str(exc))
    return {"backend": backend, "sessions": sessions, "completed": not errors, "failed": bool(errors),
            "searched": searched, "response": response, "observed_model": observed_model,
            "observed_effort": observed_effort, "errors": errors, "images_delivered": images_delivered}
