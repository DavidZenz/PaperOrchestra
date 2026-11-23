"""Fresh Mistral Vibe ACP workers with process-local model/thinking settings.

Vibe's ACP model/thinking setters can persist defaults. This adapter deliberately
does not call them: environment overrides configure the new process, then the
shared wire driver checks what the native session actually advertises before it
sends the task. No API key or user configuration file is copied into evidence.

Capability facts for the named Mistral presets were checked on 2026-11-15:
https://docs.mistral.ai/inference/conversations/reasoning
https://docs.mistral.ai/models/mistral-large-4-0
https://docs.mistral.ai/models/mistral-small-4-0-26-03
https://docs.mistral.ai/models/zai-glm-5-3
https://docs.mistral.ai/models/zai-glm-5-3-flash
"""
from __future__ import annotations

import json
from pathlib import Path


BACKEND = "mistral-vibe"
IMAGE_LIMIT = 8
IMAGE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
# Vibe 3.1 filters the connector's published name but reports its canonical
# group.method route in ACP metadata. The tool-catalog lookup is separate from
# actual live search and can never satisfy discovery's search requirement.
SEARCH_FILTER_NAMES = ("web_search", "connector_web_search_web_search")
SEARCH_EVENT_NAMES = ("web_search", "connector_web_search.web_search")
AUXILIARY_EVENT_NAMES = ("search_tool_functions",)
KNOWN_MODELS = {
    "mistral-large-4": ("low", "medium", "high"),
    "mistral-large-4-0": ("low", "medium", "high"),
    "mistral-small-2603": ("off", "high"),
    "zai-glm-5-3": ("low", "high", "max"),
    "zai-glm-5-3-flash": ("low", "high", "max"),
}
IMAGE_MODELS = frozenset(KNOWN_MODELS) - {"zai-glm-5-3"}


def prepare(selection, prompt, images, search, directory):
    """Build one native ACP process plan; never start or resume a session here."""
    directory = Path(directory).resolve()
    model, effort = selection.get("model"), selection.get("effort")
    if selection.get("backend", BACKEND) != BACKEND:
        raise ValueError("Mistral Vibe adapter received a different backend")
    if effort is not None and model is None:
        raise ValueError(
            "Mistral Vibe needs an explicit model/alias when setting effort; "
            "its ACP thinking setter can change user defaults"
        )
    if model in KNOWN_MODELS and effort is not None and effort not in KNOWN_MODELS[model]:
        raise ValueError(
            f"Mistral Vibe {model} supports thinking {', '.join(KNOWN_MODELS[model])}; "
            f"requested {effort!r}"
        )
    resolved_images = [str(Path(path).resolve()) for path in images]
    if len(resolved_images) > IMAGE_LIMIT:
        raise ValueError(
            f"Mistral Vibe 3.1 ACP accepts at most {IMAGE_LIMIT} images per prompt; "
            f"this invocation has {len(resolved_images)}. No pages were truncated."
        )
    for name in resolved_images:
        path = Path(name)
        if path.suffix.lower() not in IMAGE_TYPES:
            raise ValueError(f"Unsupported Mistral Vibe image type: {path.suffix}")
        if path.stat().st_size > IMAGE_MAX_BYTES:
            raise ValueError(f"Mistral Vibe image exceeds the native 10 MiB limit: {path.name}")
    if resolved_images and model == "zai-glm-5-3":
        raise ValueError(
            "Mistral-hosted zai-glm-5-3 is text-only; this role requires images. "
            "Choose the multimodal zai-glm-5-3-flash or another supported image model. "
            "No vision-helper model was substituted."
        )
    if resolved_images and model not in IMAGE_MODELS:
        # Vibe can otherwise call a different vision model to describe images.
        # That would silently substitute the selected role's model/input path.
        raise ValueError(
            "Direct-image Mistral Vibe workers require an explicit supported "
            "multimodal model: mistral-large-4, mistral-large-4-0, mistral-small-2603 "
            "or zai-glm-5-3-flash. "
            "Unknown/default aliases are not silently routed through a vision helper."
        )

    env = {
        "VIBE_DEFAULT_AGENT": "ask",
        "VIBE_ENABLED_AGENTS": json.dumps(["ask"]),
        "VIBE_ENABLE_SUBAGENTS": "false",
        "VIBE_ENABLE_MCP": "false",
        "VIBE_ENABLE_CONNECTORS": "true" if search else "false",
        "VIBE_ENABLED_TOOLS": json.dumps(list(SEARCH_FILTER_NAMES) if search else []),
        "VIBE_DISABLED_TOOLS": json.dumps([] if search else ["*"]),
        "VIBE_DISABLED_SKILLS": json.dumps(["*"]),
        "VIBE_INCLUDE_PROJECT_CONTEXT": "false",
        "VIBE_OUTSIDE_WORKDIR": "deny",
        "VIBE_SESSION_LOGGING__ENABLED": "false",
        "VIBE_SESSION_LOGGING__GENERATE_TITLES": "false",
        "VIBE_ENABLE_UPDATE_CHECKS": "false",
        "VIBE_ENABLE_NOTIFICATIONS": "false",
        "VIBE_ENABLE_TELEMETRY": "false",
        "VIBE_EXPERIMENTS__ENABLE": "false",
        "VIBE_OUTPUT_LIMIT_RETRIES": "0",
    }
    if search:
        env["VIBE_CONNECTORS"] = json.dumps([
            {"name":"web_search", "disabled":False, "disabled_tools":[]}
        ])
    if model is not None:
        env["VIBE_ACTIVE_MODEL"] = model
        preset = {}
        if model in KNOWN_MODELS:
            preset.update(name=model, provider="mistral", alias=model,
                          supports_images=model in IMAGE_MODELS,
                          thinking_levels=list(KNOWN_MODELS[model]))
        if effort is not None:
            preset["thinking"] = effort
        if preset:
            # Vibe deep-merges alias-keyed model settings. For unknown aliases,
            # a sparse thinking entry preserves the user's provider and model.
            env["VIBE_MODELS"] = json.dumps({model:preset}, sort_keys=True)
    return {
        "backend": BACKEND,
        "mode": "acp",
        "command": ["vibe-acp"],
        "stdin": prompt,
        "env": env,
        "images": resolved_images,
        "acp": {
            "config_strategy": "preconfigured",
            "model": model,
            "effort": effort,
            "model_option": "model",
            "effort_option": "thinking",
            "allowed_search_tools": list(SEARCH_EVENT_NAMES) if search else [],
            "allowed_auxiliary_tools": list(AUXILIARY_EVENT_NAMES) if search else [],
            "image_limit": IMAGE_LIMIT,
            "image_max_bytes": IMAGE_MAX_BYTES,
        },
    }


def execute(plan, directory, timeout, process_started):
    from orchestra_acp import execute as execute_acp
    return execute_acp(plan, Path(directory), timeout, process_started)


def inspect(directory, request):
    from orchestra_acp import inspect as inspect_acp
    return inspect_acp(Path(directory), request, backend=BACKEND)
