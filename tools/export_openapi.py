"""Export actual application routes; product contract remains in contracts/openapi.yaml."""

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def render() -> str:
    settings = Settings(database_url="postgresql+psycopg://unused@localhost/unused", _env_file=None)
    return (
        json.dumps(create_app(settings).openapi(), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "contracts/runtime.openapi.json"
    content = render()
    if args.check:
        if not path.exists() or path.read_text() != content:
            raise SystemExit("Runtime OpenAPI snapshot drift")
    else:
        path.write_text(content)
    print("Runtime OpenAPI snapshot: PASS")


if __name__ == "__main__":
    main()
