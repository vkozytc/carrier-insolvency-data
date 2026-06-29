"""Per-state HTML parsers for public guaranty-fund / DOI receivership pages.

There is NO clean national structured feed for US P&C carrier insolvencies. The
viable public sources are per-state guaranty-fund / department-of-insurance HTML
tables — consumer-notice records that may be displayed with attribution and a
source link. Each state's page has a different DOM, so each gets ONE pinned
parser behind a small registry (see ``sources.py``).

Every parser is pure: it takes an HTML string and returns a list of dicts with
``carrier_name``, ``event_date`` (ISO or None), and optionally a per-company
``source_url``. No network here — fetching lives in the separate ``fetchers``
package. A parser returning 0 rows from real HTML is the DOM-drift signal.

Stdlib only: ``html.parser.HTMLParser`` for tables/anchors, ``re`` for the
nested layouts that a flat table walk can't handle.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .normalize import to_iso

# Texas tags the domicile state onto the name, e.g. "Affirmative Ins Co (IL)";
# strip it so the slug matches the carrier's plain name.
_TX_DOMICILE_RE = re.compile(r"\s*\([A-Z]{2}\)\s*$")

# Florida lists each company as an anchor to a per-company detail page; that
# detail URL is the official per-event source link.
_FL_DETAIL_RE = re.compile(r"/division/receiver/companies/detail/\d+", re.I)
_FL_HOST = "https://www.myfloridacfo.com"

# California is nested layout tables, so match the company anchor + the
# conservation-date cell that immediately follows it (regex is sturdier than a
# table walk on the nesting). Empty dates render as &nbsp;.
_CA_ROW_RE = re.compile(
    r'index\.pl\?document_id=([0-9a-fA-F]+)"[^>]*>([^<]+)</a>\s*</td>\s*'
    r'<td[^>]*>([^<]*)</td>',
    re.I,
)
_CA_DETAIL = "https://www.caclo.org/perl/index.pl?document_id="

# New Jersey is a Bootstrap trigger-table + sibling modal <div>s, all static.
# Pass 1: trigger anchors -> (modal id, company name). Pass 2: the date <td>
# inside the matching modal.
_NJ_TRIGGER_RE = re.compile(
    r'data-toggle="modal"[^>]*data-target="#([^"]+)"[^>]*role="button"[^>]*>'
    r'([^<]+)</a>',
    re.I,
)
_NJ_DATE_RE = re.compile(r"<td[^>]*>\s*([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s*</td>")

# Louisiana lists insolvent companies as anchors to external receiver sites;
# the company NAME comes from the anchor text (an insurance-name suffix marks a
# company anchor) and the stable laiga.org page itself is the source link.
_LA_NAME_RE = re.compile(r"\b(insurance|casualty|indemnity|assurance)\b", re.I)


class _TableRows(HTMLParser):
    """Collect every <table> row as a list of cell texts. Accumulates ALL text
    inside each <td>/<th> (a company name may be nested in <p><span>), so it
    never relies on direct-child text."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _extract_rows(html: str) -> list[list[str]]:
    parser = _TableRows()
    parser.feed(html)
    return parser.rows


class _Anchors(HTMLParser):
    """Collect (href, link_text) for every <a href>. convert_charrefs (default
    on) means the text arrives already entity-decoded ('&amp;' -> '&')."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._text = []

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text or []).split())))
            self._href = None
            self._text = None

    def handle_data(self, data):
        if self._text is not None:
            self._text.append(data)


def _extract_links(html: str) -> list[tuple[str, str]]:
    parser = _Anchors()
    parser.feed(html)
    return parser.links


def _parse_table(html: str, name_key: str, date_key: str, *, label: str) -> list[dict]:
    """Header-mapped flat-table parse shared by NC + TX. Finds the header row by
    ``name_key``, maps the name + date columns by header substring (not fixed
    positions, so a reordered column never silently mis-reads), and returns
    ``carrier_name`` + ``event_date`` per data row."""
    rows = _extract_rows(html)
    header_idx = name_col = date_col = None
    for idx, row in enumerate(rows):
        lower = [c.lower() for c in row]
        if any(name_key in c for c in lower):
            header_idx = idx
            for i, cell in enumerate(lower):
                if name_key in cell and name_col is None:
                    name_col = i
                elif date_key in cell and date_col is None:
                    date_col = i
            break
    if header_idx is None or name_col is None:
        return []  # header not found -> DOM drift; caller treats 0 rows as the signal

    out: list[dict] = []
    for row in rows[header_idx + 1:]:
        if name_col >= len(row):
            continue
        name = row[name_col].strip()
        if not name or name_key in name.lower():
            continue
        date = row[date_col] if (date_col is not None and date_col < len(row)) else None
        out.append({"carrier_name": name, "event_date": to_iso(date)})
    return out


def parse_nc(html: str) -> list[dict]:
    """North Carolina Insurance Guaranty Association insolvency list.
    Headers: NAIC # | Company Name | Date of Insolvency | Bar Date."""
    return _parse_table(html, "company name", "date of insolvency", label="NC")


