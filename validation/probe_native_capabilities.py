"""Bounded live native transport checks, not a scientific paper/workflow run.

Each selected check makes one direct role attempt. Failures are retained; this
component diagnostic never claims to exercise the controller's retry policies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, default=Path(__file__).resolve().parents[1] / "paper-orchestra")
    parser.add_argument("--backend", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--checks", nargs="+", choices=["text", "image", "search"], default=["text", "image", "search"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--rscript", default="/opt/homebrew/opt/r/bin/Rscript")
    args = parser.parse_args()
    skill = args.skill.resolve()
    sys.path[:0] = [str(skill / "vendor"), str(skill / "scripts")]
    from google.genai import types
    from orchestra_runtime import Runtime, role_override
    from orchestra_transports import inspect_invocation
    from utils.gemini_utils import parse_gemini_json_results
    from bundle import manifest
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use a fresh output directory")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(output / "execution", backend=args.backend, model=args.model, effort=args.effort, timeout=args.timeout)
    report = {"kind":"live native transport component checks, one direct attempt per check; not a paper run",
              "backend":args.backend, "model":args.model, "effort":args.effort, "checks":[],
              "skill_path":str(skill), "skill_bundle_at_start":manifest(skill)}
    for check in args.checks:
        try:
            config = {}
            role = "runtime-probe"
            contents = ["Reply exactly PAPER_ORCHESTRA_RUNTIME_OK. Use no tools."]
            if check == "image":
                source = output / "fixture.R"
                source.write_text('library(ggplot2)\nset.seed(0)\nd <- data.frame(label=c("A","B","C"), value=c(7,11,3))\np <- ggplot(d,aes(label,value)) + geom_col(fill="steelblue") + geom_text(aes(label=value),vjust=-0.2,size=8) + ylim(0,14) + theme_classic(base_size=22) + labs(x="Bar",y="Height")\nggsave("fixture.png",p,width=6,height=4,dpi=120)\nwriteLines(capture.output(sessionInfo()),"sessionInfo.txt")\n')
                subprocess.run([args.rscript,"--vanilla",str(source)],cwd=output,check=True,capture_output=True,timeout=30)
                image = output / "fixture.png"
                role = "figure-critic"
                contents = [types.Part.from_text(text='Read the attached plot. Return only JSON {"bar_B":NUMBER}, giving the height of bar B. Do not use tools.'),
                            types.Part.from_bytes(data=image.read_bytes(),mime_type="image/png")]
            elif check == "search":
                role = "literature-discovery"
                contents = ['Use live web search to find the original PaperOrchestra research paper. Return only JSON with keys title, authors (list), arxiv_url.']
                config = {"tools":[{"google_search":{}}]}
            token = role_override.set(role)
            try:
                raw = runtime.generate(contents,config,"runtime-probe" if check == "text" else "gemini-3.1-pro-preview").text
            finally:
                role_override.reset(token)
            invocations = sorted((runtime.root / "invocations").iterdir(),key=lambda p:p.stat().st_mtime_ns)
            directory = invocations[-1]
            request = json.loads((directory / "request.json").read_text())
            receipt = inspect_invocation(directory,request)
            if not receipt["completed"]:
                raise ValueError("Native completion proof is invalid")
            if check == "text":
                assert raw.strip() == "PAPER_ORCHESTRA_RUNTIME_OK", "Unexpected fixed response"
            else:
                # Use the exact upstream parser, including fenced-JSON handling;
                # original worker text remains a separate retained artifact.
                value = parse_gemini_json_results(raw)
                assert isinstance(value,dict), "Original upstream parser rejected native response"
                if check == "image":
                    assert value.get("bar_B") == 11, "Native worker did not read the image correctly"
                    assert receipt["images_delivered"] == request["images"], "Missing native image receipt"
                else:
                    assert receipt["searched"], "No completed native search call/result"
                    assert "paperorchestra" in value["title"].lower() and "2604.05018" in value["arxiv_url"], "Wrong original paper"
            report["checks"].append({"check":check,"status":"passed","invocation":directory.name,
                                      "native_receipt":receipt,"response_sha256":hashlib.sha256(raw.encode()).hexdigest()})
        except Exception as exc:
            report["checks"].append({"check":check,"status":"failed","error":str(exc)})
        (output / "probe.json").write_text(json.dumps(report,indent=2)+"\n")
    report["skill_bundle_at_finish"] = manifest(skill)
    report["skill_unchanged"] = report["skill_bundle_at_finish"] == report["skill_bundle_at_start"]
    report["status"] = "passed" if all(x["status"] == "passed" for x in report["checks"]) else "failed"
    (output / "probe.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"backend":args.backend,"status":report["status"],"checks":[{k:x[k] for k in ("check","status")} for x in report["checks"]]},indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
