"""Preflight or execute an explicitly approved Zotero item mutation plan."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

RESEARCHOS_ROOT = Path(__file__).resolve().parents[3]
if str(RESEARCHOS_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCHOS_ROOT))

from tools.researchos_outputs import A001_LIBRARY_GOVERNANCE, find_researchos_root
from tools.zotero.write.mutation_contract import load_plan
from tools.zotero.write.mutation_executor import execute_plan, select_actions
from tools.zotero.write.zotero_web_api import env_config, fetch_web_api_paged, selected_proxy
from tools.zotero.write.zotero_web_api import zotero_request as shared_zotero_request


RUNS_DIR = A001_LIBRARY_GOVERNANCE / "zotero-item-mutation-runs"


class ZoteroApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--item-key")
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--root")
    return parser


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else find_researchos_root(Path(__file__))
    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = root / plan_path
    plan = load_plan(plan_path)
    actions = select_actions(plan, args.item_key, args.max_items)
    config = env_config()
    opener, proxy_info = selected_proxy()

    def request(method: str, endpoint: str, body: Any | None, headers: dict[str, str] | None):
        return shared_zotero_request(config, method, endpoint, body, headers, opener, error_cls=ZoteroApiError)

    def paged_request(cfg: dict[str, str], method: str, path: str, body: Any | None, headers: dict[str, str] | None):
        return shared_zotero_request(cfg, method, path, body, headers, opener, error_cls=ZoteroApiError)

    collections = fetch_web_api_paged(config, "collections", request_fn=paged_request, error_cls=ZoteroApiError)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = root / RUNS_DIR / f"{stamp}-{'write' if args.write else 'preflight'}"
    summary = execute_plan(plan, actions, collections, request, run_dir, args.write, proxy_info)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["blocked_rows"] == 0 else 2


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
