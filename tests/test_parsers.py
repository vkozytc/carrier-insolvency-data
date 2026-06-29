"""Tests for the per-state HTML parsers — pinned fixtures, no live network.

The fixture HTML mirrors the live page structure of each state guaranty-fund /
DOI page (verified against the real DOM), with real carrier names that have
genuinely been placed into insolvency / receivership / liquidation."""

from __future__ import annotations

from carrier_insolvency import (
    parse_ca,
    parse_fl,
    parse_la,
    parse_nc,
    parse_nj,
    parse_tx,
)

# NC table, mirroring live headers: NAIC # | Company Name | Date of Insolvency
# | Bar Date. Mixes 4-digit and 2-digit years (the live page does too).
_NC_HTML = """
<html><body>
<table>
  <thead><tr>
    <th>NAIC #</th><th>Company Name</th>
    <th>Date of Insolvency</th><th>Bar Date</th>
  </tr></thead>
  <tbody>
    <tr><td>24678</td><td>Arrowood Indemnity Company</td>
        <td>11/8/2023</td><td>1/15/2025</td></tr>
    <tr><td>13207</td><td>Lighthouse Property Ins Corp</td>
        <td>04/28/22</td><td>08/23/22</td></tr>
  </tbody>
</table>
</body></html>
"""


def test_parse_nc_live_headers():
    rows = parse_nc(_NC_HTML)
    by_name = {r["carrier_name"]: r["event_date"] for r in rows}
    assert by_name == {
        "Arrowood Indemnity Company": "2023-11-08",
        "Lighthouse Property Ins Corp": "2022-04-28",
    }


def test_parse_nc_is_header_mapped_not_positional():
    html = (
        "<table><tr><th>Date of Insolvency</th><th>Company Name</th></tr>"
        "<tr><td>3/4/2022</td><td><span>Acme Mutual Ins Co</span></td></tr></table>"
    )
    rows = parse_nc(html)
    assert rows == [{"carrier_name": "Acme Mutual Ins Co", "event_date": "2022-03-04"}]


def test_parse_nc_missing_table_returns_empty():
    assert parse_nc("<html><body>no table here</body></html>") == []


_FL_HTML = """
<html><body>
<nav><a href="/division/receiver/companies">COMPANIES</a>
     <a href="/division/receiver/companies/closed">Closed Companies</a></nav>
<ul>
  <li><a href="http://www.myfloridacfo.com/division/receiver/companies/detail/562">FEDNAT INSURANCE COMPANY</a></li>
  <li><a href="http://www.myfloridacfo.com/division/receiver/companies/detail/563">UNITED PROPERTY &amp; CASUALTY INSURANCE COMPANY</a></li>
  <li><a href="/division/receiver/companies/detail/557">ST. JOHNS INSURANCE COMPANY, INC.</a></li>
</ul>
</body></html>
"""


def test_parse_fl_extracts_only_company_detail_links():
    rows = parse_fl(_FL_HTML)
    names = {r["carrier_name"] for r in rows}
    assert names == {
        "FEDNAT INSURANCE COMPANY",
        "UNITED PROPERTY & CASUALTY INSURANCE COMPANY",   # entity-decoded
        "ST. JOHNS INSURANCE COMPANY, INC.",
    }
    assert all("/detail/" in r["source_url"] for r in rows)
    by = {r["carrier_name"]: r["source_url"] for r in rows}
    # relative href absolutized; http upgraded to https
    assert by["ST. JOHNS INSURANCE COMPANY, INC."] == \
        "https://www.myfloridacfo.com/division/receiver/companies/detail/557"
    assert by["FEDNAT INSURANCE COMPANY"].startswith("https://")
    assert all(r["event_date"] is None for r in rows)  # date lives on detail pages


_TX_HTML = """
<table>
  <tr><th>Company Name</th><th>Estate Number</th><th>Date</th><th>Status</th></tr>
  <tr><td>ACCC Insurance Company</td><td>564</td><td>12/14/20</td><td>Prime Tempus</td></tr>
  <tr><td>Affirmative Insurance Company (IL)</td><td>851</td><td>03/24/16</td><td>IL OSD</td></tr>
</table>
"""


def test_parse_tx_strips_domicile_tag():
    rows = parse_tx(_TX_HTML)
    by = {r["carrier_name"]: r["event_date"] for r in rows}
    assert by == {
        "ACCC Insurance Company": "2020-12-14",
        "Affirmative Insurance Company": "2016-03-24",  # '(IL)' stripped
    }


_CA_HTML = """
<table><tr>
  <td class="leftborder vertdivider"><a href="index.pl?document_id=66398C2Bd35a">Crusader Insurance Company</a></td>
  <td class="vertdivider" align="center">06/07/2023</td>
  <td sorttable_customkey="00/00/0000" class="vertdivider">&nbsp;</td>
  <td><a href="mailto:x@caclo.org">Manager</a></td>
</tr></table>
"""


def test_parse_ca_anchor_and_date_cell():
    rows = parse_ca(_CA_HTML)
    assert len(rows) == 1
    assert rows[0]["carrier_name"] == "Crusader Insurance Company"
    assert rows[0]["event_date"] == "2023-06-07"
    assert rows[0]["source_url"] == \
        "https://www.caclo.org/perl/index.pl?document_id=66398c2bd35a"  # lowercased


_NJ_HTML = """
<nav><a href data-toggle="modal" data-target="#navbar" role="button">Menu</a></nav>
<table><tr><td>
  <a href data-toggle="modal" data-target="#RelianceInsurance" role="button">Reliance Insurance Company</a>
</td></tr></table>
<div class="modal fade" id="RelianceInsurance"><div class="modal-content">
  <div class="modal-header"><h4>Reliance Insurance Company</h4></div>
  <div class="modal-body"><table><tr><td>Oct 03, 2001</td></tr></table></div>
</div></div>
"""


def test_parse_nj_trigger_plus_modal_date_excludes_navbar():
    rows = parse_nj(_NJ_HTML)
    assert rows == [{"carrier_name": "Reliance Insurance Company",
                     "event_date": "2001-10-03"}]


def test_parse_nj_missing_modal_yields_none_not_a_bleed():
    # A trigger with no matching modal -> None date, never a date stolen from
    # the next modal (the next-modal-bounded search guards this).
    html = (
        '<table><tr><td>'
        '<a href data-toggle="modal" data-target="#Orphan" role="button">Orphan Co</a>'
        '</td><td>'
        '<a href data-toggle="modal" data-target="#HasDate" role="button">Has Date Co</a>'
        '</td></tr></table>'
        '<div class="modal fade" id="HasDate"><div class="modal-body">'
        '<table><tr><td>Jan 02, 2020</td></tr></table></div></div>'
    )
    rows = parse_nj(html)
    by = {r["carrier_name"]: r["event_date"] for r in rows}
    assert by == {"Orphan Co": None, "Has Date Co": "2020-01-02"}


_LA_HTML = """
<a href="/history/company-organization/">Company Organization</a>
<a href="http://lemicins.com/AmericasWebsite/">Americas Insurance Company</a>
<a href="http://lemicins.com/AccessHomeWebsite/">Access Home Insurance Company</a>
<a href="https://x">Southern Fidelity Insurance Company Information</a>
<a href="/">Cowork Recon</a>
"""


def test_parse_la_company_anchors_only():
    rows = parse_la(_LA_HTML)
    names = {r["carrier_name"] for r in rows}
    assert names == {
        "Americas Insurance Company",
        "Access Home Insurance Company",
        "Southern Fidelity Insurance Company",   # trailing "Information" stripped
    }
    assert all(r["event_date"] is None for r in rows)
