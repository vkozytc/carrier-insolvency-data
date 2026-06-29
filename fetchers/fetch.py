"""Fetch the official state guaranty-fund pages and refresh ``data/events.json``.

Run directly to regenerate the dataset from the live sources::

    python -m fetchers.fetch                 # refresh data/events.json + .csv
    python -m fetchers.fetch --dry-run       # fetch + parse, print counts only
    python -m fetchers.fetch --only NC,TX    # restrict to some sources

Design:
  - ONE pinned parser per state (DOM differs per source), driven by the registry
    in ``carrier_insolvency.sources``.
  - Each source is isolated: a network or parse failure for one state logs a
    warning and yields 0 rows, never aborting the others. A real page that parses
    to 0 rows is the DOM-drift signal (logged).
  - Stdlib ``urllib`` only — no third-party HTTP dependency.

P&C insolvencies are rare, so a weekly refresh (see the GitHub Action) is ample.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Allow ``python fetchers/fetch.py`` from the repo root by putting ``src`` on the
# path; an installed package (``pip install .``) imports normally.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from carrier_insolvency import InsolvencyEvent, Source  # noqa: E402
from carrier_insolvency.dataset import to_csv, to_json  # noqa: E402
from carrier_insolvency.sources import SOURCES, SOURCES_BY_LABEL, build_events  # noqa: E402

_LOG = logging.getLogger("carrier_insolvency.fetch")

_UA = "carrier-insolvency-data/0.1 (+https://app.coworkrecon.org/carrier-watch)"
_TIMEOUT = 30.0

_DATA_DIR = _ROOT / "data"
_JSON_PATH = _DATA_DIR / "events.json"
_CSV_PATH = _DATA_DIR / "events.csv"


def _fetch_html(url: str) -> str:
    """GET a URL and return its decoded body. Raises on network/HTTP error
    (callers isolate the failure per source)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (http(s) only, fixed registry URLs)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def fetch_source(source: Source) -> list[InsolvencyEvent]:
    """Fetch + parse + build events for one source. Never raises: a network or
    parse failure logs a warning and returns an empty list (0 rows is the
    DOM-drift / outage signal)."""
    try:
        html = _fetch_html(source.url)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        _LOG.warning("fetch %s failed: %s", source.label, exc)
        return []
    try:
        parsed = source.parser(html)
    except Exception as exc:  # a parser bug must not abort the batch
        _LOG.warning("parse %s crashed: %s", source.label, exc)
        return []
    if html.strip() and not parsed:
        _LOG.warning("%s parsed 0 rows from %d bytes (DOM drift?)",
                     source.label, len(html))
    events = build_events(source, parsed)
    _LOG.info("%s -> %d events", source.label, len(events))
    return events


def fetch_all(only: list[str] | None = None) -> list[InsolvencyEvent]:
    """Fetch every registered source (or just ``only`` labels). Failures are
    isolated per source. Returns the combined list of events."""
    sources = SOURCES
    if only:
        wanted = {label.strip().upper() for label in only}
        sources = tuple(s for s in SOURCES if s.label in wanted)
        missing = wanted - set(SOURCES_BY_LABEL)
        if missing:
            _LOG.warning("unknown source labels ignored: %s", ", ".join(sorted(missing)))
    out: list[InsolvencyEvent] = []
    for source in sources:
        out.extend(fetch_source(source))
    return out


def refresh_dataset(only: list[str] | None = None, *, write: bool = True) -> int:
    """Fetch all sources and (re)write ``data/events.json`` + ``events.csv``.
    Returns the number of events written. With ``write=False`` it's a dry run."""
    events = fetch_all(only)
    generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json_text = to_json(events, generated_at=generated_at)
    csv_text = to_csv(events)
    if write:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _JSON_PATH.write_text(json_text, encoding="utf-8")
        _CSV_PATH.write_text(csv_text, encoding="utf-8")
        _LOG.info("wrote %s and %s", _JSON_PATH, _CSV_PATH)
    # count after dedupe = lines in events array
    import json as _json
    return _json.loads(json_text)["event_count"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the carrier-insolvency dataset.")
    parser.add_argument("--only", help="Comma-separated source labels (e.g. NC,TX).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + parse but do not write the data files.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    only = args.only.split(",") if args.only else None
    count = refresh_dataset(only, write=not args.dry_run)
    action = "would write" if args.dry_run else "wrote"
    print(f"{action} {count} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
