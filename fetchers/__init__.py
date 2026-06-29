"""Network fetchers for the carrier-insolvency dataset (OPTIONAL, isolated).

This package is the ONLY place that touches the network. The core
``carrier_insolvency`` package is pure and offline; keeping fetching here means
you can ``import carrier_insolvency`` and use the parsers / dataset without ever
making an HTTP request.

Fetchers use the Python standard library (``urllib``) only — no third-party HTTP
client — so the whole project installs with zero runtime dependencies.
"""

from .fetch import fetch_all, fetch_source, refresh_dataset

__all__ = ["fetch_source", "fetch_all", "refresh_dataset"]
