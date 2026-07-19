"""Compute a deterministic, read-only snapshot identifier for shared corpus content."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 1
DEFAULT_ZONES = (
    "zotero",
    "fulltext",
    "reading-cards/cards",
    "reading-cards/indexes",
)
EXCLUDED_SUFFIXES = ("-wal", "-shm", ".writer.lock", ".tmp")


class CorpusSnapshotError(RuntimeError):
    """Raised when a shared corpus snapshot cannot be computed safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_zone_files(zone_root: Path) -> Iterable[Path]:
    seen_directories: set[str] = set()
    for current, dirnames, filenames in os.walk(zone_root, followlinks=True):
        current_path = Path(current)
        resolved_key = os.path.normcase(str(current_path.resolve()))
        if resolved_key in seen_directories:
            dirnames[:] = []
            continue
        seen_directories.add(resolved_key)
        safe_dirs: list[str] = []
        for name in dirnames:
            child = current_path / name
            try:
                child_key = os.path.normcase(str(child.resolve()))
            except OSError:
                continue
            if child_key not in seen_directories:
                safe_dirs.append(name)
        dirnames[:] = safe_dirs
        for name in filenames:
            path = current_path / name
            if name.endswith(EXCLUDED_SUFFIXES) or path.is_symlink() or not path.is_file():
                continue
            yield path


def compute_snapshot(corpus_root: Path, zones: tuple[str, ...] = DEFAULT_ZONES) -> dict[str, object]:
    root = corpus_root.resolve()
    if not root.is_dir():
        raise CorpusSnapshotError("Shared corpus root does not exist")
    aggregate = hashlib.sha256()
    zone_results: dict[str, dict[str, object]] = {}
    total_files = 0
    total_bytes = 0
    for zone_name in zones:
        zone_root = corpus_root / Path(zone_name)
        if not zone_root.exists() or not zone_root.is_dir():
            raise CorpusSnapshotError(f"Required shared corpus zone is missing: {zone_name}")
        rows: list[tuple[str, int, str]] = []
        for path in iter_zone_files(zone_root):
            relative = path.relative_to(zone_root).as_posix()
            size = path.stat().st_size
            rows.append((relative, size, sha256_file(path)))
        rows.sort(key=lambda row: row[0])
        zone_digest = hashlib.sha256()
        for relative, size, file_hash in rows:
            record = f"{zone_name}\0{relative}\0{size}\0{file_hash}\n".encode("utf-8")
            zone_digest.update(record)
            aggregate.update(record)
        zone_bytes = sum(row[1] for row in rows)
        zone_results[zone_name] = {
            "file_count": len(rows),
            "bytes": zone_bytes,
            "content_hash": zone_digest.hexdigest(),
        }
        total_files += len(rows)
        total_bytes += zone_bytes
    content_hash = aggregate.hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "researchos_shared_corpus_snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_id": f"corpus-{content_hash[:16]}",
        "content_hash": content_hash,
        "file_count": total_files,
        "bytes": total_bytes,
        "zones": zone_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", default="corpus")
    args = parser.parse_args(argv)
    try:
        result = compute_snapshot(Path(args.corpus_root))
    except CorpusSnapshotError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
