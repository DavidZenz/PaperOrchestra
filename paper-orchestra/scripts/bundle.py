"""Content-addressed skill snapshots; runtime output never enters the skill bundle."""
import hashlib
import json
from pathlib import Path
import shutil


def manifest(root):
    root = Path(root).resolve()
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and path.name != ".DS_Store":
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"sha256":digest, "files":files}


def snapshot(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    description = manifest(root)
    for relative in description["files"]:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    if manifest(destination) != description or manifest(root) != description:
        raise RuntimeError("Skill changed while recording its snapshot")
    return description
