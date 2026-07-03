"""Public HTTP API for Community Energy Flexibility OS.

A thin FastAPI service that wraps the ``community_energy_flex`` engine and serves
the reference datasets, so a website (or any client) can get an optimised
schedule without importing Python. The engine stays the single source of truth;
this layer only translates HTTP <-> domain and caches the live feeds.
"""
