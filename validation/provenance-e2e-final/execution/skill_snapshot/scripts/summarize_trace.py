#!/usr/bin/env python3
"""Audit recorded process/session evidence and upstream artifact handoffs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))


def executed_search(events):
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_state(root):
    files = {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob("*"))
             if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc" and p.name != ".DS_Store"}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"sha256":digest,"files":files}


def summarize(output):
    output = Path(output).resolve()
    run = json.loads((output / "run.json").read_text())
    trace = [json.loads(s) for s in (output / "execution" / "trace.jsonl").read_text().split("\n") if s.strip()]
    errors = []
    warnings = []
    starts = {e["invocation"]: e for e in trace if e["event"] == "agent_start"}
    ends = [e for e in trace if e["event"] == "agent_end"]
    ended = {e["invocation"] for e in ends}
    errored = {e["invocation"] for e in trace if e["event"] == "agent_error"}
    for key in starts:
        if key not in ended and key not in errored:
            errors.append(f"Invocation {key} has no terminal outcome")
    processes = {e["invocation"]: e["pid"] for e in trace if e["event"] == "process_started"}
    sessions = []
    for event in ends:
        key = event["invocation"]
        start = starts.get(key)
        if not start or key not in processes:
            errors.append(f"Invocation {key} has no matching process start")
            continue
        directory = output / "execution" / "invocations" / key
        for filename, expected in [("prompt.txt", start["prompt_sha256"]), ("response.txt", event["response_sha256"])]:
            if not (directory / filename).exists() or sha(directory / filename) != expected:
                errors.append(f"Invocation {key} {filename} hash mismatch")
        raw = []
        for line_number, line in enumerate((directory / "events.jsonl").read_text().split("\n"), 1):
            if not line.strip():
                continue
            try:
                raw.append(json.loads(line))
            except ValueError:
                warnings.append({"invocation":key,"file":"events.jsonl","line":line_number,
                                 "issue":"Malformed raw event retained; excluded from proof",
                                 "line_sha256":hashlib.sha256(line.encode()).hexdigest()})
        recorded_sessions = [e["thread_id"] for e in raw if e.get("type") == "thread.started"]
        if len(recorded_sessions) != 1 or recorded_sessions != event["sessions"]:
            errors.append(f"Invocation {key} has invalid independent session evidence")
        if not any(e.get("type") == "turn.completed" for e in raw):
            errors.append(f"Invocation {key} did not complete a turn")
        if any(e.get("type") in {"turn.failed", "error"} for e in raw):
            errors.append(f"Invocation {key} contains a failed turn")
        if start["search_required"] and not executed_search(raw):
            errors.append(f"Invocation {key} has no executed web_search event")
        sessions.extend(recorded_sessions)
    if len(sessions) != len(set(sessions)):
        errors.append("Independent invocations reused a session")
    # PIDs can be reused by an OS over time; UUIDs/sessions establish identity.
    call_roles = {e["call"]: e["role"] for e in trace if e["event"] == "llm_call_start"}
    roles = []
    review_groups = []
    pending_review_roles = []
    pending_review_values = []
    failed_ensembles = []
    previous_review_end = -1
    for event in trace:
        if event["event"] not in {"llm_call_end", "llm_call_error"}:
            continue
        call = event["call"]
        role = call_roles.get(call)
        if not role:
            errors.append(f"Completed model call {call} has no call start")
            continue
        is_failure = event["event"] == "llm_call_error"
        linked = [key for key, start in starts.items() if start.get("call") == call
                  and key in (ended | errored if is_failure else ended) and key in processes]
        if not linked:
            errors.append(f"Model call {call} has no matching separate agent attempt/outcome")
        if role in {"peer-reviewer", "area-chair"}:
            start_indices = [index for index, e in enumerate(trace) if e["event"] == "llm_call_start" and e["call"] == call]
            end_index = trace.index(event)
            if len(start_indices) != 1 or start_indices[0] <= previous_review_end or start_indices[0] >= end_index:
                errors.append("Reviewer/chair calls overlapped or have invalid sequential spans")
            previous_review_end = end_index
        if is_failure:
            if role in {"peer-reviewer", "area-chair"}:
                failed_ensembles.append({"completed_members":len(pending_review_roles),"failed_role":role,"call":call})
                pending_review_roles.clear()
                pending_review_values.clear()
            continue
        parsed_path = output / "execution" / "parsed" / f"{call}.json"
        parsed = None
        if not parsed_path.exists() or sha(parsed_path) != event.get("sha256"):
            errors.append(f"Parsed model call {call} artifact hash mismatch")
        else:
            parsed = json.loads(parsed_path.read_text())
        if role in {"peer-reviewer", "area-chair"}:
            pending_review_roles.append(role)
            pending_review_values.append(parsed)
            if role == "area-chair":
                if pending_review_roles != ["peer-reviewer"] * 3 + ["area-chair"]:
                    errors.append("Completed reviewer calls do not form sequential 3-reviewer + chair groups")
                else:
                    roles.extend(pending_review_roles)
                    review_groups.append((trace.index(event), list(pending_review_values)))
                pending_review_roles.clear()
                pending_review_values.clear()
    if pending_review_roles:
        errors.append("Incomplete reviewer ensemble has no recorded failure/fallback")
    reviews = roles
    handoffs = []
    observed_handoffs = set()
    for event in trace:
        if event["event"] == "stage_start" and event["stage"] == "SectionWritingAgent":
            inputs = event["inputs"]
            for left, right in [
                ("outline.json", "literature_agent_output/outline_v1.json"),
                ("latex_writeup/template.tex", "literature_agent_output/updated_template.tex"),
                ("latex_writeup/references.bib", "literature_agent_output/references.bib"),
            ]:
                ok = left in inputs and inputs[left] == inputs.get(right)
                handoffs.append({"from":right, "to":left, "hash_equal":ok})
                observed_handoffs.add("section")
                if not ok:
                    errors.append(f"Section handoff differs: {right} -> {left}")
        if event["event"] == "stage_start" and event["stage"] == "ContentRefinementAgent":
            inputs = event["inputs"]
            left, right = "latex_writeup/raw_draft_paper.tex", "content_refinement_workdir/raw_draft_paper.tex"
            ok = left in inputs and inputs[left] == inputs.get(right)
            handoffs.append({"from": left, "to":right, "hash_equal":ok})
            observed_handoffs.add("refinement")
            if not ok:
                errors.append("Section draft was not handed to refinement unchanged")
    final = output / "final_paper.pdf"
    aggregation = []
    frozen_build = None
    if run.get("skill_bundle"):
        snapshot = bundle_state(output / "execution" / "skill_snapshot")
        launch, finish = run["skill_bundle"], run.get("final_skill_bundle")
        frozen_build = {"launch_sha256":launch["sha256"],"snapshot_sha256":snapshot["sha256"],
                        "finish_sha256":(finish or {}).get("sha256"),
                        "snapshot_matches":snapshot == launch, "unchanged":finish == launch}
        if snapshot != launch:
            errors.append("Recorded skill source snapshot differs from launch bundle")
        if run["status"] == "completed" and (finish != launch or not run.get("skill_unchanged")):
            errors.append("Installed skill did not remain unchanged through the run")
        if run.get("skill_path") and Path(run["skill_path"]).is_dir():
            current = bundle_state(Path(run["skill_path"]))
            frozen_build["currently_installed_sha256"] = current["sha256"]
            frozen_build["currently_installed_matches"] = current == launch
    selected_figures = []
    parallel_plot_branch = None
    if run.get("plotting") and run.get("plot_backend") in {"ggplot2","matplotlib"}:
        spans = {e["span"]:e for e in trace if e["event"] == "stage_start"}
        intervals = {e["stage"]:(spans[e["span"]]["time"], e["time"])
                     for e in trace if e["event"] == "stage_end" and e.get("span") in spans}
        if "HybridLiteratureAgent" in intervals and "PlottingAgent" in intervals:
            lit, plot = intervals["HybridLiteratureAgent"], intervals["PlottingAgent"]
            parallel_plot_branch = max(lit[0],plot[0]) < min(lit[1],plot[1])
        if run["status"] == "completed" and not parallel_plot_branch:
            errors.append("Literature and plotting branches did not execute concurrently")
        results_path = output / "plotting_results.json"
        outline_path = output / "outline.json"
        results = json.loads(results_path.read_text()) if results_path.exists() else []
        planned = json.loads(outline_path.read_text()).get("plotting_plan",[]) if outline_path.exists() else []
        result_ids = {r.get("figure_id") for r in results if r.get("image_path")}
        if run["status"] == "completed" and (not planned or any(p.get("figure_id") not in result_ids for p in planned)):
            errors.append("A planned figure is missing its rendered handoff")
        for result in results:
            figure_id = result.get("figure_id")
            renderer = run["plot_backend"] if result.get("task_name") == "plot" else run.get("diagram_backend")
            if renderer not in {"ggplot2","tikz"}:
                continue
            if not result.get("image_path"):
                errors.append(f"Figure {figure_id} has no image handoff")
                continue
            image_path = output / result["image_path"]
            if not image_path.exists():
                errors.append(f"Figure {figure_id} handoff file is missing")
                continue
            image_hash = sha(image_path)
            matches = [e for e in trace if e["event"] == "render_end" and e.get("figure_id") == figure_id
                       and e.get("backend") == renderer and e.get("preview_sha256") == image_hash]
            if not matches:
                errors.append(f"Figure {figure_id} has no matching source-backed renderer result")
                continue
            rendered = matches[-1]
            directory = output / "figure_sources" / Path(rendered["directory"]).name
            source = directory / rendered["source"]
            source_ok = source.is_file() and sha(source) == rendered["source_sha256"]
            pdf = directory / "figure.pdf"
            pdf_ok = pdf.is_file() and sha(pdf) == rendered["pdf_sha256"]
            copied = output / "latex_writeup" / result["image_path"]
            copy_ok = copied.is_file() and sha(copied) == image_hash
            writer_starts = [e for e in trace if e["event"] == "stage_start" and e["stage"] == "SectionWritingAgent"]
            writer_ok = bool(writer_starts) and writer_starts[-1]["inputs"].get("latex_writeup/" + result["image_path"]) == image_hash
            workers = [e for e in starts.values() if e.get("figure_id") == figure_id and e.get("role") == f"{renderer}-visualizer"
                       and e["invocation"] in ended]
            generated = False
            for worker in workers:
                response = (output / "execution" / "invocations" / worker["invocation"] / "response.txt").read_text()
                labels = "r|R" if renderer == "ggplot2" else "latex|tex"
                match = re.search(r"```(?:" + labels + r")\s*\n(.*?)```", response, re.DOTALL)
                code = match.group(1).strip() if match else response.strip()
                if hashlib.sha256(code.encode()).hexdigest() == rendered["source_sha256"]:
                    generated = True
            metadata = json.loads((directory / "render.json").read_text())
            inputs_ok = bool(metadata.get("files_sha256")) and all(
                (directory / name).is_file() and sha(directory / name) == expected
                for name, expected in metadata.get("files_sha256",{}).items())
            anchored = [directory / "render.json"] + [directory / name for name in metadata.get("files_sha256",{})]
            anchors_ok = all(path.is_file() and run.get("artifacts",{}).get(path.relative_to(output).as_posix()) == sha(path)
                             for path in anchored)
            inputs_ok = inputs_ok and anchors_ok
            if not (source_ok and pdf_ok and copy_ok and writer_ok and workers and generated and inputs_ok):
                errors.append(f"Figure {figure_id} lacks valid code, PDF, handoff, or separate-worker proof")
            selected_figures.append({"figure_id":figure_id,"backend":renderer,
                                    "source":str(source.relative_to(output)),"source_hash_valid":source_ok,
                                    "pdf_hash_valid":pdf_ok,"preview_handoff_valid":copy_ok,
                                    "section_writer_received":writer_ok,"worker_invocations":len(workers),
                                    "code_generated_by_worker":generated,"renderer_inputs_valid":inputs_ok})
    files = list((output / "content_refinement_workdir" / "peer_reviews").glob("review_v*.json"))
    files.sort(key=lambda p:int(p.stem.removeprefix("review_v")))
    if files:
        refinement_starts = [index for index, event in enumerate(trace)
                             if event["event"] == "stage_start" and event["stage"] == "ContentRefinementAgent"]
        last_refinement = max(refinement_starts, default=-1)
        retained_review_groups = [values for index, values in review_groups if index > last_refinement]
        if len(files) != len(retained_review_groups):
            errors.append("Saved aggregate reviews do not match completed ensembles")
        for index, file in enumerate(files[:len(retained_review_groups)]):
            individual = retained_review_groups[index][:3]
            aggregate = json.loads(file.read_text())
            checked = []
            for axis, bounds in [(a,(1,4)) for a in ["Originality","Quality","Clarity","Significance","Soundness","Presentation","Contribution"]] + [("Overall",(1,10)),("Confidence",(1,5))]:
                values = []
                for review in individual:
                    try:
                        value = int(review[axis])
                        if bounds[0] <= value <= bounds[1]:
                            values.append(value)
                    except (ValueError,TypeError,KeyError):
                        pass
                if values:
                    expected = int(round(sum(values)/len(values)))
                    ok = aggregate.get(axis) == expected
                    checked.append({"axis":axis,"expected":expected,"actual":aggregate.get(axis),"ok":ok})
                    if not ok:
                        errors.append(f"{file.name} {axis} is not the upstream rounded mean")
            aggregation.append({"file":file.name,"scores":checked})
    if run["status"] == "completed":
        if not final.exists():
            errors.append("Completed run has no final PDF")
        elif run.get("artifacts", {}).get("final_paper.pdf") != sha(final):
            errors.append("Final PDF does not match the manifest artifact hash")
        if observed_handoffs != {"section","refinement"}:
            errors.append("Completed run requires both section and refinement handoff evidence")
        if not reviews:
            errors.append("Completed run has no reviewer ensemble evidence")
        required_stages = ["OutlineAgent", "HybridLiteratureAgent", "SectionWritingAgent", "ContentRefinementAgent"]
        if run.get("plotting"):
            required_stages.append("PlottingAgent")
        stage_starts = {e["span"]:e for e in trace if e["event"] == "stage_start"}
        stage_ends = [e for e in trace if e["event"] == "stage_end"]
        for name in required_stages:
            matches = [e for e in stage_ends if e["stage"] == name and e.get("span") in stage_starts]
            if not matches:
                errors.append(f"Completed run has no successful {name} stage span")
        for end in stage_ends:
            start = stage_starts.get(end.get("span"))
            if not start or start.get("stage") != end.get("stage") or trace.index(start) >= trace.index(end):
                errors.append("Invalid stage start/end ordering")
        for before, after in [("OutlineAgent","HybridLiteratureAgent"),("HybridLiteratureAgent","SectionWritingAgent"),("SectionWritingAgent","ContentRefinementAgent")]+([("OutlineAgent","PlottingAgent"),("PlottingAgent","SectionWritingAgent")] if run.get("plotting") else []):
            for start in [e for e in trace if e["event"] == "stage_start" and e["stage"] == after]:
                if not any(e["event"] == "stage_end" and e["stage"] == before for e in trace[:trace.index(start)]):
                    errors.append(f"Stage {after} began before {before} completed")
    failures = [e for e in trace if e["event"] == "capability_failure"]
    if failures:
        errors.append("Required capability failure was recorded")
    if any(e["event"] == "provenance_error" for e in trace):
        errors.append("Manuscript figure provenance failure was recorded")
    from audit_manuscript_provenance import audit as audit_manuscripts
    manuscript_provenance, provenance_errors = audit_manuscripts(output, run, trace)
    errors.extend(provenance_errors)
    return {"status": run["status"], "upstream_commit": run["upstream_commit"],
            "agent_attempts": len(starts), "completed_agent_attempts":len(ends),
            "unique_sessions":len(set(sessions)), "process_launches":len(processes),
            "roles":dict(Counter(e["role"] for e in ends)),
            "ensembles":len(reviews)//4,
            "failed_review_ensembles":failed_ensembles,
            "live_searches":sum(bool(e.get("searched")) for e in ends),
            "semantic_scholar_statuses":dict(Counter(str(e["status"]) for e in trace if e["event"] == "http_end")),
            "handoffs":handoffs,
            "aggregate_score_checks":aggregation,
            "frozen_build":frozen_build,
            "parallel_plot_branch":parallel_plot_branch,
            "selected_figures":selected_figures,
            "manuscript_provenance":manuscript_provenance,
            "revision_decisions":[{k:v for k,v in e.items() if k in {"version", "outcome", "total_gain", "total_drop"}} for e in trace if e["event"] == "revision_decision"],
            "format_decisions":[{k:v for k,v in e.items() if k in {"version", "outcome"}} for e in trace if e["event"] == "format_decision"],
            "evidence_valid":not errors, "errors":errors, "warnings":warnings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = summarize(args.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["evidence_valid"] else 1)
