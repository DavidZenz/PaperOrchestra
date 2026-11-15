"""Antigravity CLI ACP transport; no provider API key or built-in orchestration.

Verified local interface: agy 1.5.9, ACP-v1 image/embeddedContext support,
model/thought_level session options. Print-mode stdin is text-only, so all roles
use direct ACP images. Session config acknowledgments are retained on the wire.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import orchestra_acp

AGENT = "paper-orchestra-isolated-worker"
DENY = ["command(*)", "unsandboxed(*)", "write_file(*)", "read_file(*)", "execute_url(*)", "mcp(*)"]


def prepare(selection, prompt, images, search, directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    model, effort = selection.get("model"), selection.get("effort")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("Antigravity model must be a nonempty advertised ACP model ID or null")
    if effort is not None and effort not in {"low", "medium", "high", "xhigh", "extra", "max"}:
        raise ValueError("Unsupported Antigravity reasoning effort")
    tools = ["search_web"] if search else []
    agent_file = directory / ".agents/agents" / (AGENT + ".md")
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    definition = ("---\nname: " + AGENT + "\ndescription: Independent PaperOrchestra role artifact worker\n"
                  "mainAgent: true\nsubagent: false\nmodel: inherit\n"
                  "tools: " + json.dumps(tools) + "\nskills: []\nplugins: []\nmcpServers: []\n---\n"
                  "Execute only the supplied independent role task. Return its exact requested artifact. "
                  "Never delegate, spawn agents, or orchestrate other roles. Use no tools except the "
                  "explicitly exposed live search tool when the task requires discovery.\n")
    agent_file.write_text(definition)
    settings = {"agentMode": "", "toolPermission": "request-review", "permissions": {
        "deny": DENY + ([] if search else ["read_url(*)"]),
        "allow": ["read_url(*)"] if search else []}}
    executable = shutil.which("agy") or "agy"
    command = [executable, "--settings", json.dumps(settings, separators=(",", ":")), "acp",
               "--process-per-session", "--sandbox", "--include-default-customizations=false",
               "--agent", AGENT, "--disable-telemetry", "--log-file", str(directory / "acp-server.log")]
    return {"backend": "antigravity", "mode": "acp", "command": command, "stdin": prompt, "env": {},
            "images": [str(Path(image).resolve()) for image in images],
            "acp": {"config_strategy": "session-options", "model": model, "effort": effort,
                    "model_option": "model", "effort_option": "thought_level", "expected_mode": "default",
                    "allowed_search_tools": tools,
                    "search_evidence": "native matched search_web query/status; result body is not emitted by ACP 1.5.9",
                    "agent_file": str(agent_file), "agent_file_sha256": hashlib.sha256(agent_file.read_bytes()).hexdigest()}}


def execute(plan, directory, timeout, process_started):
    return orchestra_acp.execute(plan, directory, timeout, process_started)


def inspect(directory, request):
    receipt = orchestra_acp.inspect(directory, request, "antigravity")
    try:
        directory = Path(directory).resolve()
        plan = json.loads((directory / "transport.json").read_text())
        policy = plan["acp"]
        agent_file = directory / ".agents/agents" / (AGENT + ".md")
        if hashlib.sha256(agent_file.read_bytes()).hexdigest() != policy.get("agent_file_sha256"):
            receipt["errors"].append("Antigravity isolated worker tool definition changed")
        tools = ["search_web"] if request.get("search_required") else []
        if "tools: " + json.dumps(tools) + "\n" not in agent_file.read_text() or policy.get("allowed_search_tools") != tools:
            receipt["errors"].append("Antigravity scoped agent exposes an incorrect tool list")
        command = plan["command"]
        if "--agent" not in command or command[command.index("--agent") + 1] != AGENT or "--include-default-customizations=false" not in command:
            receipt["errors"].append("Antigravity did not select the isolated role worker")
        settings = json.loads(command[command.index("--settings") + 1])
        denied = settings.get("permissions", {}).get("deny", [])
        if not all(rule in denied for rule in DENY) or not request.get("search_required") and "read_url(*)" not in denied:
            receipt["errors"].append("Antigravity invocation lacks restrictive per-session permissions")
    except Exception as exc:
        receipt["errors"].append(str(exc))
    receipt["failed"] = bool(receipt["errors"])
    receipt["completed"] = not receipt["failed"]
    return receipt
