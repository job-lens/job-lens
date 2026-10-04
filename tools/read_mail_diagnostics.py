"""Read existing JobLens mail failure metadata without changing production.

Run over SSH stdin: python3 - EXPECTED_DEPLOYED_SHA < this-file.py.
Only fixed Docker read commands and the deployed-sha marker are accessed.
Raw logs are filtered on the server and are never written or returned.
"""

import json
import os
import re
import selectors
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}")
CONTAINER = re.compile(r"[0-9a-f]{64}")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z")
CODES = frozenset(
    {
        "unknown",
        "application_error",
        "concurrent_idempotent_requests",
        "daily_quota_exceeded",
        "invalid_attachment",
        "invalid_idempotency_key",
        "invalid_idempotent_request",
        "invalid_parameter",
        "invalid_permission",
        "method_not_allowed",
        "missing_api_key",
        "missing_required_field",
        "missing_required_parameter",
        "monthly_quota_exceeded",
        "not_found",
        "rate_limit_exceeded",
        "resource_locked",
        "restricted_api_key",
        "service_unavailable",
        "suspended_api_key",
        "validation_error",
    }
)
FAILURE = re.compile(
    r"email_delivery_failed category=(configuration|provider_http|timeout|transport|protocol) "
    r"provider_status=(unknown|[1-5][0-9]{2}) provider_code=([a-z_]+) "
    r"trace_id=([A-Za-z0-9_-]{1,64})"
)


class DiagnosticError(Exception):
    """Fixed public error code; never carry an underlying exception or log."""


