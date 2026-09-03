"""Download a ModelScope repo snapshot over HTTP (China-friendly, no Hub client)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import httpx

from research_mentor.hyperparameters import MODELSCOPE_ENDPOINT

_USER_AGENT = "research-mentor-reranker-download"
_TIMEOUT = httpx.Timeout(connect=20.0, read=None, write=None, pool=20.0)
Progress = Callable[[str, int, int | None], None]


def modelscope_file_list_url(repo_id: str, revision: str = "master") -> str:
    return (
        f"{MODELSCOPE_ENDPOINT}/api/v1/models/{repo_id}/repo/files"
        f"?Revision={quote(revision)}&Recursive=True"
    )


def modelscope_resolve_url(repo_id: str, path: str, revision: str = "master") -> str:
    return (
        f"{MODELSCOPE_ENDPOINT}/models/{repo_id}/resolve/"
        f"{quote(revision, safe='')}/{quote(path, safe='/')}"
    )


def modelscope_snapshot_download(
    repo_id: str,
    local_dir: str | Path,
    *,
    revision: str = "master",
    client: httpx.Client | None = None,
    on_progress: Progress | None = None,
) -> Path:
    target = Path(local_dir)
    target.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            follow_redirects=True,
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
    try:
        listing = client.get(modelscope_file_list_url(repo_id, revision))
        listing.raise_for_status()
        payload = listing.json()
        files = (payload.get("Data") or {}).get("Files") or []
        blobs = [
            item
            for item in files
            if item.get("Type") == "blob" and item.get("Path")
        ]
        if not blobs:
            raise RuntimeError(f"ModelScope 未返回文件列表: {repo_id}")
        for item in blobs:
            rel = str(item["Path"])
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            expected = _int_or_none(item.get("Size"))
            if dest.is_file() and expected and dest.stat().st_size == expected:
                if on_progress is not None:
                    on_progress(rel, expected, expected)
                continue
            _stream_to_file(
                client,
                modelscope_resolve_url(repo_id, rel, revision),
                dest,
                expected_size=expected,
                on_progress=on_progress,
                label=rel,
            )
    finally:
        if owns_client:
            client.close()
    return target


def _stream_to_file(
    client: httpx.Client,
    url: str,
    dest: Path,
    *,
    expected_size: int | None,
    on_progress: Progress | None,
    label: str,
) -> None:
    tmp = dest.with_name(dest.name + ".part")
    headers: dict[str, str] = {}
    start = tmp.stat().st_size if tmp.is_file() else 0
    if start and expected_size and start >= expected_size:
        tmp.replace(dest)
        return
    if start:
        headers["Range"] = f"bytes={start}-"
    with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()
        append = start > 0 and response.status_code == 206
        if not append:
            start = 0
        downloaded = start
        mode = "ab" if append else "wb"
        with tmp.open(mode) as handle:
            for chunk in response.iter_bytes(1024 * 1024):
                handle.write(chunk)
                downloaded += len(chunk)
                if on_progress is not None:
                    on_progress(label, downloaded, expected_size)
    if expected_size and tmp.stat().st_size != expected_size:
        raise RuntimeError(
            f"ModelScope 下载不完整: {label} ({tmp.stat().st_size}/{expected_size})"
        )
    tmp.replace(dest)


def _int_or_none(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
