"""Programmatic ingestion with a local cache and bundled offline fallback."""

from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    CACHE_METADATA_PATH,
    CACHE_SAMPLE_PATH,
    DATASET_API_URL,
    FALLBACK_SAMPLE_PATH,
    MAX_SAMPLE_ROWS,
    ensure_data_directories,
)


@dataclass(frozen=True)
class IngestResult:
    """A raw dataset and the provenance needed by the audit log."""

    frame: pd.DataFrame
    source_kind: str
    source_url: str
    source_name: str
    retrieved_at: datetime
    notice: str = ""


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _request_bytes(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - URL is fixed/configured HTTPS.
        url,
        headers={"User-Agent": "TrustLayer-Data-Reliability-Copilot/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def _resource_year(resource: dict[str, Any]) -> int:
    text = " ".join(
        str(resource.get(key, "")) for key in ("name", "url", "last_modified", "created")
    )
    years = [int(value) for value in re.findall(r"(?:19|20)\d{2}", text)]
    return max(years, default=0)


def _select_latest_tabular_resource(resources: list[dict[str, Any]]) -> dict[str, Any]:
    supported = {"CSV", "XLSX", "XLS", "ZIP"}
    candidates = [
        resource
        for resource in resources
        if str(resource.get("format", "")).upper() in supported and resource.get("url")
    ]
    if not candidates:
        raise ValueError("Toronto Open Data returned no supported tabular resources.")

    format_rank = {"CSV": 3, "XLSX": 2, "XLS": 1, "ZIP": 0}
    return max(
        candidates,
        key=lambda item: (
            _resource_year(item),
            str(item.get("last_modified") or item.get("created") or ""),
            format_rank.get(str(item.get("format", "")).upper(), -1),
        ),
    )


def _read_excel_workbook(payload: bytes) -> pd.DataFrame:
    sheets = pd.read_excel(io.BytesIO(payload), sheet_name=None)
    usable = [frame for frame in sheets.values() if not frame.empty]
    if not usable:
        raise ValueError("The downloaded workbook did not contain any data rows.")
    return pd.concat(usable, ignore_index=True, sort=False)


def _read_zip(payload: bytes) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        for name in names:
            suffix = Path(name).suffix.lower()
            with archive.open(name) as resource:
                item = resource.read()
            if suffix == ".csv":
                frames.append(pd.read_csv(io.BytesIO(item)))
            elif suffix in {".xlsx", ".xls"}:
                frames.append(_read_excel_workbook(item))
    if not frames:
        raise ValueError("The downloaded archive had no readable CSV or Excel files.")
    return pd.concat(frames, ignore_index=True, sort=False)


def _read_resource(payload: bytes, resource_format: str, url: str) -> pd.DataFrame:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    kind = resource_format.upper()
    if kind == "CSV" or suffix == ".csv":
        return pd.read_csv(io.BytesIO(payload))
    if kind in {"XLSX", "XLS"} or suffix in {".xlsx", ".xls"}:
        return _read_excel_workbook(payload)
    if kind == "ZIP" or suffix == ".zip":
        return _read_zip(payload)
    raise ValueError(f"Unsupported Toronto resource format: {resource_format or suffix}")


def _date_sort_column(frame: pd.DataFrame) -> str | None:
    for column in frame.columns:
        normalized = re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
        if normalized in {"date", "report_date", "incident_date"}:
            return str(column)
    return None


def _manageable_sample(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the newest rows so freshness checks describe the current source resource."""

    if frame.empty:
        raise ValueError("The downloaded resource was empty.")
    working = frame.copy()
    date_column = _date_sort_column(working)
    if date_column:
        working["__trustlayer_sort_date"] = pd.to_datetime(working[date_column], errors="coerce")
        working = working.sort_values("__trustlayer_sort_date", ascending=False).drop(
            columns="__trustlayer_sort_date"
        )
    return working.head(MAX_SAMPLE_ROWS).reset_index(drop=True)


def _write_cache(frame: pd.DataFrame, metadata: dict[str, Any]) -> None:
    ensure_data_directories()
    frame.to_csv(CACHE_SAMPLE_PATH, index=False)
    CACHE_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _load_cache() -> IngestResult:
    frame = pd.read_csv(CACHE_SAMPLE_PATH)
    metadata: dict[str, Any] = {}
    if CACHE_METADATA_PATH.exists():
        metadata = json.loads(CACHE_METADATA_PATH.read_text(encoding="utf-8"))
    return IngestResult(
        frame=frame,
        source_kind="cache",
        source_url=str(metadata.get("source_url", "")),
        source_name=str(metadata.get("source_name", CACHE_SAMPLE_PATH.name)),
        retrieved_at=_utc_now(),
        notice="Using the locally cached Toronto Open Data sample.",
    )


def _load_fallback(reason: str = "") -> IngestResult:
    if not FALLBACK_SAMPLE_PATH.exists():
        raise FileNotFoundError(f"Bundled fallback dataset not found: {FALLBACK_SAMPLE_PATH}")
    notice = "Using the bundled offline fallback sample."
    if reason:
        notice = f"{notice} Remote/cache reason: {reason}"
    return IngestResult(
        frame=pd.read_csv(FALLBACK_SAMPLE_PATH),
        source_kind="fallback",
        source_url="",
        source_name=FALLBACK_SAMPLE_PATH.name,
        retrieved_at=_utc_now(),
        notice=notice,
    )


def fetch_dataset(*, force_refresh: bool = False, offline: bool = False) -> IngestResult:
    """Fetch the newest official resource, falling back to cache and bundled data."""

    ensure_data_directories()
    if offline:
        if CACHE_SAMPLE_PATH.exists():
            return _load_cache()
        return _load_fallback("offline mode requested")

    if CACHE_SAMPLE_PATH.exists() and not force_refresh:
        return _load_cache()

    try:
        package_payload = json.loads(_request_bytes(DATASET_API_URL).decode("utf-8"))
        if not package_payload.get("success"):
            raise ValueError("Toronto Open Data package API reported an unsuccessful response.")
        package = package_payload["result"]
        resource = _select_latest_tabular_resource(package.get("resources", []))
        resource_url = str(resource["url"])
        resource_name = str(resource.get("name") or Path(resource_url).name)
        frame = _manageable_sample(
            _read_resource(
                _request_bytes(resource_url, timeout=60),
                str(resource.get("format", "")),
                resource_url,
            )
        )
        retrieved_at = _utc_now()
        _write_cache(
            frame,
            {
                "dataset_title": package.get("title", "TTC Subway Delay Data"),
                "source_url": resource_url,
                "source_name": resource_name,
                "resource_format": resource.get("format", ""),
                "resource_last_modified": resource.get("last_modified"),
                "retrieved_at": retrieved_at.isoformat(),
                "sample_rows": len(frame),
            },
        )
        return IngestResult(
            frame=frame,
            source_kind="remote",
            source_url=resource_url,
            source_name=resource_name,
            retrieved_at=retrieved_at,
            notice=f"Downloaded the latest tabular resource and cached {len(frame):,} rows.",
        )
    except Exception as exc:
        if CACHE_SAMPLE_PATH.exists():
            cached = _load_cache()
            return IngestResult(
                frame=cached.frame,
                source_kind=cached.source_kind,
                source_url=cached.source_url,
                source_name=cached.source_name,
                retrieved_at=cached.retrieved_at,
                notice=f"Remote fetch failed ({exc}); using the local cache.",
            )
        return _load_fallback(str(exc))
