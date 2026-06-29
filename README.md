# carrier-insolvency-data

**A free, verifiable dataset + parser code for US property & casualty insurance
carrier insolvency, receivership, and liquidation events — each row with its
official source link.**

When a P&C insurance carrier is placed into insolvency or liquidation, the record
exists — but it's scattered across ~50 state guaranty-fund and department-of-
insurance websites, each with its own page layout, and several published only as
HTML tables or PDFs. There is **no single national, machine-readable feed** of
which carriers are in receivership and when. The NAIC's aggregate view is
JS-rendered and its terms bar commercial redistribution; the state guaranty
funds' own pages are public consumer notices but live in a dozen different DOMs.

This repo is a small, honest attempt to fill that gap: one normalized schema, one
JSON/CSV artifact, and the open parser code that produces it — all pointing back
to the official record.

> **This is data, not advice.** Every record is a published regulatory fact with
> a link to its source. This project does **not** rate carriers, predict
> failures, or recommend replacement carriers. Verify any record against its
> `source_url` before relying on it.

## What's in the box

```
data/events.json      # the dataset (schema below)
data/events.csv       # same data, CSV
src/carrier_insolvency/   # pure, offline parsing + normalization + load API
fetchers/             # optional, network-only refresh code (stdlib urllib)
.github/workflows/    # example weekly-refresh GitHub Action
tests/                # pytest tests for the parsers + dataset
```

Zero runtime dependencies — Python standard library only.

## Schema

Each event is one record:

| field          | type            | meaning |
|----------------|-----------------|---------|
| `carrier_name` | string          | Carrier name exactly as printed by the source |
| `carrier_slug` | string          | Stable normalized slug (for de-dup / joins) |
| `state`        | string (2-char) | State of the guaranty fund / receivership proceeding |
| `event_type`   | enum            | `insolvency` \| `liquidation` \| `receivership` \| `conservation` |
| `event_date`   | ISO date \| null | `YYYY-MM-DD` when the source prints one (some list pages don't) |
| `source_url`   | string (http/s) | **Official source link — always present** |
| `source_name`  | string          | Publishing authority |

`data/events.json`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-06-28T00:00:00Z",
  "provenance": "…",
  "event_count": 12,
  "events": [ { "carrier_name": "Arrowood Indemnity Company", "...": "..." } ]
}
```

## Use it

As data — just read `data/events.json` or `data/events.csv` in any language.

As a Python library:

```python
from carrier_insolvency import load

for e in load():
    print(e.state, e.event_type, e.event_date, e.carrier_name, e.source_url)
```

Parse a page yourself (offline, no network):

```python
from carrier_insolvency import parse_nc, build_events, SOURCES_BY_LABEL

html = open("nc_insolvencies.html").read()
events = build_events(SOURCES_BY_LABEL["NC"], parse_nc(html))
```

## Refreshing the data

The core package never touches the network. The optional `fetchers` package does:

```bash
python -m fetchers.fetch              # refresh data/events.json + .csv from live sources
python -m fetchers.fetch --dry-run    # fetch + parse, print counts, write nothing
python -m fetchers.fetch --only NC,TX # restrict to specific states
```

`.github/workflows/refresh.yml` runs this weekly and commits the result. Each
source is isolated: if a state changes its page layout (DOM drift) the parser
returns 0 rows for that state and logs a warning — it never breaks the others.
A source that suddenly parses to 0 rows is itself the breakage signal.

## Official sources

This dataset is built **only** from public, official records. Current sources:

| State | Authority | Page |
|-------|-----------|------|
| NC | North Carolina Insurance Guaranty Association | https://www.ncrb.org/nciga/Insolvencies |
| FL | Florida DFS — Division of Rehabilitation & Liquidation | https://www.myfloridacfo.com/division/receiver/companies |
| TX | Texas Property & Casualty Insurance Guaranty Association | https://tpciga.org/liquidation-directory/ |
| CA | California Conservation & Liquidation Office | https://www.caclo.org/perl/insolvent.pl |
| NJ | New Jersey Property-Liability Insurance Guaranty Association | https://www.njguaranty.org/njpliga-Insolvencies.html |
| LA | Louisiana Insurance Guaranty Association | https://www.laiga.org/ |

More states are added one pinned parser at a time. PRs that add a state parser
(with a fixture of its real page DOM) are welcome.

NAIC GRID is intentionally **not** used: it is JS-rendered and its terms bar
commercial redistribution. Washington is absent because its guaranty association
is a JS single-page app with no static HTML and currently lists no companies in
receivership.

## Provenance of the shipped sample

The records currently in `data/events.json` were ported from pinned page
fixtures that mirror the live source DOM (the same fixtures the parsers are
tested against). They are **real** carrier insolvency/receivership/liquidation
events — but treat the bundled file as a starting sample: run the fetcher (or let
the weekly Action run) to populate it from the live pages, and always confirm a
record against its `source_url`.

## Human front-end

This dataset powers, and is maintained alongside, the human-readable Carrier
Watch view at **https://app.coworkrecon.org/carrier-watch** — a free, no-login
page that lets an insurance agent see the same public events without writing
code. If you use this data, a link back to Carrier Watch is appreciated.

## Contributing

Add a state by writing one pinned parser (`src/carrier_insolvency/parsers.py`),
registering it (`src/carrier_insolvency/sources.py`), and adding a test with a
fixture of that state's real page DOM (`tests/`). Keep the core pure and offline;
network code belongs in `fetchers/`.

## License

MIT — see [LICENSE](LICENSE).
