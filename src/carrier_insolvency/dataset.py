"""Load and serialize the dataset — ``load`` / ``to_json`` / ``to_csv``.

The dataset artifact ships at ``data/events.json`` in the repo root. ``load``
reads it (or any path you point it at) and returns validated
``InsolvencyEvent`` records; ``to_json`` / ``to_csv`` serialize records back out.
All deterministic, stdlib only, no network.

The on-disk JSON shape is::

    {
      "schema_version": 1,
      "generated_at": "2026-06-28T00:00:00Z",   # optional metadata
      "events": [ {<InsolvencyEvent fields>}, ... ]
    }
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .models import InsolvencyEvent

SCHEMA_VERSION = 1

# Stable column order for CSV and dict serialization.
FIELD_ORDER = (
    "carrier_name", "carrier_slug", "state", "event_type",
    "event_date", "source_url", "source_name",
)


def _default_data_path() -> Path:
    """Locate the bundled ``data/events.json`` relative to the repo root.

    The package lives at ``<root>/src/carrier_insolvency``; the data file at
    ``<root>/data/events.json``. Walk up from this file to find it."""
    here = Path(__file__).resolve()
    # here = <root>/src/carrier_insolvency/dataset.py -> parents[2] = <root>
    return here.parents[2] / "data" / "events.json"


def load(path: str | Path | None = None) -> list[InsolvencyEvent]:
    """Load events from a dataset JSON file (defaults to the bundled dataset).

    Validates every record through ``InsolvencyEvent`` (so a tampered file with
    a bad source scheme raises rather than silently shipping junk)."""
    p = Path(path) if path is not None else _default_data_path()
    raw = json.loads(p.read_text(encoding="utf-8"))
    events = raw.get("events", []) if isinstance(raw, dict) else raw
    out: list[InsolvencyEvent] = []
    for rec in events:
        out.append(InsolvencyEvent(
            carrier_name=rec["carrier_name"],
            carrier_slug=rec.get("carrier_slug") or "",
            state=rec["state"],
            event_type=rec["event_type"],
            event_date=rec.get("event_date"),
            source_url=rec["source_url"],
            source_name=rec.get("source_name", ""),
        ))
    return out


def _sort_key(event: InsolvencyEvent) -> tuple:
    # Deterministic order: state, then carrier, then date (empty dates last).
    return (event.state, event.carrier_slug, event.event_date or "9999-99-99")


def dedupe(events: list[InsolvencyEvent]) -> list[InsolvencyEvent]:
    """Drop exact-duplicate records (same carrier/state/type/date/source),
    preserving first occurrence — the dataset is an idempotent union of sources."""
    seen: set[tuple] = set()
    out: list[InsolvencyEvent] = []
    for e in events:
        key = (e.carrier_slug, e.state, e.event_type, e.event_date, e.source_url)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def to_json(events: list[InsolvencyEvent], *, generated_at: str | None = None,
            indent: int = 2) -> str:
    """Serialize events to the dataset JSON shape (stable, sorted, idempotent)."""
    ordered = sorted(dedupe(events), key=_sort_key)
    payload: dict = {"schema_version": SCHEMA_VERSION}
    if generated_at:
        payload["generated_at"] = generated_at
    payload["event_count"] = len(ordered)
    payload["events"] = [
        {k: e.to_dict()[k] for k in FIELD_ORDER} for e in ordered
    ]
    return json.dumps(payload, indent=indent, ensure_ascii=False) + "\n"


def to_csv(events: list[InsolvencyEvent]) -> str:
    """Serialize events to CSV (stable column + row order)."""
    ordered = sorted(dedupe(events), key=_sort_key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(FIELD_ORDER), lineterminator="\n")
    writer.writeheader()
    for e in ordered:
        row = e.to_dict()
        writer.writerow({k: ("" if row[k] is None else row[k]) for k in FIELD_ORDER})
    return buf.getvalue()
