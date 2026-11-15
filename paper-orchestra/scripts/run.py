#!/usr/bin/env python3
"""Run the pinned authors' controller with separate Codex agent invocations."""
from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "vendor"))
from orchestra_runtime import Runtime, configure, instrument, artifacts
from bundle import manifest as bundle_manifest, snapshot as snapshot_bundle
from orchestra_models import ModelPolicy, validate_profile


def find_rscript():
    return (os.environ.get("PAPER_ORCHESTRA_RSCRIPT") or shutil.which("Rscript")
            or next((p for p in ["/opt/homebrew/opt/r/bin/Rscript", "/usr/local/bin/Rscript"] if Path(p).is_file()), "Rscript"))


def preflight(plotting=False, image_command=None, plot_backend="ggplot2", diagram_backend="tikz", rscript=None):
    missing = [x for x in ["codex", "pdflatex", "bibtex"] if not shutil.which(x)]
    for module in ["google.genai", "pymupdf", "pypdf", "cv2", "numpy", "matplotlib", "json_repair", "requests", "pydantic", "thefuzz", "dotenv", "rich", "tqdm"]:
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        except ModuleNotFoundError:
            missing.append(module)
    if plotting and diagram_backend == "image" and not image_command:
        missing.append("image-tool command for potential diagram generation (--image-command-json)")
    if plotting and plot_backend == "ggplot2":
        rscript = rscript or find_rscript()
        if not shutil.which(rscript):
            missing.append("Rscript (--rscript or PAPER_ORCHESTRA_RSCRIPT)")
        else:
            result = subprocess.run([rscript,"--vanilla","-e","quit(status=if(requireNamespace('ggplot2',quietly=TRUE)) 0 else 1)"], capture_output=True, timeout=30)
            if result.returncode:
                missing.append("R package ggplot2")
    if plotting and diagram_backend == "tikz":
        if not shutil.which("kpsewhich"):
            missing.append("kpsewhich (TeX package lookup)")
        else:
            for package in ["standalone.cls", "tikz.sty"]:
                result = subprocess.run(["kpsewhich", package], capture_output=True, text=True, timeout=15)
                if result.returncode or not result.stdout.strip():
                    missing.append(f"LaTeX package {package}")
    if image_command and (not isinstance(image_command, list) or not image_command or not all(isinstance(x, str) for x in image_command)):
        missing.append("image command must be a nonempty JSON argv array")
    if image_command and isinstance(image_command, list) and image_command and not shutil.which(image_command[0]):
        missing.append(f"image executable {image_command[0]}")
    return missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", type=Path)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--idea-filename", default="idea_sparse.md")
    parser.add_argument("--experimental-log-filename", default="experimental_log.md")
    parser.add_argument("--cutoff", default=datetime.now().strftime("%Y-%m"))
    parser.add_argument("--use-plotting", action="store_true")
    parser.add_argument("--model", help="Codex model; otherwise use the runtime's configured default")
    parser.add_argument("--model-map-json", help="JSON mapping of upstream writer/reflection/discovery model names to Codex models")
    parser.add_argument("--model-profile", type=Path, help="Saved JSON default/group/role model choices")
    parser.add_argument("--role-models-json", help="JSON mapping of individual role names to Codex model IDs")
    parser.add_argument("--show-model-plan", action="store_true", help="Print resolved role models without starting agents")
    parser.add_argument("--image-command-json", help="JSON argv of image tool; appended argument is request JSON path")
    parser.add_argument("--plot-backend", choices=["ggplot2"], default="ggplot2")
    parser.add_argument("--diagram-backend", choices=["tikz"], default="tikz")
    parser.add_argument("--rscript", default=find_rscript())
    parser.add_argument("--render-timeout", type=int, default=60)
    parser.add_argument("--agent-timeout", type=int, default=600)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        model_map = json.loads(args.model_map_json) if args.model_map_json is not None else {}
        role_models = json.loads(args.role_models_json) if args.role_models_json is not None else {}
        if not isinstance(model_map, dict) or not isinstance(role_models, dict):
            raise ValueError("--model-map-json and --role-models-json must contain JSON objects")
        profile_bytes = args.model_profile.read_bytes() if args.model_profile else None
        model_profile = validate_profile(json.loads(profile_bytes)) if profile_bytes is not None else {}
        model_policy = ModelPolicy(model=args.model, model_map=model_map,
                                   profile=model_profile, role_models=role_models)
    except (ValueError, OSError) as exc:
        parser.error(f"Invalid model selection: {exc}")
    if args.show_model_plan:
        print(json.dumps({"model_calls":0, "model_policy":model_policy.snapshot()}, indent=2))
        return 0
    if args.output is None:
        parser.error("--output is required unless --show-model-plan")
    if not args.preflight_only:
        if not args.materials or not args.template:
            parser.error("--materials and --template are required unless --preflight-only")
        for path in [args.materials / args.idea_filename, args.materials / args.experimental_log_filename,
                     args.template / "template.tex", args.template / "guidelines.md"]:
            if not path.is_file():
                parser.error(f"Required input file missing: {path}")
    image_command = json.loads(args.image_command_json) if args.image_command_json else None
    missing = preflight(args.use_plotting, image_command, args.plot_backend, args.diagram_backend, args.rscript)
    if missing:
        print(json.dumps({"status": "unavailable", "missing": missing}, indent=2))
        return 2
    output = args.output.resolve()
    if output.is_relative_to(SKILL) or (args.materials and output.is_relative_to(args.materials.resolve())):
        parser.error("Output must be outside the installed skill and material directories")
    # Authors' pipeline removes intermediate directories. Require a fresh destination.
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be a new or empty directory; prior runs are retained")
    output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(output / "execution", model=args.model, model_map=model_map,
                      timeout=args.agent_timeout, image_command=image_command,
                      plot_backend=args.plot_backend, diagram_backend=args.diagram_backend,
                      rscript=args.rscript, render_timeout=args.render_timeout,
                      manuscript_provenance=args.use_plotting,
                      model_profile=model_profile, role_models=role_models)
    os.environ.setdefault("MPLCONFIGDIR", str(output / "execution" / "matplotlib-cache"))
    os.environ.setdefault("XDG_CACHE_HOME", str(output / "execution" / "cache"))
    configure(runtime)
    manifest = {"upstream_commit": json.loads((SKILL / "upstream-lock.json").read_text())["commit"],
                "backend": "fresh codex exec process for every model attempt",
                "plotting": args.use_plotting, "cutoff": args.cutoff,
                "model": args.model or "Codex configured default", "model_map": model_map,
                "image_command": image_command, "status": "running"}
    manifest["model_policy"] = model_policy.snapshot()
    if args.model_profile:
        manifest["model_profile_source"] = {"path":str(args.model_profile.resolve()),
                                            "sha256":hashlib.sha256(profile_bytes).hexdigest()}
        (runtime.root / "model_profile.source.json").write_bytes(profile_bytes)
    model_snapshot = runtime.root / "model_profile.json"
    model_snapshot.write_text(json.dumps(model_policy.reusable_profile(), indent=2) + "\n")
    manifest["model_profile_snapshot_sha256"] = hashlib.sha256(model_snapshot.read_bytes()).hexdigest()
    manifest.update(plot_backend=args.plot_backend, diagram_backend=args.diagram_backend,
                    rscript=args.rscript, render_timeout=args.render_timeout, skill_path=str(SKILL),
                    manuscript_provenance=1 if args.use_plotting else None)
    manifest["skill_bundle"] = snapshot_bundle(SKILL, runtime.root / "skill_snapshot")
    manifest["implementation_sha256"] = manifest["skill_bundle"]["files"]
    software = {}
    for label, command in [("codex",["codex","--version"]),("pdflatex",["pdflatex","--version"])]:
        result = subprocess.run(command,capture_output=True,text=True,timeout=30)
        software[label] = result.stdout.split("\n")[0]
    if args.use_plotting and args.plot_backend == "ggplot2":
        result = subprocess.run([args.rscript,"--vanilla","-e","cat(R.version.string,'\\n'); cat('ggplot2 ',as.character(packageVersion('ggplot2')),'\\n'); sessionInfo()"],capture_output=True,text=True,timeout=30)
        software["R_session"] = result.stdout
    manifest["software"] = software
    (output / "run.json").write_text(json.dumps(manifest, indent=2))
    runtime.event("run_start", **manifest)
    try:
        # Executed runtime proof, not just the presence of an executable.
        from google.genai import types
        response = runtime.generate([types.Part.from_text(text="Reply exactly PAPER_ORCHESTRA_RUNTIME_OK. Use no tools.")], {}, "runtime-probe")
        if response.text.strip() != "PAPER_ORCHESTRA_RUNTIME_OK":
            raise RuntimeError("Separate-agent capability probe did not return the expected response")
        if args.preflight_only:
            manifest["status"] = "preflight_ok"
            return 0
        shutil.copytree(args.materials, output / "raw_materials")
        if args.use_plotting:
            from orchestra_visuals import install
            install()
        instrument(output)
        if args.use_plotting:
            from methods.paper_writer_with_plotting import write_single_paper
        else:
            from methods.paper_writer import write_single_paper
        success = write_single_paper(
            base_dir=str(output), latex_template_dir=str(args.template.resolve()),
            idea_filename=args.idea_filename, experimental_log_filename=args.experimental_log_filename,
            research_cutoff=args.cutoff)
        if runtime.fatal or runtime.pending_search:
            raise RuntimeError("Required runtime capabilities failed: " + "; ".join(runtime.fatal)
                               + (f"; {len(runtime.pending_search)} discovery tasks lack completed search evidence" if runtime.pending_search else ""))
        if not success or not (output / "final_paper.pdf").is_file():
            raise RuntimeError("Authors' controller exhausted its three paper attempts")
        manifest["final_skill_bundle"] = bundle_manifest(SKILL)
        manifest["skill_unchanged"] = manifest["final_skill_bundle"] == manifest["skill_bundle"]
        if not manifest["skill_unchanged"]:
            raise RuntimeError("Installed skill changed during the run; frozen-build conformance failed")
        manifest["status"] = "completed"
        manifest["artifacts"] = artifacts(output)
        (output / "run.json").write_text(json.dumps(manifest, indent=2))
        from summarize_trace import summarize
        audit = summarize(output)
        (output / "execution" / "audit.json").write_text(json.dumps(audit, indent=2))
        if not audit["evidence_valid"]:
            raise RuntimeError("Execution evidence audit failed: " + "; ".join(audit["errors"]))
        return 0
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
        manifest["error"] = "Run interrupted; no completed paper run is claimed"
        runtime.event("run_interrupted")
        return 130
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)
        runtime.event("run_failure", error=str(exc))
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    finally:
        (output / "run.json").write_text(json.dumps(manifest, indent=2))
        runtime.event("run_end", status=manifest["status"])


if __name__ == "__main__":
    raise SystemExit(main())
