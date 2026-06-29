"""Tests for the dataset build + load + serialize round-trip, and the bundled
``data/events.json`` artifact (every shipped record must be schema-valid with an
official http(s) source link)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carrier_insolvency import (
    EVENT_TYPES,
    InsolvencyEvent,
    SOURCES_BY_LABEL,
    build_events,
    load,
    to_csv,
    to_json,
)

_ROOT = Path(__file__).resolve().parents[1]
_DATA_JSON = _ROOT / "data" / "events.json"


def test_build_events_attaches_source_url_and_slug():
    fl = SOURCES_BY_LABEL["FL"]
    parsed = [{"carrier_name": "FedNat Insurance Company", "event_date": None,
               "source_url": "https://www.myfloridacfo.com/division/receiver/companies/detail/562"}]
    events = build_events(fl, parsed)
    assert len(events) == 1
    e = events[0]
    assert e.carrier_slug == "fednat-insurance-company"
    assert e.state == "FL" and e.event_type == "receivership"
    assert e.source_url.endswith("/detail/562")


def test_build_events_falls_back_to_source_page_url():
    nc = SOURCES_BY_LABEL["NC"]
    parsed = [{"carrier_name": "Arrowood Indemnity Company", "event_date": "2023-11-08"}]
    events = build_events(nc, parsed)
    assert events[0].source_url == nc.url  # no per-company link -> page url


def test_build_events_skips_invalid_rows():
    nc = SOURCES_BY_LABEL["NC"]
    parsed = [
        {"carrier_name": "", "event_date": None},                      # empty name
        {"carrier_name": "Good Co", "event_date": None,
         "source_url": "javascript:alert(1)"},                          # bad scheme
        {"carrier_name": "Real Co", "event_date": None},               # valid
    ]
    events = build_events(nc, parsed)
    assert [e.carrier_name for e in events] == ["Real Co"]


def test_model_rejects_non_http_source():
    with pytest.raises(ValueError):
        InsolvencyEvent(
            carrier_name="X", carrier_slug="x", state="NC",
            event_type="insolvency", event_date=None,
            source_url="ftp://example.com", source_name="src")


def test_model_rejects_unknown_event_type():
    with pytest.raises(ValueError):
        InsolvencyEvent(
            carrier_name="X", carrier_slug="x", state="NC",
            event_type="bankruptcy", event_date=None,
            source_url="https://example.com", source_name="src")


def test_json_csv_roundtrip(tmp_path):
    nc = SOURCES_BY_LABEL["NC"]
    events = build_events(nc, [
        {"carrier_name": "Arrowood Indemnity Company", "event_date": "2023-11-08"},
    ])
    p = tmp_path / "events.json"
    p.write_text(to_json(events), encoding="utf-8")
    loaded = load(p)
    assert len(loaded) == 1
    assert loaded[0].carrier_name == "Arrowood Indemnity Company"
    # CSV has a header + one data row
    csv_text = to_csv(events)
    assert csv_text.splitlines()[0].startswith("carrier_name,")
    assert "Arrowood Indemnity Company" in csv_text


def test_to_json_is_deterministic_and_idempotent():
    nc = SOURCES_BY_LABEL["NC"]
    events = build_events(nc, [
        {"carrier_name": "Bravo Co", "event_date": None},
        {"carrier_name": "Alpha Co", "event_date": None},
        {"carrier_name": "Alpha Co", "event_date": None},  # dup
    ])
    out1 = to_json(events)
    out2 = to_json(events)
    assert out1 == out2
    payload = json.loads(out1)
    assert payload["event_count"] == 2  # dup collapsed
    # sorted by (state, slug): Alpha before Bravo
    assert [e["carrier_name"] for e in payload["events"]] == ["Alpha Co", "Bravo Co"]


def test_bundled_dataset_is_schema_valid():
    """Every shipped record loads, validates, and has an official http(s) link."""
    events = load(_DATA_JSON)
    assert len(events) >= 1, "bundled dataset should ship at least the sample records"
    for e in events:
        assert e.carrier_name
        assert e.source_url.startswith(("http://", "https://"))
        assert e.event_type in EVENT_TYPES
        assert len(e.state) == 2
        if e.event_date is not None:
            # ISO YYYY-MM-DD
            assert len(e.event_date) == 10 and e.event_date[4] == "-"
