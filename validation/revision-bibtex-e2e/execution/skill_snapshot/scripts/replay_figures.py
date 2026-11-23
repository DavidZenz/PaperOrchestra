#!/usr/bin/env python3
"""Re-render retained R/TikZ sources in a fresh directory without an LLM call."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
from orchestra_visuals import render_saved


def replay(run, destination, rscript="Rscript", timeout=60):
    run, destination = Path(run).resolve(), Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Replay destination must be new or empty")
    destination.mkdir(parents=True, exist_ok=True)
    run_manifest = json.loads((run / "run.json").read_text()) if (run / "run.json").is_file() else None
    results = []
    for file in sorted((run / "figure_sources").glob("*/render.json")):
        meta = json.loads(file.read_text())
        if meta.get("status") != "rendered":
            continue
        if run_manifest:
            for path in [file] + [file.parent / name for name in meta.get("files_sha256", {})]:
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if run_manifest.get("artifacts", {}).get(path.relative_to(run).as_posix()) != actual:
                    raise ValueError("Retained rendering input differs from the completed run manifest")
        target = destination / file.parent.name
        target.mkdir()
        for name in [meta["source"], "worker.R", "render.json"]:
            if (file.parent / name).is_file():
                shutil.copy(file.parent / name, target / name)
        source_hash = hashlib.sha256((target / meta["source"]).read_bytes()).hexdigest()
        if source_hash != meta["source_sha256"]:
            raise ValueError("Retained source hash mismatch")
        command = render_saved(target, rscript=rscript, timeout=timeout)
        preview_hash = hashlib.sha256((target / "preview.jpg").read_bytes()).hexdigest()
        results.append({"id":file.parent.name, "backend":meta["backend"], "command":command,
                        "source_sha256":source_hash, "preview_identical":preview_hash == meta["preview_sha256"],
                        "preview_sha256":preview_hash})
    if not results:
        raise ValueError("No successfully rendered, source-backed figures found")
    result = {"llm_calls":0, "figures":results,
              "all_previews_identical":all(item["preview_identical"] for item in results)}
    (destination / "replay.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    print(json.dumps(replay(args.run, args.output, args.rscript, args.timeout), indent=2))
    raise SystemExit(0 if json.loads((args.output / "replay.json").read_text())["all_previews_identical"] else 1)
