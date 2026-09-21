#!/usr/bin/env python3
"""Offline, receipt-based installation of the self-contained drama-studio skill."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "drama-studio"
NAME = "drama-studio"
RECEIPT = ".drama-studio-install.json"


class InstallError(Exception):
    pass


def inventory(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise InstallError(f"Expected a real skill directory: {root}")
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise InstallError(f"Symlink inside skill: {relative}")
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_file() and str(relative) != RECEIPT:
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.is_file() and not path.is_dir():
            raise InstallError(f"Unsupported file type: {relative}")
    return files


def payload(host: str = "generic") -> dict[str, bytes]:
    files = {name: (SOURCE / name).read_bytes() for name in inventory(SOURCE)}
    if host == "workbuddy":
        original = files["SKILL.md"].decode("utf-8")
        version = (ROOT / "VERSION").read_text().strip()
        fields = ("description_zh: 短剧市场研究、对标拉片与原创剧本创作工作流\n"
                  "description_en: Research short dramas and develop original screenplays with mali-story.\n"
                  f"version: {version}\nauthor: Drama Studio\n")
        files["SKILL.md"] = original.replace("\n---\n", "\n" + fields + "---\n", 1).encode("utf-8")
    return files


def hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


def destination(args) -> Path:
    if args.host == "chatgpt":
        raise InstallError("ChatGPT requires skill import and remote MCP setup; use package and docs/hosts.md")
    if args.skills_dir:
        if args.project or args.scope != "user":
            raise InstallError("Use --skills-dir by itself, without --project or --scope project")
        base = Path(args.skills_dir).expanduser().absolute()
    else:
        if args.host == "workbuddy":
            raise InstallError("Confirm WorkBuddy's current skill directory and pass --skills-dir, or use package")
        folder = ".agents" if args.host == "codex" else ".claude"
        if args.scope == "project":
            if not args.project:
                raise InstallError("--scope project requires --project")
            base = Path(args.project).expanduser().absolute() / folder / "skills"
        else:
            if args.project:
                raise InstallError("--project requires --scope project")
            base = Path.home() / folder / "skills"
    target = base / NAME
    if target.resolve() == SOURCE.resolve():
        raise InstallError("Installation target must differ from the source skill")
    return target


def inspect_target(target: Path) -> dict:
    if target.is_symlink():
        raise InstallError("Refusing a symlink installation target")
    if not target.exists():
        return {"state": "absent"}
    if not target.is_dir():
        raise InstallError("Installation target is not a directory")
    receipt_path = target / RECEIPT
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise InstallError("Existing directory has no owned installation receipt; preserve it")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise InstallError("Invalid installation receipt; preserve the existing directory") from error
    if not isinstance(receipt, dict) or receipt.get("name") != NAME or not isinstance(receipt.get("files"), dict):
        raise InstallError("Unrecognized installation receipt")
    current = inventory(target)
    if current != receipt["files"]:
        changed = sorted(key for key in set(current) | set(receipt["files"])
                         if current.get(key) != receipt["files"].get(key))
        raise InstallError("Local skill modifications detected; preserve them: " + ", ".join(changed))
    return {"state": "installed", "version": receipt.get("version"), "files": current}


def plan(args) -> dict:
    target = destination(args)
    files = hashes(payload(args.host))
    if "SKILL.md" not in files or "scripts/drama_tools.py" not in files:
        raise InstallError("Incomplete source skill")
    existing = inspect_target(target)
    action = "install" if existing["state"] == "absent" else (
        "unchanged" if existing["files"] == files else "upgrade_required")
    return {"ok": True, "action": action, "host": args.host,
            "destination": str(target), "file_count": len(files),
            "version": (ROOT / "VERSION").read_text().strip(),
            "remote_mcp": "not_checked", "host_discovery": "not_checked"}


def install(args) -> dict:
    initial = plan(args)
    if initial["action"] == "unchanged":
        return initial
    if initial["action"] == "upgrade_required" and not args.upgrade:
        raise InstallError("Use --upgrade to replace an unchanged owned installation; the prior version is retained")
    target = Path(initial["destination"])
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / ".drama-studio-install.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise InstallError("Another install may be running; inspect the lock before retrying") from error
    stage = None
    backup = None
    try:
        os.close(descriptor)
        current = plan(args)
        if current["action"] == "unchanged":
            return current
        if current["action"] == "upgrade_required" and not args.upgrade:
            raise InstallError("The destination changed; run plan again")
        contents = payload(args.host)
        files = hashes(contents)
        stage = Path(tempfile.mkdtemp(prefix=".drama-studio-stage-", dir=target.parent))
        for name in files:
            output = stage / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(contents[name])
        if inventory(stage) != files:
            raise InstallError("Source changed while copying; retry from a stable checkout")
        (stage / RECEIPT).write_text(json.dumps({"name": NAME, "version": current["version"],
                                                "files": files}, indent=2) + "\n", encoding="utf-8")
        if target.exists():
            inspect_target(target)
            backup = target.parent / (".drama-studio-backup-" + uuid.uuid4().hex)
            target.rename(backup)
        try:
            stage.rename(target)
            stage = None
        except OSError:
            if backup is not None and not target.exists():
                backup.rename(target)
            raise
        return {**current, "action": "upgraded" if backup else "installed",
                "backup": str(backup) if backup else None}
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        lock.unlink()


def verify(args) -> dict:
    target = destination(args)
    observed = inspect_target(target)
    if observed["state"] == "absent":
        raise InstallError("Skill is not installed at the selected destination")
    result = subprocess.run([sys.executable, "-B", str(target / "scripts" / "drama_tools.py"), "doctor"],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise InstallError("Installed offline tool self-check failed: " + (result.stderr or result.stdout).strip())
    return {"ok": True, "destination": str(target), "version": observed["version"],
            "files_verified": len(observed["files"]), "offline_tools": json.loads(result.stdout),
            "matches_checkout": observed["files"] == hashes(payload(args.host)),
            "host_discovery": "not_checked", "remote_mcp": "not_checked",
            "next": "Ask the host to discover drama-studio, then follow references/mali-story.md"}


def package(output: Path, host: str = "generic") -> dict:
    files = payload(host)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, files[name])
    content = buffer.getvalue()
    output = output.expanduser().absolute()
    if output.is_symlink():
        raise InstallError("Refusing a symlink archive destination")
    if output.exists():
        if output.is_file() and output.read_bytes() == content:
            return {"ok": True, "action": "unchanged", "archive": str(output)}
        raise InstallError("Archive already exists with different content; choose a new output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(content)
    return {"ok": True, "archive": str(output), "sha256": hashlib.sha256(content).hexdigest(),
            "files": len(files), "kind": "skill_bundle", "host_import": "not_checked"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "install", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--host", choices=["codex", "claude-code", "workbuddy", "chatgpt"], required=True)
        command.add_argument("--scope", choices=["user", "project"], default="user")
        command.add_argument("--project")
        command.add_argument("--skills-dir", help="An explicitly confirmed host skills directory")
        if name == "install":
            command.add_argument("--upgrade", action="store_true")
    command = commands.add_parser("package")
    command.add_argument("--host", choices=["generic", "chatgpt", "workbuddy"], default="generic")
    command.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 10):
            raise InstallError("Python 3.10 or later is required")
        result = package(args.output or ROOT / "dist" / f"drama-studio-{args.host}.zip", args.host) if args.command == "package" else globals()[args.command](args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (InstallError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