def capture(command, limit=4096, timeout=30):
    """Capture a bounded fixed read in memory, including Docker's log stderr."""
    with subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    ) as process:
        output = bytearray()
        deadline = time.monotonic() + timeout
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise DiagnosticError("read_timeout")
                    if not selector.select(remaining):
                        raise DiagnosticError("read_timeout")
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    if len(output) + len(chunk) > limit:
                        raise DiagnosticError("read_limit_exceeded")
                    output.extend(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DiagnosticError("read_timeout")
            if process.wait(timeout=remaining) != 0:
                raise DiagnosticError("docker_read_failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return bytes(output).decode("utf-8", errors="replace")


def filter_records(raw):
    """Reconstruct only full, allowlisted diagnostic records, never raw lines."""
    records = deque(maxlen=40)
    count = 0
    for line in raw.splitlines():
        if len(line) > 1024:
            continue
        timestamp, separator, message = line.partition(" ")
        if not separator or TIMESTAMP.fullmatch(timestamp) is None:
            continue
        # Docker prefixes the timestamp; logging may prefix a level/logger name.
        offset = message.find("email_delivery_failed ")
        if offset < 0:
            continue
        match = FAILURE.fullmatch(message[offset:])
        if match is None or match[3] not in CODES:
            continue
        count += 1
        records.append(
            {
                "timestamp": timestamp,
                "category": match[1],
                "provider_status": match[2],
                "provider_code": match[3],
                "trace_id": match[4],
            }
        )
    return count, list(records)


def collect(expected, read=capture, marker=Path("/opt/job-lens/deployed-sha")):
    if SHA.fullmatch(expected) is None:
        raise DiagnosticError("invalid_expected_revision")
    with marker.open() as stream:
        deployed = stream.read(128).strip()
    if deployed != expected:
        raise DiagnosticError("deployed_revision_mismatch")
    ids = read(
        [
            "docker",
            "ps",
            "--quiet",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=joblens-release",
            "--filter",
            "label=com.docker.compose.service=api",
        ]
    ).splitlines()
    if len(ids) != 1 or CONTAINER.fullmatch(ids[0]) is None:
        raise DiagnosticError("expected_one_joblens_api")
    api = ids[0]
    identity = read(
        [
            "docker",
            "inspect",
            "--format",
            (
                '{{index .Config.Labels "com.docker.compose.project"}} '
                '{{index .Config.Labels "com.docker.compose.service"}} '
                '{{index .Config.Labels "org.opencontainers.image.revision"}}'
            ),
            api,
        ]
    ).strip()
    if identity != "joblens-release api " + expected:
        raise DiagnosticError("api_identity_mismatch")
    count, records = filter_records(
        read(
            ["docker", "logs", "--since", "24h", "--tail", "20000", "--timestamps", api],
            limit=12 * 1024 * 1024,
        )
    )
    return {
        "schema_version": 1,
        "deployed_revision": expected,
        "api_revision_verified": True,
        "window": "24h",
        "tail_limit": 20000,
        "matching_record_count": count,
        "records": records,
        "result": "records_found" if count else "no_matching_records_inconclusive",
    }


PROBE = '"""Standalone stdin payload for one credential-free, fixed-endpoint comparison."""\n\nimport json\nfrom urllib.error import HTTPError, URLError\nfrom urllib.request import HTTPRedirectHandler, Request, build_opener\n\n\nclass NoRedirect(HTTPRedirectHandler):\n    def redirect_request(self, req, fp, code, msg, headers, newurl):\n        return None\n\n\nopener = build_opener(NoRedirect())\nresults = []\nfor profile, headers in (\n    ("urllib_default", {}),\n    ("resend_sdk_headers", {"Accept": "application/json", "User-Agent": "resend-python:2.39.0"}),\n):\n    # No Authorization, cookies, sender, recipient, account or message data.\n    request = Request("https://api.resend.com/domains", headers=headers, method="GET")\n    result = {"profile": profile, "authenticated": False, "request_count": 1}\n    try:\n        try:\n            response = opener.open(request, timeout=10)\n        except HTTPError as error:\n            response = error\n        with response:\n            result["status"] = response.code\n            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()\n            result["content_kind"] = {\n                "application/json": "json", "text/html": "html", "text/plain": "text",\n            }.get(content_type, "other")\n            body = response.read(8193)\n        if len(body) > 8192:\n            result["body_kind"] = "truncated"\n        else:\n            try:\n                data = json.loads(body)\n                result["body_kind"] = "json"\n                code = data.get("name") if isinstance(data, dict) else None\n                result["provider_code"] = code if code in (\n                    "missing_api_key", "restricted_api_key", "invalid_permission",\n                    "validation_error", "application_error", "rate_limit_exceeded",\n                ) else "unknown"\n            except (ValueError, TypeError, RecursionError):\n                result["body_kind"] = "non_json"\n                result["provider_code"] = "unknown"\n        result["result"] = "http_response"\n    except (URLError, OSError, TimeoutError):\n        result["result"] = "transport_error"\n    except Exception:  # Never surface raw transport/provider exceptions.\n        result["result"] = "probe_error"\n    results.append(result)\nprint(json.dumps({"probe": "unauthenticated_fixed_domains_get", "results": results}, sort_keys=True))\n'


def probe_headers(expected):
    ids = capture(
        [
            "docker",
            "ps",
            "--quiet",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=joblens-release",
            "--filter",
            "label=com.docker.compose.service=api",
        ]
    ).splitlines()
    if len(ids) != 1 or CONTAINER.fullmatch(ids[0]) is None:
        raise DiagnosticError("expected_one_joblens_api")
    identity = capture(
        [
            "docker",
            "inspect",
            "--format",
            '{{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}} {{index .Config.Labels "org.opencontainers.image.revision"}}',
            ids[0],
        ]
    ).strip()
    if identity != "joblens-release api " + expected:
        raise DiagnosticError("api_identity_mismatch")
    result = subprocess.run(
        ["docker", "exec", "-i", "--env", "PYTHONDONTWRITEBYTECODE=1", ids[0], "python", "-"],
        input=PROBE,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode or len(result.stdout) > 4096:
        raise DiagnosticError("probe_failed")
    data = json.loads(result.stdout)
    # The payload emits no raw data. Reconstruct once more at SSH boundary.
    safe = []
    for row in data.get("results", []):
        if row.get("profile") not in ("urllib_default", "resend_sdk_headers"):
            continue
        item = {"profile": row["profile"], "authenticated": False}
        status = row.get("status")
        if type(status) is int and 100 <= status <= 599:
            item["status"] = status
        for key, allowed in {
            "content_kind": ("json", "html", "text", "other"),
            "body_kind": ("json", "non_json", "truncated"),
            "result": ("http_response", "transport_error", "probe_error"),
            "provider_code": CODES,
        }.items():
            if row.get(key) in allowed:
                item[key] = row[key]
        safe.append(item)
    return {"probe": "unauthenticated_fixed_domains_get", "results": safe}


def main():
    try:
        if len(sys.argv) != 2:
            raise DiagnosticError("expected_one_revision_argument")
        result = collect(sys.argv[1])
        result["header_comparison"] = probe_headers(sys.argv[1])
    except DiagnosticError as error:
        print(json.dumps({"result": "diagnostic_failed", "reason": str(error)}))
        return 1
    except Exception:  # noqa: BLE001 - suppress all raw error details at the SSH boundary
        # Never print exception messages, tracebacks, command output or secrets.
        print(json.dumps({"result": "diagnostic_failed", "reason": "read_failed"}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
