"""Tests for date + carrier-name normalization (pure, no network)."""

from __future__ import annotations

from carrier_insolvency import carrier_display, carrier_slug, to_iso


def test_to_iso_all_state_formats():
    assert to_iso("11/8/2023") == "2023-11-08"        # NC 4-digit
    assert to_iso("04/28/22") == "2022-04-28"          # 2-digit -> 20xx
    assert to_iso("03/24/87") == "1987-03-24"          # 2-digit -> 19xx (pivot 70)
    assert to_iso("Oct 03, 2001") == "2001-10-03"      # NJ 'Mon DD, YYYY'


def test_to_iso_rejects_blank_and_sentinels():
    assert to_iso("\xa0") is None                       # &nbsp;
    assert to_iso("00/00/0000") is None                # CA empty sentinel
    assert to_iso("") is None
    assert to_iso(None) is None
    assert to_iso("not a date") is None
    assert to_iso("13/40/2023") is None                # out of range


def test_carrier_slug_known_and_unknown():
    # Known national carrier collapses regardless of suffix.
    assert carrier_slug("The Travelers Indemnity Company") == "travelers"
    assert carrier_slug("Liberty Mutual Fire Ins Co") == "liberty"
    # Unknown carrier keeps a slug of its own name (never collapsed to 'other').
    assert carrier_slug("Reliance Insurance Company") == "reliance-insurance-company"
    assert carrier_slug("") == "other"
    assert carrier_slug(None) == "other"


def test_carrier_display_roundtrip():
    assert carrier_display("travelers") == "Travelers"
    assert carrier_display("reliance-insurance-company") == "Reliance Insurance Company"
