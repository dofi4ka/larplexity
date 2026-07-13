#!/usr/bin/env python3
"""Docker HEALTHCHECK helper — hits local /healthz."""

from __future__ import annotations

import os
import sys
import urllib.request


def main() -> int:
    port = os.getenv("HEALTH_PORT", "8080")
    url = f"http://127.0.0.1:{port}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status == 200:
                return 0
    except Exception as exc:
        print(f"healthcheck failed: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
