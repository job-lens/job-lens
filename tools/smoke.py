import json
import sys
import urllib.error
import urllib.request


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
    for route in ("/api/v1/health/live", "/api/v1/health/ready"):
        with urllib.request.urlopen(base + route, timeout=10) as response:
            if response.status != 200 or json.load(response) != {"status": "ok"}:
                raise SystemExit(f"Health check failed: {route}")
    with urllib.request.urlopen(base + "/learner", timeout=10) as response:
        if b'id="root"' not in response.read():
            raise SystemExit("SPA fallback failed")
    try:
        urllib.request.urlopen(base + "/api/v1/not-a-route", timeout=10)
    except urllib.error.HTTPError as error:
        if error.code != 404 or json.load(error)["status"] != 404:
            raise SystemExit("API error routing failed") from error
    else:
        raise SystemExit("API paths must not fall back to the SPA")
    print("PASS: gateway, API, migrated database, SPA fallback and API error boundary")


if __name__ == "__main__":
    main()