def parse_tx(html: str) -> list[dict]:
    """Texas P&C Insurance Guaranty Association liquidation directory:
    Company Name | Estate Number | Date | Status. Strip the trailing domicile
    tag '(IL)' so the slug matches the carrier's plain name."""
    out: list[dict] = []
    for row in _parse_table(html, "company name", "date", label="TX"):
        name = _TX_DOMICILE_RE.sub("", row["carrier_name"]).strip()
        if name:
            out.append({**row, "carrier_name": name})
    return out


def parse_fl(html: str) -> list[dict]:
    """Florida Division of Rehabilitation & Liquidation companies page -> one row
    per company in receivership. The list page carries no date (it lives on each
    company's detail page), so ``event_date`` is None and the per-company detail
    URL becomes the official source link."""
    out: list[dict] = []
    seen: set[str] = set()
    for href, text in _extract_links(html):
        if not _FL_DETAIL_RE.search(href) or not text:
            continue
        url = href if href.startswith("http") else _FL_HOST + href
        # FL serves http hrefs; prefer https for the stored source link.
        url = url.replace("http://www.myfloridacfo.com", _FL_HOST, 1)
        if url in seen:
            continue
        seen.add(url)
        out.append({"carrier_name": text, "event_date": None, "source_url": url})
    return out


def parse_ca(html: str) -> list[dict]:
    """California Conservation & Liquidation Office estate list. Nested layout
    tables, so match each company anchor + the conservation-date cell that
    follows it. The per-company document_id link is the source; ``event_date`` =
    conservation date (blank/&nbsp; -> None)."""
    out: list[dict] = []
    seen: set[str] = set()
    for hexid, name, date in _CA_ROW_RE.findall(html):
        name = " ".join(name.split())
        if not name:
            continue
        url = _CA_DETAIL + hexid.lower()
        if url in seen:
            continue
        seen.add(url)
        out.append({"carrier_name": name, "event_date": to_iso(date), "source_url": url})
    return out


def parse_nj(html: str) -> list[dict]:
    """New Jersey P-L Insurance Guaranty Association insolvencies: Bootstrap
    trigger-table + sibling modal <div>s (all static). Pass 1: trigger anchors
    -> (modal id, name). Pass 2: the 'Mon DD, YYYY' date <td> inside the
    matching modal, bounded to the next modal so a date never bleeds across."""
    out: list[dict] = []
    seen: set[str] = set()
    for modal_id, name in _NJ_TRIGGER_RE.findall(html):
        if modal_id.lower() == "navbar":
            continue
        name = " ".join(name.split())
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        date = None
        pos = html.find(f'id="{modal_id}"')
        if pos != -1:
            # Bound the date search to the NEXT outer modal ('class="modal
            # fade"'), not an arbitrary byte window, so a date can't bleed from
            # a later modal. Fall back to a window if it's the last modal.
            nxt = html.find('class="modal fade"', pos + 1)
            end = nxt if nxt != -1 else min(pos + 4000, len(html))
            match = _NJ_DATE_RE.search(html, pos, end)
            if match:
                date = match.group(1)
        out.append({"carrier_name": name, "event_date": to_iso(date)})
    return out


def parse_la(html: str) -> list[dict]:
    """Louisiana Insurance Guaranty Association insolvent-company list. Anchors
    whose text is a company name (insurance-name suffix) -> name; the source is
    the stable laiga.org page (the external receiver hrefs are inconsistent).
    No list-page date, so ``event_date`` is None (like FL). The caller supplies
    the page URL as the source link."""
    out: list[dict] = []
    seen: set[str] = set()
    for _href, text in _extract_links(html):
        name = " ".join(text.split())
        name = re.sub(r"\s+(Information|Website|Details?|Page)$", "", name, flags=re.I)
        if not name or len(name) > 70 or not _LA_NAME_RE.search(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"carrier_name": name, "event_date": None})
    return out
