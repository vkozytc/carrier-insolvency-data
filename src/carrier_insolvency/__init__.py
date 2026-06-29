"""carrier_insolvency — a free, verifiable dataset + parsers for US P&C insurance
carrier insolvency / receivership / liquidation events.

Public, official-record data only. Every event carries its official
``source_url``. Pure and deterministic core (no network); the optional network
fetchers live in the separate top-level ``fetchers`` package.

Quick start::

    from carrier_insolvency import load
    for event in load():
        print(event.state, event.carrier_name, event.event_type, event.source_url)
"""

from __future__ import annotations

from .dataset import dedupe, load, to_csv, to_json
from .models import EVENT_TYPES, InsolvencyEvent
from .normalize import carrier_display, carrier_slug, to_iso
from .parsers import parse_ca, parse_fl, parse_la, parse_nc, parse_nj, parse_tx
from .sources import SOURCES, SOURCES_BY_LABEL, Source, build_events

__version__ = "0.1.0"

__all__ = [
    "InsolvencyEvent",
    "EVENT_TYPES",
    "load",
    "to_json",
    "to_csv",
    "dedupe",
    "carrier_slug",
    "carrier_display",
    "to_iso",
    "Source",
    "SOURCES",
    "SOURCES_BY_LABEL",
    "build_events",
    "parse_nc",
    "parse_tx",
    "parse_fl",
    "parse_ca",
    "parse_nj",
    "parse_la",
    "__version__",
]
