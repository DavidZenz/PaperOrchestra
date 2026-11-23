#!/usr/bin/env python3
"""Recheck a retained run's bibliography and provider-response hash bindings."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
from orchestra_bibliography import validate_library, validate_manuscript


def audit(output):
    output = Path(output).resolve()
    result = {"library": validate_library(output / "literature_agent_output"),
              "manuscript": validate_manuscript(output / "content_refinement_workdir",
                  "final_refined_paper", output / "literature_agent_output/citation_map.json")}
    if (output / "final_paper.pdf").read_bytes() != (output / "content_refinement_workdir/final_refined_paper.pdf").read_bytes():
        raise ValueError("Published PDF differs from audited final PDF")
    providers = {}
    records = 0
    for line in (output / "execution/trace.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event.get("event") != "reference_retrieval":
            continue
        path = output / "execution/reference_retrieval" / Path(event["path"]).name
        if hashlib.sha256(path.read_bytes()).hexdigest() != event["sha256"]:
            raise ValueError("Provider receipt checksum mismatch: " + str(path))
        record = json.loads(path.read_text())
        records += 1
        if record["event"] == "reference_selected":
            provider = record["provider"]
            providers[provider] = providers.get(provider, 0) + 1
    if not providers:
        raise ValueError("No verified provider selection evidence")
    result.update(provider_selections=providers, hash_checked_retrieval_records=records, valid=True)
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(audit(sys.argv[1]), indent=2))
    except Exception as exc:
        print(json.dumps({"valid": False, "error": str(exc)}))
        sys.exit(1)
