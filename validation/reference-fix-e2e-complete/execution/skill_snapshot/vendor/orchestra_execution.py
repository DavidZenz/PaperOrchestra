"""Backend and native-effort choices, keeping the original model policy compatible."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from orchestra_models import GROUPS, ROLE_GROUPS, ROLES, LEGACY_EDITOR, ModelPolicy, requested_model, validate_profile

BACKENDS = ("codex", "claude-code", "antigravity", "mistral-vibe")
EFFORTS = {
    "codex": {"minimal", "low", "medium", "high", "xhigh", "max"},
    "claude-code": {"low", "medium", "high", "xhigh", "max"},
    "antigravity": {"low", "medium", "high", "xhigh", "max"},
    "mistral-vibe": {"off", "low", "medium", "high", "xhigh", "max"},
}


def _target(value, label):
    if not isinstance(value, dict):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{label} must be a model ID, null, or a backend/model/effort object")
        return {"model":value}
    if not value or set(value) - {"backend", "model", "effort"}:
        raise ValueError(f"{label} has unknown or empty execution settings")
    if "backend" in value and value["backend"] not in BACKENDS:
        raise ValueError(f"{label}.backend must be one of {BACKENDS}")
    for key in ("model", "effort"):
        if key in value and value[key] is not None and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError(f"{label}.{key} must be a nonempty string or null")
    return copy.deepcopy(value)


def _targets(mapping, label, allowed=None):
    if not isinstance(mapping, dict):
        raise ValueError(f"{label} must be a JSON object")
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip() or (allowed is not None and key not in allowed):
            raise ValueError(f"Unknown {label} key: {key!r}")
        _target(value, f"{label}.{key}")
    return copy.deepcopy(mapping)


def validate_execution_profile(profile):
    if not isinstance(profile, dict) or profile.get("schema_version", 1) != 2:
        return validate_profile(profile)
    if type(profile["schema_version"]) is not int:
        raise ValueError("Execution profile schema_version must be 2")
    if set(profile) - {"schema_version", "name", "default", "groups", "roles"}:
        raise ValueError("Unknown execution profile fields")
    if "name" in profile and (not isinstance(profile["name"], str) or not profile["name"].strip()):
        raise ValueError("Execution profile name must be a nonempty string")
    if "default" in profile:
        _target(profile["default"], "profile.default")
    _targets(profile.get("groups", {}), "profile groups", set(GROUPS))
    _targets(profile.get("roles", {}), "profile roles", set(ROLES) | {LEGACY_EDITOR})
    return copy.deepcopy(profile)


class ExecutionPolicy:
    def __init__(self, *, model=None, model_map=None, profile=None, role_models=None, backend=None, effort=None):
        self.model = _target(model, "default model")["model"]
        self.backend = backend
        self.effort = effort
        _target({"backend":self.backend or "codex", "effort":effort}, "execution defaults")
        self.model_map = _targets(model_map if model_map is not None else {}, "upstream models")
        self.profile = validate_execution_profile(profile if profile is not None else {})
        self.role_models = _targets(role_models if role_models is not None else {}, "role models", set(ROLES) | {LEGACY_EDITOR})
        # Validate all effective targets before any process or paid probe.
        self.plan()

    def resolve(self, role, upstream_model, *, legacy_role=None):
        legacy = legacy_role or (LEGACY_EDITOR if role in {"content-editor", "format-editor"} else role)
        group = ROLE_GROUPS.get(role, "writing" if role == LEGACY_EDITOR else None)
        result = {"backend":"codex", "model":None, "effort":None}
        reasons = {key:"runtime configured default" for key in result}

        def apply(value, reason):
            target = _target(value, reason)
            if "backend" in target and target["backend"] != result["backend"]:
                if "model" not in target or "effort" not in target:
                    raise ValueError(f"{reason}: changing backend requires explicit model and effort (null selects native default)")
            for key, setting in target.items():
                result[key], reasons[key] = setting, reason

        if "default" in self.profile:
            apply(self.profile["default"], "profile default")
        if self.backend is not None:
            # CLI backend sets an explicit execution fallback, not a provider guess.
            result["backend"], reasons["backend"] = self.backend, "--backend fallback"
        if self.effort is not None:
            result["effort"], reasons["effort"] = self.effort, "--effort fallback"
        if self.model is not None:
            apply(self.model, "--model fallback")
        if upstream_model in self.model_map:
            apply(self.model_map[upstream_model], f"upstream model map: {upstream_model}")
        if group in self.profile.get("groups", {}):
            apply(self.profile["groups"][group], f"profile group: {group}")
        for mapping, label in ((self.profile.get("roles", {}), "profile role"), (self.role_models, "role override")):
            key = next((key for key in dict.fromkeys((role, legacy)) if key in mapping), None)
            if key is not None:
                apply(mapping[key], f"{label}: {key}")
        if result["effort"] is not None and result["effort"] not in EFFORTS[result["backend"]]:
            raise ValueError(f"Unsupported native effort {result['effort']!r} for {result['backend']}; no cross-provider mapping is performed")
        if result["backend"] == "mistral-vibe":
            from orchestra_vibe import KNOWN_MODELS
            if result["effort"] is not None and result["model"] is None:
                raise ValueError("Mistral Vibe requires an explicit model when selecting native effort")
            if (result["model"] in KNOWN_MODELS and result["effort"] is not None
                    and result["effort"] not in KNOWN_MODELS[result["model"]]):
                raise ValueError(f"Unsupported Mistral Vibe effort for {result['model']}; supported: {KNOWN_MODELS[result['model']]}")
        return {"model":result["model"], "routing_role":role, "group":group,
                "selected_by":reasons["model"], "backend":result["backend"],
                "effort":result["effort"], "execution_selected_by":reasons}

    def plan(self):
        return [{"role":role, "requested_model":requested_model(role), **self.resolve(role, requested_model(role))} for role in ROLES]

    def snapshot(self):
        return {"schema_version":2, "default_model":self.model, "default_backend":self.backend,
                "default_effort":self.effort, "upstream_model_map":copy.deepcopy(self.model_map),
                "profile":copy.deepcopy(self.profile), "role_overrides":copy.deepcopy(self.role_models),
                "resolved_plan":self.plan()}

    def reusable_profile(self):
        return {"schema_version":2, "name":self.profile.get("name", "resolved-run-execution"),
                "roles":{entry["role"]:{key:entry[key] for key in ("backend", "model", "effort")} for entry in self.plan()}}


def execution_policy(*, model=None, model_map=None, profile=None, role_models=None, backend=None, effort=None):
    profile = validate_execution_profile(profile if profile is not None else {})
    structured = any(isinstance(v, dict) for mapping in (model_map or {}, role_models or {}) for v in mapping.values())
    if backend is None and effort is None and profile.get("schema_version", 1) == 1 and not structured:
        return ModelPolicy(model=model, model_map=model_map, profile=profile, role_models=role_models)
    return ExecutionPolicy(model=model, model_map=model_map, profile=profile, role_models=role_models, backend=backend, effort=effort)


def policy_from_snapshot(recorded):
    return execution_policy(model=recorded["default_model"], model_map=recorded["upstream_model_map"],
                            profile=recorded["profile"], role_models=recorded["role_overrides"],
                            backend=recorded.get("default_backend"), effort=recorded.get("default_effort"))


def configured_default(backend):
    return {"codex":"Codex", "claude-code":"Claude Code", "antigravity":"Antigravity", "mistral-vibe":"Mistral Vibe"}[backend] + " configured default"
