"""The source registry: one entry per state guaranty-fund / DOI page.

Each ``Source`` ties together the official page URL, the publishing authority's
name, the regulatory event type that page records, and the pinned parser for
that page's DOM. The fetcher (separate ``fetchers`` package) walks this registry;
``build_events`` turns raw parser dicts into validated ``InsolvencyEvent``
records, attaching the per-source ``source_url`` when a row has no per-company
detail link of its own.

This module imports NO network code — it's pure metadata + the local parser
functions, so it stays importable and testable without any I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import InsolvencyEvent
from .normalize import carrier_slug
from .parsers import parse_ca, parse_fl, parse_la, parse_nc, parse_nj, parse_tx


@dataclass(frozen=True)
class Source:
    """A single official insolvency-record source.

    Attributes:
        label: Short stable key (used in logs and as the fetcher registry key).
        state: 2-letter US state code of the publishing authority.
        event_type: The regulatory status this page records (see EVENT_TYPES).
        url: The official page URL — also the default per-record source link.
        source_name: Human-readable name of the publishing authority.
        parser: Pure ``(html) -> list[dict]`` parser for this page's DOM.
    """

    label: str
    state: str
    event_type: str
    url: str
    source_name: str
    parser: Callable[[str], list[dict]]


# The pinned source registry. WA is intentionally absent: its guaranty assoc is
# a JS single-page app (no static HTML) with zero companies currently listed.
# NAIC GRID is intentionally absent: it is JS-rendered AND its disclaimer bars
# commercial redistribution, so we never touch it. These six states publish
# static, attributable consumer-notice HTML.
SOURCES: tuple[Source, ...] = (
    Source(
        label="NC", state="NC", event_type="insolvency",
        url="https://www.ncrb.org/nciga/Insolvencies",
        source_name="North Carolina Insurance Guaranty Association",
        parser=parse_nc,
    ),
    Source(
        label="FL", state="FL", event_type="receivership",
        url="https://www.myfloridacfo.com/division/receiver/companies",
        source_name="Florida DFS — Division of Rehabilitation & Liquidation",
        parser=parse_fl,
    ),
    Source(
        label="TX", state="TX", event_type="liquidation",
        url="https://tpciga.org/liquidation-directory/",
        source_name="Texas Property & Casualty Insurance Guaranty Association",
        parser=parse_tx,
    ),
    Source(
        label="CA", state="CA", event_type="receivership",
        url="https://www.caclo.org/perl/insolvent.pl",
        source_name="California Conservation & Liquidation Office",
        parser=parse_ca,
    ),
    Source(
        label="NJ", state="NJ", event_type="liquidation",
        url="https://www.njguaranty.org/njpliga-Insolvencies.html",
        source_name="New Jersey Property-Liability Insurance Guaranty Association",
        parser=parse_nj,
    ),
    Source(
        label="LA", state="LA", event_type="receivership",
        url="https://www.laiga.org/",
        source_name="Louisiana Insurance Guaranty Association",
        parser=parse_la,
    ),
)

SOURCES_BY_LABEL: dict[str, Source] = {s.label: s for s in SOURCES}


def build_events(source: Source, parsed_rows: list[dict]) -> list[InsolvencyEvent]:
    """Turn raw parser dicts into validated ``InsolvencyEvent`` records.

    A row may carry its own per-company ``source_url`` (FL / CA detail pages);
    otherwise the source's page URL is used. Rows that fail validation (empty
    name, bad source scheme) are skipped — never fatal — so one malformed row
    can't drop the rest of a source."""
    out: list[InsolvencyEvent] = []
    for row in parsed_rows:
        name = (row.get("carrier_name") or "").strip()
        if not name:
            continue
        try:
            out.append(InsolvencyEvent(
                carrier_name=name,
                carrier_slug=carrier_slug(name),
                state=source.state,
                event_type=source.event_type,
                event_date=row.get("event_date"),
                source_url=row.get("source_url") or source.url,
                source_name=source.source_name,
            ))
        except ValueError:
            continue
    return out
