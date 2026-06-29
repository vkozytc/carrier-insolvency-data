"""Normalization helpers — pure, deterministic, stdlib only.

Two jobs:
  1. ``to_iso`` — collapse the many date formats seen across state guaranty-fund
     pages to a single ISO ``YYYY-MM-DD`` (or ``None`` when blank/unparseable).
  2. ``carrier_slug`` / ``carrier_display`` — map a free-text carrier name to a
     stable slug so the same carrier de-duplicates across sources, and back to a
     readable display name.

No network, no I/O, no third-party deps — so the dataset stays reproducible and
the package installs with zero supply-chain surface.
"""

from __future__ import annotations

import datetime as _dt
import re

# Two-digit-year pivot: years below this are read as 20xx, at/above as 19xx.
# Insurance estates run for decades, so a 2-digit "87" means 1987, "22" means
# 2022. 70 is a conventional, conservative cut.
_YEAR_PIVOT = 70


def to_iso(value: str | None) -> str | None:
    """Normalize the date formats seen on state guaranty-fund pages to ISO.

      - ``M/D/YYYY``         (e.g. North Carolina, 4-digit year)
      - ``MM/DD/YY``         (e.g. Texas estates, 2-digit year)
      - ``MM/DD/YYYY``       (e.g. California)
      - ``Mon DD, YYYY``     (e.g. New Jersey, "Oct 03, 2001")

    Returns ``None`` for blank, ``&nbsp;``, the ``00/00/0000`` empty sentinel,
    or anything that does not parse to a real calendar date.
    """
    if not value:
        return None
    s = value.replace("\xa0", " ").strip()
    if not s or s.startswith("00/00"):
        return None
    if "/" in s:
        parts = s.split("/")
        if len(parts) != 3:
            return None
        try:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return None
        if year < 100:
            year += 2000 if year < _YEAR_PIVOT else 1900
        if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
            return None
        return f"{year:04d}-{month:02d}-{day:02d}"
    # "Mon DD, YYYY"
    try:
        return _dt.datetime.strptime(s, "%b %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


# Known national carriers: map any name containing the needle to a canonical
# slug + display, so "Travelers Indemnity Co." and "The Travelers" collapse to
# one. Unknown carriers keep a slugified form of their own name (never collapsed
# into "other") so the long tail stays individually identifiable.
_CARRIER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("travelers", "travelers"),
    ("liberty", "liberty"),
    ("safeco", "safeco"),
    ("nationwide", "nationwide"),
    ("progressive", "progressive"),
    ("hartford", "hartford"),
    ("chubb", "chubb"),
    ("cincinnati", "cincinnati"),
    ("auto-owners", "auto-owners"),
    ("auto owners", "auto-owners"),
    ("erie", "erie"),
)

_CARRIER_DISPLAY: dict[str, str] = {
    "travelers": "Travelers",
    "liberty": "Liberty Mutual",
    "nationwide": "Nationwide",
    "progressive": "Progressive",
    "hartford": "The Hartford",
    "safeco": "Safeco",
    "chubb": "Chubb",
    "cincinnati": "Cincinnati",
    "erie": "Erie",
    "auto-owners": "Auto-Owners",
}


def carrier_slug(raw: str | None) -> str:
    """Normalize a free-text carrier name to a stable slug.

    Known national carriers map to a canonical slug; everything else gets a
    slugified form of its own name (so the long tail stays distinct, never
    collapsed into a single bucket)."""
    if not raw:
        return "other"
    low = raw.strip().lower()
    for needle, slug in _CARRIER_PATTERNS:
        if needle in low:
            return slug
    slug = re.sub(r"[^a-z0-9]+", "-", low).strip("-")
    return slug or "other"


def carrier_display(slug: str) -> str:
    """Map a slug back to a readable display name."""
    return _CARRIER_DISPLAY.get(slug, slug.replace("-", " ").title())
