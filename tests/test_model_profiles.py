"""Model-selection tests with labelled response fixtures; no real model calls."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "paper-orchestra"
sys.path.insert(0, str(SKILL / "vendor"))
from orchestra_models import ModelPolicy, GROUPS, ROLES, validate_profile, read_profile, audit_model_policy
import orchestra_runtime as runtime_module
from orchestra_runtime import Runtime, configure, role_override
from utils.gemini_utils import call_gemini_with_contents
from methods.agents import content_refinement_agent as refinement_module


class PolicyTests(unittest.TestCase):
    def test_explicit_canonical_role_has_highest_precedence(self):
        policy = ModelPolicy(model="global-fixture", model_map={"upstream": "map-fixture"},
            profile={"default": "default-fixture", "groups": {"writing": "group-fixture"},
                     "roles": {"content-editor": "profile-role", "content-or-format-editor": "profile-legacy"}},
            role_models={"content-editor": "explicit-role", "content-or-format-editor": "explicit-legacy"})
        result = policy.resolve("content-editor", "upstream")
        self.assertEqual(result["model"], "explicit-role")
        self.assertEqual(result["routing_role"], "content-editor")
        self.assertEqual(result["group"], "writing")
        self.assertEqual(result["selected_by"], "role override: content-editor")

    def test_explicit_legacy_role_wins_over_profile_canonical_role(self):
        policy = ModelPolicy(profile={"roles": {"format-editor": "profile-format"}},
                             role_models={"content-or-format-editor": "explicit-shared"})
        self.assertEqual(policy.resolve("format-editor", "upstream")["model"], "explicit-shared")

    def test_profile_role_then_group_then_upstream_map_then_global_then_default(self):
        cases = [
            ({"roles": {"section-writer": "role"}, "groups": {"writing": "group"}, "default": "default"}, {"u": "mapped"}, "global", "role"),
            ({"groups": {"writing": "group"}, "default": "default"}, {"u": "mapped"}, "global", "group"),
            ({"default": "default"}, {"u": "mapped"}, "global", "mapped"),
            ({"default": "default"}, {}, "global", "global"),
            ({"default": "default"}, {}, None, "default"),
            ({}, {}, None, None),
        ]
        for profile, mapping, global_model, expected in cases:
            with self.subTest(expected=expected):
                policy = ModelPolicy(profile=profile, model_map=mapping, model=global_model)
                self.assertEqual(policy.resolve("section-writer", "u")["model"], expected)

    def test_null_at_role_group_or_map_explicitly_resets_lower_priority_models(self):
        cases = [
            {"role_models": {"section-writer": None}, "profile": {"roles": {"section-writer": "profile-role"}}},
            {"profile": {"roles": {"section-writer": None}, "groups": {"writing": "group"}}},
            {"profile": {"groups": {"writing": None}}, "model_map": {"u": "map"}},
            {"model_map": {"u": None}, "profile": {"default": "profile-default"}},
        ]
        for options in cases:
            with self.subTest(options=options):
                self.assertIsNone(ModelPolicy(model="global", **options).resolve("section-writer", "u")["model"])

    def test_omitted_entry_inherits_but_null_profile_default_means_codex_default(self):
        self.assertEqual(ModelPolicy(profile={"groups": {"writing": "group"}, "roles": {}}).resolve("outline", "u")["model"], "group")
        self.assertIsNone(ModelPolicy(profile={"default": None}).resolve("outline", "u")["model"])

    def test_canonical_editor_roles_have_distinct_groups_and_legacy_fallback(self):
        policy = ModelPolicy(profile={"groups": {"writing": "writer", "formatting": "formatter"}})
        self.assertEqual(policy.resolve("content-editor", "u")["model"], "writer")
        self.assertEqual(policy.resolve("format-editor", "u")["model"], "formatter")
        legacy = ModelPolicy(profile={"roles": {"content-or-format-editor": "shared"}})
        self.assertEqual(legacy.resolve("content-editor", "u")["model"], "shared")
        self.assertEqual(legacy.resolve("format-editor", "u")["model"], "shared")

    def test_probe_is_independently_selectable_and_plan_covers_every_role_once(self):
        policy = ModelPolicy(profile={"roles": {"runtime-probe": "probe-fixture"}})
        plan = policy.plan()
        self.assertEqual(len({entry["role"] for entry in plan}), len(ROLES))
        self.assertEqual({entry["role"] for entry in plan}, set(ROLES))
        probe = next(entry for entry in plan if entry["role"] == "runtime-probe")
        self.assertEqual(probe["model"], "probe-fixture")
        self.assertIsNone(probe["group"])
        self.assertEqual(len(GROUPS), 8)

    def test_reusable_flat_profile_preserves_all_resolved_choices_including_null(self):
        original = ModelPolicy(model="fallback", profile={"name": "fixture plan", "groups": {"figure_code": "code"}},
                               role_models={"peer-reviewer": None, "content-editor": "content"})
        reusable = original.reusable_profile()
        restored = ModelPolicy(profile=reusable)
        self.assertEqual(reusable["name"], "fixture plan")
        self.assertEqual({x["role"]: x["model"] for x in restored.plan()}, {x["role"]: x["model"] for x in original.plan()})
        self.assertIn("peer-reviewer", reusable["roles"])
        self.assertIsNone(reusable["roles"]["peer-reviewer"])

    def test_caller_mutation_of_profile_or_overrides_does_not_change_policy(self):
        profile = {"groups": {"writing": "original"}}
        overrides = {"peer-reviewer": "review-original"}
        mapping = {"u": "upstream-original"}
        policy = ModelPolicy(profile=profile, role_models=overrides, model_map=mapping)
        profile["groups"]["writing"] = "changed"
        overrides["peer-reviewer"] = "changed"
        mapping["u"] = "changed"
        self.assertEqual(policy.resolve("section-writer", "u")["model"], "original")
        self.assertEqual(policy.resolve("peer-reviewer", "u")["model"], "review-original")
        self.assertEqual(policy.resolve("area-chair", "u")["model"], "upstream-original")

    def test_invalid_unknown_keys_and_wrong_types_are_rejected(self):
        invalid = [[], None, {"extra": "x"}, {"schema_version": True}, {"schema_version": 2},
                   {"name": ""}, {"default": " "}, {"default": False},
                   {"roles": []}, {"roles": {"made-up-role": "x"}},
                   {"groups": {"made-up-group": "x"}}, {"groups": {"writing": 3}},
                   {"roles": {"outline": ["model"]}}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_profile(value)
        for kwargs in [{"model": 3}, {"model_map": []}, {"role_models": {"unknown": "x"}},
                       {"role_models": {"outline": ""}}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ModelPolicy(**kwargs)

    def test_profile_file_load_validates_without_changing_its_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            text = '{"schema_version":1,"roles":{"outline":null}}\n'
            path.write_text(text)
            self.assertEqual(read_profile(path), {"schema_version": 1, "roles": {"outline": None}})
            self.assertEqual(path.read_text(), text)


class RuntimeModelTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        previous = runtime_module._runtime
        self.stack.callback(configure, previous)
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(redirect_stderr(io.StringIO()))

    def test_each_role_gets_its_own_model_argument_fresh_invocation_and_same_parsed_handoff(self):
        seen = []
        fixture = {"labelled_response_fixture": True, "payload": [1, 2, 3]}
        def executor(command, prompt, directory):
            seen.append((command, directory, json.loads((directory / "request.json").read_text())))
            return json.dumps(fixture)
        runtime = Runtime(self.root, executor=executor,
                          model_profile={"groups": {"writing": "writing-fixture", "figure_code": "code-fixture"}},
                          role_models={"ggplot2-visualizer": "r-fixture", "peer-reviewer": None})
        configure(runtime)
        roles = ["outline", "tikz-visualizer", "ggplot2-visualizer", "peer-reviewer"]
        expected = ["writing-fixture", "code-fixture", "r-fixture", None]
        for role in roles:
            token = role_override.set(role)
            try:
                result = call_gemini_with_contents(["LABELLED INPUT FIXTURE"], "upstream-fixture")
            finally:
                role_override.reset(token)
            self.assertEqual(result["parsed_response"], fixture)
        self.assertEqual(len({directory for command, directory, request in seen}), 4)
        for (command, directory, request), role, model in zip(seen, roles, expected):
            self.assertIn("--ephemeral", command)
            self.assertNotIn("resume", command)
            self.assertNotIn("fork", command)
            self.assertEqual(request["model_routing"]["routing_role"], role)
            self.assertEqual(request["model_routing"]["model"], model)
            self.assertEqual(json.loads((directory / "response.txt").read_text()), fixture)
            if model is None:
                self.assertNotIn("--model", command)
            else:
                self.assertEqual(command[command.index("--model") + 1], model)
        parsed = [json.loads(p.read_text()) for p in (self.root / "parsed").glob("*.json")]
        self.assertEqual(parsed, [fixture] * 4)

    def test_original_five_attempt_retry_retains_selected_model_and_role(self):
        seen = []
        def executor(command, prompt, directory):
            seen.append((command, directory, json.loads((directory / "request.json").read_text())))
            return "LABELLED INVALID JSON FIXTURE"
        configure(Runtime(self.root, executor=executor, role_models={"peer-reviewer": "stable-review-fixture"}))
        token = role_override.set("peer-reviewer")
        try:
            with patch("utils.gemini_utils.time.sleep"):
                with self.assertRaises(AssertionError):
                    call_gemini_with_contents(["fixture"], "upstream")
        finally:
            role_override.reset(token)
        self.assertEqual(len(seen), 5)
        self.assertEqual(len({directory for command, directory, request in seen}), 5)
        self.assertEqual({request["model_routing"]["routing_role"] for command, directory, request in seen}, {"peer-reviewer"})
        self.assertEqual({command[command.index("--model") + 1] for command, directory, request in seen}, {"stable-review-fixture"})
        self.assertIsNone(runtime_module._routing_role.get())

    def test_original_content_and_format_controller_paths_route_separately_without_changing_trace_roles(self):
        seen = []
        tex = lambda label: r"\documentclass{article}\begin{document}" + label + r"\end{document}"
        def executor(command, prompt, directory):
            request = json.loads((directory / "request.json").read_text())
            seen.append((command, request))
            if request["model_routing"]["routing_role"] == "content-editor":
                return '```json\n{"actions_taken":["fixture edit"]}\n```\n```latex\n' + tex("content") + "\n```"
            return "```latex\n" + tex("formatted") + "\n```"
        configure(Runtime(self.root / "execution", executor=executor,
                          role_models={"content-editor": "content-fixture", "format-editor": "format-fixture"}))
        for name, value in [("log.md", "fixture data"), ("citations.json", "{}"),
                            ("guidelines.md", "fixture guidelines"), ("draft.tex", tex("baseline"))]:
            (self.root / name).write_text(value)
        agent = refinement_module.ContentRefinementAgent(str(self.root / "log.md"), str(self.root / "citations.json"),
                    str(self.root / "guidelines.md"), work_dir=str(self.root), max_reflections=1)
        scores = lambda overall: {**{a: 2 for a in ["Originality", "Quality", "Clarity", "Significance", "Soundness", "Presentation", "Contribution"]}, "Overall": overall, "Confidence": 3}
        peer = Mock(side_effect=[(scores(3), 3), (scores(4), 4)])
        def compile_pdf(cwd, pdf_path, basename, timeout=30):
            import pymupdf
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 72), "LABELLED COMPILE FIXTURE " + basename)
            doc.save(pdf_path)
            doc.close()
        with patch.object(refinement_module, "compile_latex", compile_pdf), \
             patch.object(refinement_module, "pdf_to_grid_images", return_value=[]), \
             patch.object(agent, "_get_peer_review", peer), \
             patch.object(agent, "_get_formatting_review", return_value={"other_issues": ["spacing fixture"]}):
            agent.run(str(self.root / "draft.tex"))
        self.assertEqual([request["role"] for command, request in seen], ["content-or-format-editor"] * 2)
        self.assertEqual([request["model_routing"]["routing_role"] for command, request in seen], ["content-editor", "format-editor"])
        self.assertEqual([command[command.index("--model") + 1] for command, request in seen], ["content-fixture", "format-fixture"])
        self.assertEqual(agent.worklogs["v1"]["outcome"], "ACCEPTED_SCORE_INCREASE")
        self.assertEqual(agent.format_worklogs["v1"]["outcome"], "ACCEPTED_COMPILE_SUCCESS")
        self.assertEqual((self.root / "final_refined_paper.tex").read_text(), tex("formatted"))
        self.assertEqual(peer.call_count, 2)
        self.assertIsNone(runtime_module._routing_role.get())


class ModelSelectionCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(configure, runtime_module._runtime)
        self.root = Path(self.tmp.name)

    def cli(self, *args):
        env = dict(os.environ, PATH="", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(SKILL / "scripts/run.py"), *args], env=env,
                              capture_output=True, text=True, timeout=20)

    def test_dry_run_requires_no_output_materials_tools_or_model_calls(self):
        profile = self.root / "models.json"
        profile.write_text(json.dumps({"groups": {"writing": "writer-fixture"}, "roles": {"peer-reviewer": None}}))
        result = self.cli("--show-model-plan", "--model-profile", str(profile))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["model_calls"], 0)
        plan = {item["role"]: item for item in output["model_policy"]["resolved_plan"]}
        self.assertEqual(plan["section-writer"]["model"], "writer-fixture")
        self.assertIsNone(plan["peer-reviewer"]["model"])
        self.assertEqual(set(self.root.iterdir()), {profile})

    def test_missing_profile_or_invalid_role_fails_before_probe_and_output_creation(self):
        output = self.root / "must-not-exist"
        for options in [("--model-profile", str(self.root / "missing.json")),
                        ("--role-models-json", '{"unknown-role":"fixture"}'),
                        ("--role-models-json", "[]"),
                        ("--role-models-json", "null"),
                        ("--model-map-json", "null"),
                        ("--role-models-json", ""),
                        ("--model-map-json", "")]:
            with self.subTest(options=options):
                result = self.cli("--preflight-only", "--output", str(output), *options)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Invalid model selection", result.stderr)
                self.assertFalse(output.exists())

    def test_original_profile_bytes_remain_bound_to_saved_plan_when_file_changes_during_preflight(self):
        path = self.root / "models.json"
        original = '{"name":"original fixture","groups":{"writing":"original-writer"}}\n'
        path.write_text(original)
        expected_hash = hashlib.sha256(original.encode()).hexdigest()
        spec = importlib.util.spec_from_file_location("paper_orchestra_model_cli_fixture", SKILL / "scripts/run.py")
        run = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(SKILL / "scripts"), *sys.path]):
            spec.loader.exec_module(run)
        def preflight(*args):
            path.write_text('{"name":"changed fixture","groups":{"writing":"changed-writer"}}\n')
            return []
        output = self.root / "probe-fixture"
        with patch.object(run, "preflight", side_effect=preflight), \
             patch.object(run.Runtime, "generate", return_value=SimpleNamespace(text="PAPER_ORCHESTRA_RUNTIME_OK")), \
             patch.object(run.subprocess, "run", return_value=SimpleNamespace(stdout="LABELLED VERSION FIXTURE\n", returncode=0)), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = run.main(["--preflight-only", "--model-profile", str(path), "--output", str(output)])
        self.assertEqual(status, 0)
        manifest = json.loads((output / "run.json").read_text())
        reusable = json.loads((output / "execution/model_profile.json").read_text())
        self.assertEqual(manifest["model_profile_source"]["sha256"], expected_hash)
        self.assertEqual(manifest["model_policy"]["profile"]["name"], "original fixture")
        self.assertEqual(reusable["roles"]["section-writer"], "original-writer")
        self.assertEqual(hashlib.sha256((output / "execution/model_profile.json").read_bytes()).hexdigest(), manifest["model_profile_snapshot_sha256"])


class ModelPolicyAuditTests(unittest.TestCase):
    """Audit labelled invocation records; these fixtures are not model evidence."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(configure, runtime_module._runtime)
        self.root = Path(self.tmp.name)
        profile = {"schema_version": 1, "name": "labelled audit fixture",
                   "groups": {"writing": "writer-fixture"}, "roles": {"peer-reviewer": None}}
        self.runtime = Runtime(self.root / "execution", model="global-fixture", model_profile=profile,
                               executor=lambda *args: '{"labelled_fixture":true}')
        configure(self.runtime)
        for role in ["outline", "peer-reviewer"]:
            token = role_override.set(role)
            try:
                self.runtime.generate(["LABELLED MODEL AUDIT FIXTURE"], {}, "upstream-fixture")
            finally:
                role_override.reset(token)
        self.trace = [json.loads(line) for line in (self.runtime.root / "trace.jsonl").read_text().split("\n") if line]
        snapshot = self.runtime.root / "model_profile.json"
        snapshot.write_text(json.dumps(self.runtime.model_policy.reusable_profile()))
        source = self.runtime.root / "model_profile.source.json"
        source.write_text(json.dumps(profile))
        self.run = {"model_policy": self.runtime.model_policy.snapshot(),
                    "model_profile_snapshot_sha256": self.sha(snapshot),
                    "model_profile_source": {"path": "external-fixture.json", "sha256": self.sha(source)}}

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def audit(self):
        return audit_model_policy(self.root, self.run, self.trace)

    def assert_invalid(self, text):
        summary, errors = self.audit()
        self.assertFalse(summary["valid"], summary)
        self.assertTrue(any(text in error for error in errors), errors)

    def test_selected_role_models_and_explicit_codex_reset_match_actual_argv(self):
        summary, errors = self.audit()
        self.assertEqual(errors, [])
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["attempts_checked"], 2)

    def test_changed_native_model_argv_is_rejected(self):
        start = next(e for e in self.trace if e["event"] == "agent_start" and e["role"] == "outline")
        start["command"][start["command"].index("--model") + 1] = "different-model"
        self.assert_invalid("argv")

    def test_request_routing_metadata_cannot_substitute_for_selected_model(self):
        start = next(e for e in self.trace if e["event"] == "agent_start" and e["role"] == "outline")
        path = self.runtime.root / "invocations" / start["invocation"] / "request.json"
        request = json.loads(path.read_text())
        request["model_routing"]["model"] = "different-model"
        path.write_text(json.dumps(request))
        self.assert_invalid("selected role policy")

    def test_reusable_snapshot_must_match_configuration_even_if_hash_is_updated(self):
        path = self.runtime.root / "model_profile.json"
        data = json.loads(path.read_text())
        data["roles"]["outline"] = "different-model"
        path.write_text(json.dumps(data))
        self.run["model_profile_snapshot_sha256"] = self.sha(path)
        self.assert_invalid("Reusable model profile snapshot")

    def test_original_source_snapshot_must_match_selected_configuration(self):
        path = self.runtime.root / "model_profile.source.json"
        data = json.loads(path.read_text())
        data["groups"]["writing"] = "different-model"
        path.write_text(json.dumps(data))
        self.run["model_profile_source"]["sha256"] = self.sha(path)
        self.assert_invalid("Original model profile snapshot")

    def test_legacy_runs_explicitly_bypass_new_model_policy_audit(self):
        summary, errors = audit_model_policy(self.root, {"status": "completed"}, [])
        self.assertFalse(summary["enabled"])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
