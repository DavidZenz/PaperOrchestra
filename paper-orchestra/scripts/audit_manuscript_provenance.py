#!/usr/bin/env python3
"""Audit the opt-in manuscript provenance recording protocol without model calls.

API: audit(output, run, trace) -> (summary, errors). The caller adds errors to its
main audit. Legacy runs lacking manuscript_provenance == 1 are explicitly bypassed.
Snapshots are read only; no run files are normalized, regenerated or overwritten.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
from orchestra_provenance import (
    SCHEMA, normalize_latex, transform_result, verify_files, verify_manuscript,
    worker_context,
)

WRITERS = {"section-writer", "content-or-format-editor"}
WORKSPACES = ("latex_writeup", "content_refinement_workdir")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(base, name):
    base = Path(base).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"Provenance audit path escapes its run: {name}")
    return path


def recorded(output, value):
    """Resolve recorded absolute paths after a run directory has been relocated."""
    value = Path(value)
    if not value.is_absolute():
        return inside(output, value)
    if value.is_relative_to(output):
        return inside(output, value)
    parts = value.parts
    for marker in ("execution", "content_refinement_workdir", "latex_writeup", "figure_sources", "figure_code"):
        if marker in parts:
            return inside(output, Path(*parts[parts.index(marker):]))
    raise ValueError(f"Unrecognized recorded run path: {value}")


def result_tex(result):
    """Return the exact local TeX variable consumed by the pinned controller."""
    parsed = result.get("parsed_response")
    if isinstance(parsed, str):
        try:
            container = json.loads(parsed)
        except ValueError:
            container = None
        return container.get("latex") if isinstance(container, dict) and "latex" in container else parsed
    if isinstance(parsed, dict) and "raw_response" in parsed:
        raw = result.get("raw_response", "")
        return raw.split("```latex", 1)[1].split("```", 1)[0].strip() if "```latex" in raw else raw.strip()
    return None


def original_parse(raw, parsed):
    # These imports create only the transport object; they perform no model call.
    from utils.gemini_utils import parse_gemini_latex_results, parse_gemini_json_latex_response
    if isinstance(parsed, dict) and "raw_response" in parsed:
        return {"raw_response": raw}
    if isinstance(parsed, str):
        try:
            container = json.loads(parsed)
        except ValueError:
            container = None
        if isinstance(container, dict) and "latex" in container:
            with redirect_stdout(io.StringIO()):
                return parse_gemini_json_latex_response(raw)
        return parse_gemini_latex_results(raw)
    raise ValueError("Unsupported upstream manuscript parser result shape")


def audit(output, run, trace):
    """Return provenance summary and errors, preserving backward auditability."""
    if run.get("manuscript_provenance") != 1:
        return {"enabled": False, "policy": "not-requested", "checks_performed": False}, []
    output = Path(output).resolve()
    errors = []
    summary = {"enabled": True, "policy": "selected-worker-code-v1", "figures": [],
               "writer_requests_checked": 0, "manuscript_results_checked": 0,
               "compiled_manuscripts": [], "final_pdf_visible_references": False,
               "final_pdf_selected_images_verified": False}

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def anchor(path, expected=None):
        path = inside(output, path)
        digest = sha(path)
        if expected is not None:
            require(digest == expected, f"Artifact hash mismatch: {path.relative_to(output)}")
        require(run.get("artifacts", {}).get(path.relative_to(output).as_posix()) == digest,
                f"Completed manifest does not anchor provenance artifact: {path.relative_to(output)}")
        return digest

    try:
        manifest_path = output / "figure_provenance.json"
        manifest_hash = anchor(manifest_path)
        manifest = json.loads(manifest_path.read_text())
        require(manifest.get("schema_version") == SCHEMA and manifest.get("policy") == summary["policy"],
                "Unsupported manuscript figure provenance policy")
        require(isinstance(manifest.get("figures"), list) and manifest["figures"], "Selected-source manifest has no figures")
        verify_files(output, manifest, originals=True)
        summary["manifest_sha256"] = manifest_hash
        expected_files = {name: value for item in manifest["figures"] for name, value in item["files"].items()}
        figure_ids = [item["figure_id"] for item in manifest["figures"]]
        require(len(figure_ids) == len(set(figure_ids)), "Duplicate figure provenance IDs")
        results = json.loads((output / "plotting_results.json").read_text())
        selected = [item for item in results if item.get("image_path")]
        require(len(selected) == len(manifest["figures"]) and {item["figure_id"] for item in selected} == set(figure_ids),
                "Selected-source manifest differs from actual plotted figure results")
        by_id = {item["figure_id"]: item for item in selected}
        for item in manifest["figures"]:
            figure = item["figure_id"]
            result = by_id[figure]
            require(result["image_path"] == item["image_path"], f"Selected figure image mapping differs: {figure}")
            expected_backend = run.get("plot_backend") if result.get("task_name") == "plot" else run.get("diagram_backend")
            require(item["backend"] == expected_backend, f"Selected figure renderer differs: {figure}")
            preview_hash = anchor(output / item["image_path"], item["preview_sha256"])
            matches = [(index, event) for index, event in enumerate(trace) if event.get("event") == "render_end"
                       and event.get("figure_id") == figure and event.get("preview_sha256") == preview_hash]
            require(bool(matches), f"Selected figure has no successful render context: {figure}")
            index, render = matches[-1]
            original = Path("figure_sources") / Path(render["directory"]).name
            require(original.as_posix() == item["original_directory"], f"Selected original renderer directory differs: {figure}")
            source_name = {"ggplot2": "source.R", "tikz": "source.tex"}.get(item["backend"])
            alias = figure.replace(" ", "_").lower()
            require(source_name is not None and item["source"] == f"figure_code/{alias}/{source_name}",
                    f"Selected stable source alias differs: {figure}")
            require(render.get("backend") == item["backend"] and render.get("source") == source_name
                    and render.get("source_sha256") == item["source_sha256"], f"Selected source differs from actual render: {figure}")
            require(any(event.get("event") == "render_start" and event.get("figure_id") == figure
                        and event.get("directory") == render["directory"] and event.get("backend") == item["backend"]
                        and event.get("source_sha256") == item["source_sha256"] for event in trace[:index]),
                    f"Selected render lacks its matching start context: {figure}")
            metadata = json.loads((output / original / "render.json").read_text())
            require(metadata.get("status") == "rendered" and metadata.get("figure_id") == figure
                    and metadata.get("backend") == item["backend"] and metadata.get("source") == source_name,
                    f"Selected original renderer metadata differs: {figure}")
            require(metadata.get("source_sha256") == item["source_sha256"]
                    and metadata.get("preview_sha256") == preview_hash
                    and metadata.get("pdf_sha256") == render.get("pdf_sha256"), f"Selected renderer checksums differ: {figure}")
            required_names = {source_name, "render.json", "figure.pdf", "preview.jpg"}
            if item["backend"] == "ggplot2":
                required_names.update({"worker.R", "sessionInfo.txt"})
            require({Path(name).name for name in item["files"]} == required_names,
                    f"Selected-source manifest omits or invents renderer artifacts: {figure}")
            require(item["files"].get(item["source"]) == item["source_sha256"], f"Selected source checksum mapping differs: {figure}")
            for name, expected in item["files"].items():
                anchor(output / name, expected)
                anchor(output / original / Path(name).name, expected)
            for name, expected in metadata.get("files_sha256", {}).items():
                require(item["files"].get(f"figure_code/{alias}/{name}") == expected,
                        f"Published renderer input differs from actual input: {figure}/{name}")
            summary["figures"].append({"figure_id": figure, "source": item["source"], "source_sha256": item["source_sha256"],
                                       "original_directory": item["original_directory"], "selected_render_verified": True})
        for name in WORKSPACES:
            workspace = output / name
            require(anchor(workspace / "figure_provenance.json") == manifest_hash, f"Workspace source manifest differs: {name}")
            verify_files(workspace, manifest)
            for relative, expected in expected_files.items():
                anchor(workspace / relative, expected)
    except Exception as exc:
        errors.append(f"Manuscript provenance manifest: {exc}")
        summary["valid"] = False
        return summary, errors

    starts = {event["invocation"]: event for event in trace if event.get("event") == "agent_start"}
    ends = [(index, event) for index, event in enumerate(trace) if event.get("event") == "agent_end"]
    calls = {event["call"]: event for event in trace if event.get("event") == "llm_call_start"}
    call_ends = {event["call"]: event for event in trace if event.get("event") == "llm_call_end"}
    request_manifests = {}
    for key, start in starts.items():
        if start.get("role") not in WRITERS:
            continue
        try:
            directory = inside(output, f"execution/invocations/{key}")
            request = json.loads((directory / "request.json").read_text())
            require(request.get("invocation") == key and request.get("call") == start.get("call")
                    and request.get("role") == start["role"], f"Writer request identity differs: {key}")
            request_manifest_path = directory / "figure_provenance.json"
            request_manifest_hash = sha(request_manifest_path)
            request_manifest = json.loads(request_manifest_path.read_text())
            require(request_manifest.get("schema_version") == SCHEMA and request_manifest.get("policy") == summary["policy"]
                    and request_manifest.get("figures"), f"Writer snapshot has an invalid source manifest: {key}")
            request_files = {name: value for item in request_manifest["figures"] for name, value in item["files"].items()}
            for recorded_request in (start, request):
                require(recorded_request.get("figure_provenance_sha256") == request_manifest_hash
                        and recorded_request.get("figure_provenance_files") == request_files,
                        f"Writer request lacks exact selected-source context: {key}")
            verify_files(directory, request_manifest, originals=True, original_base=output)
            request_index = trace.index(start)
            require(any(event.get("event") == "provenance_published" and event.get("stage") == "SectionWritingAgent"
                        and event.get("sha256") == request_manifest_hash for event in trace[:request_index]),
                    f"Writer source manifest lacks its joined-branch publication: {key}")
            for item in request_manifest["figures"]:
                historical_matches = [event for event in trace[:request_index] if event.get("event") == "render_end"
                                      and event.get("figure_id") == item["figure_id"]
                                      and event.get("preview_sha256") == item["preview_sha256"]]
                require(historical_matches, f"Writer historical source has no actual selected render: {key}")
                rendered = historical_matches[-1]
                require(item["original_directory"] == "figure_sources/" + Path(rendered["directory"]).name
                        and item["source_sha256"] == rendered.get("source_sha256")
                        and item["backend"] == rendered.get("backend"), f"Writer historical render context differs: {key}")
                require(sha(directory / Path(item["source"]).parent / "preview.jpg") == item["preview_sha256"],
                        f"Writer historical selected preview differs: {key}")
                for name, expected in item["files"].items():
                    anchor(output / item["original_directory"] / Path(name).name, expected)
            prompt = (directory / "prompt.txt").read_text()
            exact_context = worker_context(directory, request_manifest, validate_originals=False)
            require(exact_context in prompt, f"Writer prompt lacks exact manifest/source snapshots: {key}")
            require(sha(directory / "prompt.txt") == start.get("prompt_sha256") == request.get("prompt_sha256"),
                    f"Writer prompt hash differs: {key}")
            request_manifests[key] = (request_manifest, request_manifest_hash)
            summary["writer_requests_checked"] += 1
        except Exception as exc:
            errors.append(f"Manuscript writer context: {exc}")

    result_events = [(index, event) for index, event in enumerate(trace) if event.get("event") == "manuscript_result"]
    result_by_call = {}
    known_tex = {}
    for index, event in result_events:
        call = event.get("call")
        try:
            require(call not in result_by_call, f"Duplicate manuscript result: {call}")
            result_by_call[call] = event
            require(call in calls and calls[call].get("role") in WRITERS and event.get("role") == calls[call]["role"],
                    f"Manuscript result has no writer call: {call}")
            original_path = output / "execution/manuscripts" / f"{call}.upstream.json"
            effective_path = output / "execution/manuscripts" / f"{call}.effective.json"
            require(recorded(output, event["original_path"]) == original_path
                    and recorded(output, event["effective_path"]) == effective_path,
                    f"Manuscript result snapshot path differs: {call}")
            require(sha(original_path) == event.get("original_sha256") and sha(effective_path) == event.get("effective_sha256"),
                    f"Manuscript result snapshot hash differs: {call}")
            original_result = json.loads(original_path.read_text())
            effective_result = json.loads(effective_path.read_text())
            completed = [(end_index, end) for end_index, end in ends if end_index < index
                         and starts.get(end.get("invocation"), {}).get("call") == call]
            require(bool(completed), f"Manuscript result lacks completed separate invocation: {call}")
            end_index, end = completed[-1]
            require(end["invocation"] in request_manifests, f"Manuscript result lacks valid source input context: {call}")
            candidate_manifest, candidate_manifest_hash = request_manifests[end["invocation"]]
            require(event.get("provenance_sha256") == candidate_manifest_hash, f"Manuscript transformation used another manifest: {call}")
            directory = inside(output, f"execution/invocations/{end['invocation']}")
            raw = (directory / "response.txt").read_text()
            require(sha(directory / "response.txt") == end.get("response_sha256"), f"Original worker response changed: {call}")
            require(original_result.get("raw_response") == raw, f"Upstream raw channel differs from actual worker response: {call}")
            native = []
            for line in (directory / "events.jsonl").read_text().split("\n"):
                if line.strip():
                    try:
                        native.append(json.loads(line))
                    except ValueError:
                        pass
            messages = [item["item"].get("text") for item in native if item.get("type") == "item.completed"
                        and item.get("item", {}).get("type") == "agent_message"]
            require(messages and messages[-1] == raw, f"Actual native worker message differs from retained raw response: {call}")
            require(original_parse(raw, original_result.get("parsed_response")) == original_result.get("parsed_response"),
                    f"Upstream manuscript parse differs from original response: {call}")
            recomputed, details = transform_result(original_result, candidate_manifest)
            require(effective_result == recomputed and event.get("adaptation") == details,
                    f"Raw-to-effective manuscript transformation differs: {call}")
            require(call in call_ends and trace.index(call_ends[call]) > index, f"Manuscript result lacks subsequent parsed handoff: {call}")
            parsed_path = output / "execution/parsed" / f"{call}.json"
            require(sha(parsed_path) == call_ends[call].get("sha256")
                    and json.loads(parsed_path.read_text()) == effective_result.get("parsed_response"),
                    f"Effective manuscript differs from parsed controller handoff: {call}")
            tex = result_tex(effective_result)
            if isinstance(tex, str):
                digest = hashlib.sha256(tex.encode()).hexdigest()
                known_tex[digest] = (tex, candidate_manifest, candidate_manifest_hash)
                if r"\begin{document}" in tex and r"\end{document}" in tex:
                    verify_manuscript(tex, candidate_manifest)
            summary["manuscript_results_checked"] += 1
        except Exception as exc:
            errors.append(f"Manuscript result: {exc}")
    for call, end in call_ends.items():
        if calls.get(call, {}).get("role") in WRITERS and call not in result_by_call:
            errors.append(f"Successful writer call has no raw/effective manuscript transformation: {call}")
    if not any(start.get("role") == "section-writer" for start in starts.values()):
        errors.append("Manuscript provenance run has no section writer request")
    if not result_events:
        errors.append("Manuscript provenance run has no raw/effective manuscript results")

    provenance_events = [(index, event) for index, event in enumerate(trace) if event.get("event") == "compile_provenance"]
    successful_compiles = []
    checked_sources = set()
    for index, event in enumerate(trace):
        if event.get("event") != "compile_start":
            continue
        try:
            tex_hash = event.get("tex_sha256")
            require(tex_hash in known_tex, f"Compiled TeX is not an effective worker handoff: {event.get('tex')}")
            source, candidate_manifest, candidate_manifest_hash = known_tex[tex_hash]
            complete = r"\begin{document}" in source and r"\end{document}" in source
            candidates = [(prior_index, prior) for prior_index, prior in provenance_events if prior_index < index
                          and prior.get("tex") == event.get("tex") and prior.get("tex_sha256") == tex_hash]
            if complete:
                require(bool(candidates), f"Complete candidate lacks compile provenance: {event['tex']}")
                prior_index, prior = candidates[-1]
                snapshot = recorded(output, prior["source_snapshot"])
                require(sha(snapshot) == prior.get("source_snapshot_sha256") == tex_hash,
                        f"Compiled manuscript snapshot hash differs: {event['tex']}")
                require(snapshot.read_text() == source, f"Compiled snapshot differs from effective worker TeX: {event['tex']}")
                verify_manuscript(source, candidate_manifest)
                provenance_snapshot = recorded(output, prior["provenance_snapshot"])
                require(sha(provenance_snapshot) == prior.get("provenance_sha256") == candidate_manifest_hash,
                        f"Compiled manuscript used another source manifest: {event['tex']}")
                require(provenance_snapshot.parent == snapshot.parent, f"Compiled source/manifest snapshot directories differ: {event['tex']}")
                verify_files(snapshot.parent, candidate_manifest, originals=True, original_base=output)
                checked_sources.add(prior_index)
                summary["compiled_manuscripts"].append({"tex": str(recorded(output, event["tex"]).relative_to(output)),
                                                        "tex_sha256": tex_hash, "source_snapshot": str(snapshot.relative_to(output))})
            end = next((later for later in trace[index + 1:] if later.get("event") == "compile_end" and later.get("pdf") == event.get("pdf")), None)
            if end and end.get("exists"):
                require(complete, f"A successful compiled manuscript is incomplete: {event['tex']}")
                successful_compiles.append((tex_hash, end.get("sha256")))
        except Exception as exc:
            errors.append(f"Manuscript compile provenance: {exc}")
    for index, event in provenance_events:
        if index not in checked_sources:
            errors.append(f"Manuscript compile provenance has no verified compiler consumption: {event.get('tex')}")

    try:
        final_tex = output / "content_refinement_workdir/final_refined_paper.tex"
        final_tex_hash = anchor(final_tex)
        verify_manuscript(final_tex.read_text(), manifest)
        final_pdf = output / "final_paper.pdf"
        final_pdf_hash = anchor(final_pdf)
        require((final_tex_hash, final_pdf_hash) in successful_compiles,
                "Final TeX/PDF do not match one accepted compiled manuscript source")
        import pymupdf
        with pymupdf.open(final_pdf) as document:
            visible = re.sub(r"\s+", "", "\n".join(page.get_text() for page in document))
            image_hashes = set()
            xrefs = {image[0] for page in document for image in page.get_images(full=True)}
            for xref in xrefs:
                extracted = document.extract_image(xref)
                if extracted and extracted.get("image"):
                    image_hashes.add(hashlib.sha256(extracted["image"]).hexdigest())
        require("Figuresourceprovenance" in visible, "Final PDF has no visible figure-source provenance section")
        for item in manifest["figures"]:
            require(re.sub(r"\s+", "", item["source"]) in visible and item["source_sha256"] in visible,
                    f"Final PDF lacks visible exact source path/hash: {item['figure_id']}")
            for name, expected in item["files"].items():
                if name.endswith("/worker.R"):
                    require(re.sub(r"\s+", "", name) in visible and expected in visible,
                            f"Final PDF lacks visible export-wrapper path/hash: {item['figure_id']}")
        summary["final_pdf_visible_references"] = True
        for item in manifest["figures"]:
            require(item["preview_sha256"] in image_hashes,
                    f"Final PDF does not embed the exact selected figure preview: {item['figure_id']}")
        summary["final_pdf_selected_images_verified"] = True
    except Exception as exc:
        errors.append(f"Final manuscript provenance: {exc}")
    summary["valid"] = not errors
    return summary, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    run = json.loads((args.output / "run.json").read_text())
    trace = [json.loads(line) for line in (args.output / "execution/trace.jsonl").read_text().split("\n") if line.strip()]
    summary, errors = audit(args.output, run, trace)
    print(json.dumps({"manuscript_provenance": summary, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
