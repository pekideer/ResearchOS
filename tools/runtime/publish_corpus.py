"""Plan, apply, verify and roll back guarded shared-corpus publications.

Publication is fail-closed and manifest-committed. Files are replaced atomically
one by one; the release manifest is replaced last and is the commit record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

RESEARCHOS_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import A004_CORPUS_PUBLICATION, M006_ZOTERO_INGESTION_PIPELINE
from tools.runtime.terminal_roles import check_action, default_config_path, load_config


SCHEMA_VERSION = 1
DEFAULT_MANIFEST = PurePosixPath("zotero/M-001-zotero-library/current-corpus-release.json")
ALLOWED_PREFIXES = (
    PurePosixPath("zotero/M-001-zotero-library"),
    PurePosixPath("fulltext/zotero-library"),
    PurePosixPath("fulltext/zotero-library-normalized"),
    PurePosixPath("reading-cards/cards"),
    PurePosixPath("reading-cards/indexes"),
)


class CorpusPublicationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: dict[str, Any], excluded: Iterable[str] = ()) -> str:
    payload = {key: item for key, item in value.items() if key not in set(excluded)}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def safe_relative(value: str | PurePosixPath) -> PurePosixPath:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise CorpusPublicationError(f"Unsafe corpus-relative path: {value}")
    if not any(relative == prefix or prefix in relative.parents for prefix in ALLOWED_PREFIXES):
        raise CorpusPublicationError(f"Path is outside publishable corpus zones: {value}")
    return relative


def sqlite_quick_check(path: Path) -> None:
    if path.suffix.lower() not in {".sqlite", ".db"}:
        return
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        raise CorpusPublicationError(f"SQLite validation failed for {path.name}: {exc}") from exc
    if not result or result[0] != "ok":
        raise CorpusPublicationError(f"SQLite quick_check failed for {path.name}: {result}")


def staging_mappings(staging_root: Path) -> list[tuple[Path, PurePosixPath]]:
    root = staging_root.resolve()
    mappings: list[tuple[Path, PurePosixPath]] = []

    legacy = [
        (root / "zotero_library.sqlite", PurePosixPath("zotero/M-001-zotero-library/zotero_library.sqlite")),
    ]
    for source, target in legacy:
        if source.is_file():
            mappings.append((source, target))
    for source_base, target_base in [
        (root / "reading-cards" / "cards", PurePosixPath("reading-cards/cards")),
        (root / "reading-cards" / "indexes", PurePosixPath("reading-cards/indexes")),
    ]:
        if source_base.is_dir():
            mappings.extend((path, target_base / path.relative_to(source_base).as_posix()) for path in sorted(source_base.rglob("*")) if path.is_file())
    mirror = root / "corpus"
    if mirror.is_dir():
        mappings.extend((path, PurePosixPath(path.relative_to(mirror).as_posix())) for path in sorted(mirror.rglob("*")) if path.is_file())

    deduplicated: dict[str, tuple[Path, PurePosixPath]] = {}
    for source, target in mappings:
        resolved = source.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise CorpusPublicationError(f"Staging source escapes staging root: {source}") from exc
        safe_relative(target)
        key = target.as_posix()
        if key in deduplicated and deduplicated[key][0] != resolved:
            raise CorpusPublicationError(f"Duplicate staging target: {key}")
        deduplicated[key] = (resolved, target)
    return [deduplicated[key] for key in sorted(deduplicated)]


def build_plan(staging_root: Path, corpus_root: Path, manifest_relative: PurePosixPath = DEFAULT_MANIFEST) -> dict[str, Any]:
    staging = staging_root.resolve()
    corpus = corpus_root.absolute()
    if not staging.is_dir():
        raise CorpusPublicationError("Staging root is missing")
    entries: list[dict[str, Any]] = []
    for source, relative in staging_mappings(staging):
        sqlite_quick_check(source)
        target = corpus / Path(*relative.parts)
        source_hash = sha256_file(source)
        baseline_hash = sha256_file(target) if target.is_file() else None
        if source_hash == baseline_hash:
            continue
        entries.append({
            "source": str(source),
            "target": relative.as_posix(),
            "size": source.stat().st_size,
            "sha256": source_hash,
            "baseline_sha256": baseline_hash,
        })
    if not entries:
        raise CorpusPublicationError("Staging contains no publishable files")
    safe_relative(manifest_relative)
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "action": "corpus-publication",
        "generated_at": utc_now(),
        "staging_root": str(staging),
        "corpus_root": str(corpus),
        "manifest": manifest_relative.as_posix(),
        "files": entries,
        "deletions": [],
        "apply_required": True,
    }
    plan["plan_hash"] = canonical_hash(plan, {"plan_hash"})
    plan["release_id"] = f"corpus-{plan['plan_hash'][:16]}"
    return plan


def load_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusPublicationError("Publication plan is unreadable") from exc
    if not isinstance(plan, dict) or plan.get("schema_version") != SCHEMA_VERSION:
        raise CorpusPublicationError("Unsupported publication plan")
    expected = canonical_hash(plan, {"plan_hash", "release_id"})
    # release_id is derived after the original plan hash and is not signed separately.
    unsigned = dict(plan)
    unsigned.pop("release_id", None)
    expected = canonical_hash(unsigned, {"plan_hash"})
    if plan.get("plan_hash") != expected or plan.get("release_id") != f"corpus-{expected[:16]}":
        raise CorpusPublicationError("Publication plan hash is invalid")
    return plan


def validate_entry(entry: dict[str, Any], corpus_root: Path) -> tuple[Path, Path, PurePosixPath]:
    relative = safe_relative(str(entry.get("target") or ""))
    source = Path(str(entry.get("source") or "")).resolve()
    staging = Path(str(entry.get("_staging_root") or source.parent)).resolve()
    try:
        source.relative_to(staging)
    except ValueError as exc:
        raise CorpusPublicationError(f"Staging source escapes the planned root: {relative}") from exc
    target = corpus_root / Path(*relative.parts)
    if not source.is_file() or sha256_file(source) != entry.get("sha256") or source.stat().st_size != entry.get("size"):
        raise CorpusPublicationError(f"Staging file changed after planning: {relative}")
    sqlite_quick_check(source)
    current = sha256_file(target) if target.is_file() else None
    if current != entry.get("baseline_sha256"):
        raise CorpusPublicationError(f"Corpus baseline changed after planning: {relative}")
    return source, target, relative


def validate_plan_state(plan: dict[str, Any]) -> dict[str, Any]:
    corpus_root = Path(str(plan["corpus_root"])).absolute()
    staging_root = Path(str(plan["staging_root"])).resolve()
    for raw in plan["files"]:
        entry = dict(raw)
        entry["_staging_root"] = str(staging_root)
        validate_entry(entry, corpus_root)
    return {"validated": True, "release_id": plan["release_id"], "files": len(plan["files"]), "apply_required": True}


def apply_plan(plan: dict[str, Any], role_config: Path, archive_root: Path) -> dict[str, Any]:
    check_action(load_config(role_config), "corpus-write")
    corpus_root = Path(str(plan["corpus_root"])).absolute()
    staging_root = Path(str(plan["staging_root"])).resolve()
    archive = archive_root.resolve() / str(plan["release_id"])
    if archive.exists():
        raise CorpusPublicationError("Release archive already exists")
    archive.mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    replaced: list[dict[str, Any]] = []
    manifest_path = corpus_root / Path(*PurePosixPath(plan["manifest"]).parts)
    old_manifest = archive / "before-manifest.json"
    manifest_replaced = False
    try:
        for raw in plan["files"]:
            entry = dict(raw)
            entry["_staging_root"] = str(staging_root)
            source, target, relative = validate_entry(entry, corpus_root)
            backup = archive / "before" / Path(*relative.parts)
            existed = target.is_file()
            if existed:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            os.close(fd)
            temporary = Path(temporary_name)
            try:
                shutil.copy2(source, temporary)
                if sha256_file(temporary) != raw["sha256"]:
                    raise CorpusPublicationError(f"Temporary copy hash mismatch: {relative}")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            sqlite_quick_check(target)
            replaced.append({"target": target, "backup": backup, "existed": existed})
            entries.append({"path": relative.as_posix(), "size": raw["size"], "sha256": raw["sha256"]})

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "release_id": plan["release_id"],
            "plan_hash": plan["plan_hash"],
            "committed_at": utc_now(),
            "files": entries,
        }
        if manifest_path.is_file():
            shutil.copy2(manifest_path, old_manifest)
        write_json_atomic(manifest_path, manifest)
        manifest_replaced = True
        rollback = {
            "schema_version": SCHEMA_VERSION,
            "action": "corpus-publication-rollback",
            "release_id": plan["release_id"],
            "corpus_root": str(corpus_root),
            "manifest": plan["manifest"],
            "old_manifest": str(old_manifest) if old_manifest.exists() else None,
            "files": [
                {"target": item["target"].relative_to(corpus_root).as_posix(), "backup": str(item["backup"]) if item["existed"] else None, "expected_sha256": sha256_file(item["target"])}
                for item in replaced
            ],
            "apply_required": True,
        }
        rollback["plan_hash"] = canonical_hash(rollback, {"plan_hash"})
        write_json_atomic(archive / "publication-plan.json", plan)
        write_json_atomic(archive / "release-manifest.json", manifest)
        write_json_atomic(archive / "rollback-plan.json", rollback)
        verify_manifest(corpus_root, manifest_path)
        return {"applied": True, "release_id": plan["release_id"], "files": len(entries), "manifest": str(manifest_path), "archive": str(archive)}
    except BaseException:
        if manifest_replaced:
            if old_manifest.is_file():
                shutil.copy2(old_manifest, manifest_path.with_name(manifest_path.name + ".restore.tmp"))
                os.replace(manifest_path.with_name(manifest_path.name + ".restore.tmp"), manifest_path)
            else:
                manifest_path.unlink(missing_ok=True)
        for item in reversed(replaced):
            if item["existed"]:
                os.replace(item["backup"], item["target"])
            else:
                item["target"].unlink(missing_ok=True)
        raise


def verify_manifest(corpus_root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    root = corpus_root.absolute()
    path = manifest_path or root / Path(*DEFAULT_MANIFEST.parts)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusPublicationError("Committed corpus manifest is missing or invalid") from exc
    failures: list[str] = []
    for entry in manifest.get("files", []):
        relative = safe_relative(str(entry.get("path") or ""))
        target = root / Path(*relative.parts)
        if not target.is_file() or target.stat().st_size != entry.get("size") or sha256_file(target) != entry.get("sha256"):
            failures.append(relative.as_posix())
            continue
        try:
            sqlite_quick_check(target)
        except CorpusPublicationError:
            failures.append(relative.as_posix())
    if failures:
        raise CorpusPublicationError("Committed corpus release is incomplete or mixed: " + ", ".join(failures))
    return {"valid": True, "release_id": manifest.get("release_id"), "files": len(manifest.get("files", [])), "manifest": str(path)}


def apply_rollback(plan: dict[str, Any], role_config: Path) -> dict[str, Any]:
    check_action(load_config(role_config), "corpus-write")
    if plan.get("action") != "corpus-publication-rollback" or canonical_hash(plan, {"plan_hash"}) != plan.get("plan_hash"):
        raise CorpusPublicationError("Rollback plan is invalid")
    root = Path(str(plan["corpus_root"])).absolute()
    validated: list[tuple[Path, Path | None]] = []
    for entry in plan["files"]:
        relative = safe_relative(entry["target"])
        target = root / Path(*relative.parts)
        if not target.is_file() or sha256_file(target) != entry["expected_sha256"]:
            raise CorpusPublicationError(f"Rollback target changed: {relative}")
        backup = Path(entry["backup"]).resolve() if entry.get("backup") else None
        if backup and not backup.is_file():
            raise CorpusPublicationError(f"Rollback backup missing: {relative}")
        validated.append((target, backup))
    for target, backup in reversed(validated):
        if backup:
            temporary = target.with_name(target.name + f".{os.getpid()}.rollback.tmp")
            shutil.copy2(backup, temporary)
            os.replace(temporary, target)
        else:
            target.unlink()
    manifest_path = root / Path(*PurePosixPath(plan["manifest"]).parts)
    old_manifest = Path(plan["old_manifest"]) if plan.get("old_manifest") else None
    if old_manifest and old_manifest.is_file():
        shutil.copy2(old_manifest, manifest_path.with_name(manifest_path.name + ".rollback.tmp"))
        os.replace(manifest_path.with_name(manifest_path.name + ".rollback.tmp"), manifest_path)
    else:
        manifest_path.unlink(missing_ok=True)
    return {"rolled_back": True, "release_id": plan["release_id"], "files": len(validated)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-config", type=Path, default=default_config_path())
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--staging-root", type=Path, required=True)
    plan.add_argument("--corpus-root", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--archive-root", type=Path)
    apply.add_argument("--apply", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--corpus-root", type=Path, required=True)
    verify.add_argument("--manifest", type=Path)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--plan", type=Path, required=True)
    rollback.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "plan":
            result = build_plan(args.staging_root, args.corpus_root)
            write_json_atomic(args.output.resolve(), result)
            output: dict[str, Any] = {"planned": True, "plan": str(args.output.resolve()), "release_id": result["release_id"], "files": len(result["files"]), "apply_required": True}
        elif args.command == "apply":
            plan = load_plan(args.plan.resolve())
            if not args.apply:
                output = validate_plan_state(plan)
            else:
                agent_root = Path(__file__).resolve().parents[2]
                archive_root = args.archive_root.resolve() if args.archive_root else agent_root / A004_CORPUS_PUBLICATION
                output = apply_plan(plan, args.role_config.resolve(), archive_root)
        elif args.command == "verify":
            output = verify_manifest(args.corpus_root, args.manifest.resolve() if args.manifest else None)
        else:
            plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
            output = {"validated": True, "release_id": plan.get("release_id"), "apply_required": True} if not args.apply else apply_rollback(plan, args.role_config.resolve())
    except (CorpusPublicationError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
