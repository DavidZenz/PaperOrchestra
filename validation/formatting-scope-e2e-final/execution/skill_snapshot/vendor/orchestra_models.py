"""Explicit model routing for independent Codex role invocations."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

GROUPS = {
    "discovery": ("literature-discovery",),
    "writing": ("outline", "literature-synthesis", "section-writer", "content-editor"),
    "figure_planning": ("figure-retriever", "figure-planner", "figure-stylist"),
    "figure_code": ("ggplot2-visualizer", "tikz-visualizer"),
    "figure_review": ("figure-critic", "figure-captioner"),
    "peer_review": ("peer-reviewer",),
    "meta_review": ("area-chair",),
    "formatting": ("format-reviewer", "format-editor"),
}
ROLE_GROUPS = {role:group for group, roles in GROUPS.items() for role in roles}
ROLES = ("runtime-probe", *ROLE_GROUPS)
LEGACY_EDITOR = "content-or-format-editor"
UPSTREAM_DEFAULT = "gemini-3.1-pro-preview"


def _model(value, label):
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{label} must be a nonempty Codex model ID or null")
    return value


def _mapping(value, label, allowed=None):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    for key, model in value.items():
        if not isinstance(key, str) or not key.strip() or (allowed is not None and key not in allowed):
            raise ValueError(f"Unknown {label} key: {key!r}")
        _model(model, f"{label}.{key}")
    return copy.deepcopy(value)


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError("Model profile must be a JSON object")
    if any(not isinstance(key, str) for key in profile):
        raise ValueError("Model profile field names must be strings")
    extra = set(profile) - {"schema_version", "name", "default", "groups", "roles"}
    if extra:
        raise ValueError(f"Unknown model profile fields: {', '.join(sorted(extra))}")
    if "schema_version" in profile and (type(profile["schema_version"]) is not int or profile["schema_version"] != 1):
        raise ValueError("Model profile schema_version must be 1")
    if "name" in profile and (not isinstance(profile["name"], str) or not profile["name"].strip()):
        raise ValueError("Model profile name must be a nonempty string")
    if "default" in profile:
        _model(profile["default"], "profile.default")
    _mapping(profile.get("groups", {}), "profile groups", set(GROUPS))
    _mapping(profile.get("roles", {}), "profile roles", set(ROLES) | {LEGACY_EDITOR})
    return copy.deepcopy(profile)


def read_profile(path):
    return validate_profile(json.loads(Path(path).read_text()))


def requested_model(role):
    if role == "runtime-probe":
        return "runtime-probe"
    return "gemini-3-flash-preview" if role == "literature-discovery" else UPSTREAM_DEFAULT


class ModelPolicy:
    def __init__(self, *, model=None, model_map=None, profile=None, role_models=None):
        self.model = _model(model, "default model")
        self.model_map = _mapping(model_map if model_map is not None else {}, "upstream models")
        self.profile = validate_profile(profile if profile is not None else {})
        self.role_models = _mapping(role_models if role_models is not None else {},
                                    "role models", set(ROLES) | {LEGACY_EDITOR})

    def resolve(self, role, upstream_model, *, legacy_role=None):
        legacy_role = legacy_role or (LEGACY_EDITOR if role in {"content-editor", "format-editor"} else role)
        group = ROLE_GROUPS.get(role, "writing" if role == LEGACY_EDITOR else None)
        for mapping, label in [(self.role_models, "role override"),
                               (self.profile.get("roles", {}), "profile role")]:
            for key in dict.fromkeys([role, legacy_role]):
                if key in mapping:
                    return {"model":mapping[key], "routing_role":role, "group":group,
                            "selected_by":f"{label}: {key}"}
        if group in self.profile.get("groups", {}):
            return {"model":self.profile["groups"][group], "routing_role":role, "group":group,
                    "selected_by":f"profile group: {group}"}
        if upstream_model in self.model_map:
            return {"model":self.model_map[upstream_model], "routing_role":role, "group":group,
                    "selected_by":f"upstream model map: {upstream_model}"}
        if self.model is not None:
            return {"model":self.model, "routing_role":role, "group":group, "selected_by":"--model fallback"}
        if "default" in self.profile:
            return {"model":self.profile["default"], "routing_role":role, "group":group, "selected_by":"profile default"}
        return {"model":None, "routing_role":role, "group":group, "selected_by":"Codex configured default"}

    def plan(self):
        return [{"role":role, "requested_model":requested_model(role),
                 **self.resolve(role, requested_model(role))} for role in ROLES]

    def snapshot(self):
        return {"schema_version":1, "default_model":self.model,
                "upstream_model_map":self.model_map, "profile":self.profile,
                "role_overrides":self.role_models, "resolved_plan":self.plan()}

    def reusable_profile(self):
        return {"schema_version":1, "name":self.profile.get("name", "resolved-run-models"),
                "roles":{item["role"]:item["model"] for item in self.plan()}}


def audit_model_policy(output, run, trace):
    """Check selected models against recorded argv; old runs explicitly bypass."""
    if "model_policy" not in run:
        return {"enabled":False}, []
    output = Path(output)
    errors = []
    checked = 0
    try:
        recorded = run["model_policy"]
        from orchestra_execution import policy_from_snapshot, configured_default, validate_execution_profile
        from orchestra_transports import validate_invocation_plan
        policy = policy_from_snapshot(recorded)
        if recorded != policy.snapshot():
            raise ValueError("Resolved model plan differs from selected configuration")
        snapshot = output / "execution/model_profile.json"
        if (hashlib.sha256(snapshot.read_bytes()).hexdigest() != run["model_profile_snapshot_sha256"]
                or json.loads(snapshot.read_text()) != policy.reusable_profile()):
            raise ValueError("Reusable model profile snapshot differs from selected configuration")
        if "model_profile_source" in run:
            source = output / "execution/model_profile.source.json"
            if (hashlib.sha256(source.read_bytes()).hexdigest() != run["model_profile_source"]["sha256"]
                    or validate_execution_profile(json.loads(source.read_bytes())) != policy.profile):
                raise ValueError("Original model profile snapshot differs from selected configuration")
        calls = {event["call"]:event for event in trace if event["event"] == "llm_call_start"}
        for event in trace:
            if event["event"] != "agent_start":
                continue
            key = event["invocation"]
            request = json.loads((output / "execution/invocations" / key / "request.json").read_text())
            selection = event.get("model_routing", {})
            route, role = selection.get("routing_role"), event["role"]
            if ((role == LEGACY_EDITOR and route not in {LEGACY_EDITOR, "content-editor", "format-editor"})
                    or (role != LEGACY_EDITOR and route != role)):
                raise ValueError(f"Invalid model routing role: {key}")
            expected = policy.resolve(route, event["requested_model"], legacy_role=role)
            if selection != expected or request.get("model_routing") != expected:
                raise ValueError(f"Invocation model differs from selected role policy: {key}")
            if event.get("call") in calls and calls[event["call"]].get("routing_role") != route:
                raise ValueError(f"Invocation model role differs from its original call: {key}")
            effective = expected["model"] or configured_default(expected.get("backend", "codex"))
            if event.get("effective_model") != effective or request.get("effective_model") != effective:
                raise ValueError(f"Invocation effective model metadata differs: {key}")
            command = event["command"]
            if expected.get("backend", "codex") not in {"codex", "claude-code"}:
                valid = True  # ACP model/effort ACKs and launch plan checked below.
            elif expected["model"] is None:
                valid = "--model" not in command
            else:
                valid = command.count("--model") == 1 and command[command.index("--model") + 1] == expected["model"]
            if not valid:
                raise ValueError(f"Invocation argv does not select the requested model: {key}")
            plan_errors = validate_invocation_plan(output / "execution/invocations" / key, request, command, expected)
            if plan_errors:
                raise ValueError(f"Invocation native execution plan is invalid: {key}: {'; '.join(plan_errors)}")
            checked += 1
    except (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError) as exc:
        errors.append(f"Model policy: {exc}")
    return {"enabled":True, "attempts_checked":checked, "valid":not errors}, errors
