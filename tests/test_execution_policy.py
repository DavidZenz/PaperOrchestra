"""Mixed native-runtime/effort policy tests; no inference or external tools."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper-orchestra/vendor"))
from orchestra_models import ModelPolicy, validate_profile, ROLES
from orchestra_execution import execution_policy, validate_execution_profile


class ExecutionPolicyTests(unittest.TestCase):
    def test_legacy_factory_preserves_exact_class_snapshot_resolve_and_reusable_shape(self):
        config = {"model": "legacy-global", "model_map": {"upstream": "legacy-map"},
                  "profile": {"schema_version": 1, "groups": {"writing": "legacy-writer"},
                              "roles": {"peer-reviewer": None}},
                  "role_models": {"format-editor": "legacy-formatter"}}
        expected = ModelPolicy(**config)
        actual = execution_policy(**config)
        self.assertIs(type(actual), ModelPolicy)
        self.assertEqual(actual.snapshot(), expected.snapshot())
        self.assertEqual(actual.reusable_profile(), expected.reusable_profile())
        for role in ROLES:
            self.assertEqual(actual.resolve(role, "upstream"), expected.resolve(role, "upstream"))

    def test_legacy_profile_validation_remains_exact(self):
        profile = {"schema_version": 1, "default": None, "roles": {"outline": "opaque-model-id"}}
        self.assertEqual(validate_execution_profile(profile), validate_profile(profile))

    def test_v2_role_effort_inherits_group_model_and_backend(self):
        profile = {"schema_version": 2,
                   "default": {"backend": "codex", "model": "default-model", "effort": "low"},
                   "groups": {"writing": {"model": "writer-model", "effort": "medium"}},
                   "roles": {"outline": {"effort": "high"}}}
        result = execution_policy(profile=profile).resolve("outline", "upstream")
        self.assertEqual((result["backend"], result["model"], result["effort"]), ("codex", "writer-model", "high"))

    def test_explicit_role_override_can_change_effort_without_replacing_inherited_model(self):
        policy = execution_policy(profile={"schema_version": 2, "groups": {"peer_review": {"model": "review-model", "effort": "medium"}}},
                                  role_models={"peer-reviewer": {"effort": "low"}})
        selection = policy.resolve("peer-reviewer", "upstream")
        self.assertEqual(selection["model"], "review-model")
        self.assertEqual(selection["effort"], "low")

    def test_model_null_resets_only_model_while_effort_and_backend_inherit(self):
        policy = execution_policy(model="global-model", effort="high", profile={"schema_version": 2,
            "groups": {"writing": {"model": "group-model"}}, "roles": {"outline": {"model": None}}})
        result = policy.resolve("outline", "upstream")
        self.assertIsNone(result["model"])
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["backend"], "codex")

    def test_effort_null_resets_only_effort_while_model_inherits(self):
        policy = execution_policy(model="global-model", effort="high", profile={"schema_version": 2,
            "roles": {"outline": {"effort": None}}})
        result = policy.resolve("outline", "upstream")
        self.assertEqual(result["model"], "global-model")
        self.assertIsNone(result["effort"])

    def test_scalar_model_values_do_not_guess_a_backend_from_model_names(self):
        policy = execution_policy(profile={"schema_version": 2, "roles": {"outline": "claude-labelled-model-fixture"}})
        result = policy.resolve("outline", "upstream")
        self.assertEqual(result["backend"], "codex")
        self.assertEqual(result["model"], "claude-labelled-model-fixture")

    def test_explicit_backend_switch_with_model_and_effort_resets_is_supported(self):
        profile = {"schema_version": 2,
                   "default": {"backend": "codex", "model": "old-model", "effort": "high"},
                   "roles": {"outline": {"backend": "mistral-vibe", "model": None, "effort": None}}}
        result = execution_policy(profile=profile).resolve("outline", "upstream")
        self.assertEqual(result["backend"], "mistral-vibe")
        self.assertIsNone(result["model"])
        self.assertIsNone(result["effort"])

    def test_backend_switch_cannot_leak_foreign_inherited_model_or_effort(self):
        for override in [{"backend": "claude-code"}, {"backend": "claude-code", "model": "new-model"},
                         {"backend": "claude-code", "effort": None}]:
            with self.subTest(override=override), self.assertRaises(ValueError):
                policy = execution_policy(profile={"schema_version": 2,
                    "default": {"backend": "codex", "model": "old-model", "effort": "high"},
                    "roles": {"outline": override}})
                policy.resolve("outline", "upstream")

    def test_legacy_model_map_and_global_model_precedence_survive_partial_effort_overrides(self):
        config = {"profile": {"schema_version": 2,
                              "default": {"model": "profile-default", "effort": "low"},
                              "roles": {"outline": {"effort": "high"}}},
                  "model": "global-model", "model_map": {"u": "mapped-model"}}
        policy = execution_policy(**config)
        self.assertEqual(policy.resolve("outline", "u")["model"], "mapped-model")
        self.assertEqual(policy.resolve("outline", "other")["model"], "global-model")
        self.assertEqual(policy.resolve("outline", "u")["effort"], "high")

    def test_legacy_editor_override_still_applies_to_canonical_content_and_format_roles(self):
        policy = execution_policy(profile={"schema_version": 2,
            "roles": {"content-or-format-editor": {"model": "shared-model", "effort": "medium"}}})
        for role in ["content-editor", "format-editor"]:
            with self.subTest(role=role):
                result = policy.resolve(role, "u")
                self.assertEqual(result["model"], "shared-model")
                self.assertEqual(result["effort"], "medium")

    def test_v2_reusable_snapshot_roundtrips_resolved_triplets_for_every_role(self):
        profile = {"schema_version": 2, "name": "mixed fixture",
                   "default": {"backend": "codex", "model": "codex-fixture", "effort": "high"},
                   "groups": {"figure_code": {"backend": "claude-code", "model": "claude-fixture", "effort": "medium"}},
                   "roles": {"area-chair": {"backend": "mistral-vibe", "model": "vibe-fixture", "effort": None}}}
        policy = execution_policy(profile=profile)
        flat = policy.reusable_profile()
        self.assertEqual(flat["schema_version"], 2)
        self.assertEqual(set(flat["roles"]), set(ROLES))
        restored = execution_policy(profile=flat)
        for role in ROLES:
            a, b = policy.resolve(role, "u"), restored.resolve(role, "u")
            self.assertEqual({k:a[k] for k in ["backend", "model", "effort"]}, {k:b[k] for k in ["backend", "model", "effort"]})
        self.assertEqual(policy.snapshot()["schema_version"], 2)
        self.assertIn("default_backend", policy.snapshot())
        self.assertIn("default_effort", policy.snapshot())

    def test_input_mutation_does_not_change_mixed_policy(self):
        profile = {"schema_version": 2, "roles": {"outline": {"model": "original", "effort": "high"}}}
        policy = execution_policy(profile=profile)
        expected = copy.deepcopy(policy.resolve("outline", "u"))
        profile["roles"]["outline"]["model"] = "modified"
        self.assertEqual(policy.resolve("outline", "u"), expected)

    def test_global_backend_and_effort_can_extend_unchanged_v1_profile(self):
        policy = execution_policy(backend="claude-code", effort="high",
                                  profile={"schema_version": 1, "groups": {"writing": "claude-fixture"}})
        result = policy.resolve("section-writer", "upstream")
        self.assertEqual((result["backend"], result["model"], result["effort"]),
                         ("claude-code", "claude-fixture", "high"))
        self.assertEqual(policy.snapshot()["profile"]["schema_version"], 1)

    def test_structured_upstream_map_overrides_per_field_before_role_settings(self):
        policy = execution_policy(model="fallback", effort="low",
                                  model_map={"u": {"backend": "claude-code", "model": "claude-fixture", "effort": "medium"}},
                                  role_models={"outline": {"effort": "high"}})
        result = policy.resolve("outline", "u")
        self.assertEqual((result["backend"], result["model"], result["effort"]),
                         ("claude-code", "claude-fixture", "high"))
        self.assertEqual(result["execution_selected_by"],
                         {"backend": "upstream model map: u", "model": "upstream model map: u", "effort": "role override: outline"})

    def test_backend_reset_is_explicit_codex_with_model_and_effort_resets(self):
        policy = execution_policy(profile={"schema_version": 2,
            "default": {"backend": "claude-code", "model": "claude-fixture", "effort": "high"},
            "roles": {"outline": {"backend": "codex", "model": None, "effort": None}}})
        result = policy.resolve("outline", "u")
        self.assertEqual((result["backend"], result["model"], result["effort"]), ("codex", None, None))

    def test_explicit_global_codex_overrides_profile_default_but_omitted_backend_inherits(self):
        profile = {"schema_version": 2,
                   "default": {"backend": "claude-code", "model": None, "effort": None}}
        inherited = execution_policy(profile=profile)
        reset = execution_policy(profile=profile, backend="codex")
        self.assertEqual(inherited.resolve("outline", "u")["backend"], "claude-code")
        self.assertEqual(reset.resolve("outline", "u")["backend"], "codex")
        self.assertIsNone(inherited.snapshot()["default_backend"])
        self.assertEqual(reset.snapshot()["default_backend"], "codex")

    def test_unsupported_effort_is_rejected_without_cross_provider_mapping(self):
        with self.assertRaisesRegex(ValueError, "no cross-provider mapping"):
            execution_policy(profile={"schema_version": 2,
                "default": {"backend": "codex", "model": None, "effort": "off"}})

    def test_unknown_backends_effort_types_and_properties_are_rejected(self):
        invalid = [
            {"schema_version": 2, "roles": {"outline": {"backend": "unknown"}}},
            {"schema_version": 2, "roles": {"outline": {"backend": None}}},
            {"schema_version": 2, "roles": {"outline": {"effort": 5}}},
            {"schema_version": 2, "roles": {"outline": {"effort": ""}}},
            {"schema_version": 2, "roles": {"outline": {"model": []}}},
            {"schema_version": 2, "roles": {"outline": {"unexpected": "x"}}},
            {"schema_version": 2, "roles": {"unknown-role": {"model": "x"}}},
            {"schema_version": 2, "groups": {"unknown-group": {"effort": "high"}}},
            {"schema_version": True},
        ]
        for profile in invalid:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                validate_execution_profile(profile)


class ExecutionPolicyCLITests(unittest.TestCase):
    """The selection preview must work before tools, credentials, or materials."""

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "paper-orchestra/scripts/run.py"), *args],
                              env={**os.environ, "PATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
                              capture_output=True, text=True, timeout=20)

    def test_mixed_backend_effort_preview_requires_no_tools_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "labelled-execution-profile.json"
            profile.write_text(json.dumps({"schema_version": 2, "groups": {
                "peer_review": {"backend": "claude-code", "model": "claude-labelled-fixture", "effort": "high"},
                "meta_review": {"backend": "antigravity", "model": "labelled-native-model", "effort": "low"}}}))
            result = self.cli("--show-model-plan", "--model-profile", str(profile))
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["model_calls"], 0)
            plan = {entry["role"]: entry for entry in output["model_policy"]["resolved_plan"]}
            self.assertEqual((plan["peer-reviewer"]["backend"], plan["peer-reviewer"]["model"], plan["peer-reviewer"]["effort"]),
                             ("claude-code", "claude-labelled-fixture", "high"))
            self.assertEqual(plan["area-chair"]["backend"], "antigravity")
            self.assertEqual(plan["section-writer"]["backend"], "codex")
            self.assertEqual(set(Path(directory).iterdir()), {profile})

    def test_incomplete_backend_switch_is_rejected_before_any_tool_probe(self):
        result = self.cli("--show-model-plan", "--role-models-json", '{"peer-reviewer":{"backend":"claude-code","model":"fixture"}}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changing backend requires explicit model and effort", result.stderr)
        self.assertNotIn("Missing required", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
