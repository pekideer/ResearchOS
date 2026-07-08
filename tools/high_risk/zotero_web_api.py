"""Shared narrow helpers for guarded Zotero Web API workflows."""

from __future__ import annotations

from typing import Any, Callable


WebApiRequest = Callable[[dict[str, str], str, str, Any | None, dict[str, str] | None], tuple[int, dict[str, str], Any]]


def fetch_web_api_paged(
    config: dict[str, str],
    endpoint: str,
    request_fn: WebApiRequest,
    error_cls: type[Exception] = RuntimeError,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch paginated Zotero Web API rows through a caller-owned request function."""
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        separator = "&" if "?" in endpoint else "?"
        status, headers, payload = request_fn(config, "GET", f"{endpoint}{separator}limit={limit}&start={start}", None, None)
        if status != 200:
            raise error_cls(status, f"Unexpected status for {endpoint}")
        batch = payload or []
        rows.extend(batch)
        total = int(headers.get("Total-Results", len(rows)))
        start += len(batch)
        if not batch or start >= total:
            break
    return rows
