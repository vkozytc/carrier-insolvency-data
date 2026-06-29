"""The record type for a single carrier insolvency / receivership event.

One ``InsolvencyEvent`` is one public regulatory event: a named US property &
casualty insurance carrier that a state guaranty fund or department of insurance
has placed into insolvency, liquidation, or receivership. Every record carries
its official ``source_url`` so a reader can verify it against the primary record.

The dataclass is frozen (immutable): records are built once from a parser and
never mutated, which keeps the dataset deterministic and safe to share.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# The regulatory event types we record. These are factual states a carrier is
# placed into by a court / regulator — never an opinion or a rating.
EVENT_TYPES = ("insolvency", "liquidation", "receivership", "conservation")


@dataclass(frozen=True)
class InsolvencyEvent:
    """A single public carrier insolvency / receivership event.

    Attributes:
        carrier_name: The carrier name exactly as printed by the source.
        carrier_slug: A stable normalized slug (see ``normalize.carrier_slug``)
            for de-duplication and joins.
        state: The 2-letter US state code of the guaranty fund / regulator that
            published the record (the state of the receivership proceeding).
        event_type: One of ``EVENT_TYPES`` — the regulatory status.
        event_date: ISO ``YYYY-MM-DD`` date of the event if the source prints
            one, else ``None`` (some list pages carry the date only on a
            per-company detail page).
        source_url: The official source link. REQUIRED. Must be http(s).
        source_name: Human-readable name of the publishing authority.
    """

    carrier_name: str
    carrier_slug: str
    state: str
    event_type: str
    event_date: str | None
    source_url: str
    source_name: str

    def __post_init__(self) -> None:
        if not self.carrier_name:
            raise ValueError("carrier_name is required")
        if not self.source_url.lower().startswith(("http://", "https://")):
            # Records are public, clickable facts — a non-http(s) source is
            # either junk or an injection vector; reject it at construction.
            raise ValueError(f"source_url must be http(s), got {self.source_url!r}")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"event_type must be one of {EVENT_TYPES}, got {self.event_type!r}")

    def to_dict(self) -> dict:
        """Plain-dict view (stable key order) for JSON / CSV serialization."""
        return asdict(self)
