"""Vercel entrypoint — the Python runtime loads `main:app` from here.

Locally nothing uses this file: run.py starts uvicorn directly.
"""

from reroute.app import create_app

app = create_app()
