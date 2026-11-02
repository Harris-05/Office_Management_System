"""Container-local readiness using an explicitly allowed production Host header."""

import os
import urllib.request

from app.config import get_settings


def main():
    request = urllib.request.Request(
        "http://127.0.0.1:" + os.environ.get("PORT", "8000") + "/health/ready",
        headers={"Host": get_settings().allowed_hosts[0]},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
