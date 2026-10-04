"""Read only the isolated runtime boundary and four relevant rate-limit timers."""

import hashlib
import ipaddress
import json
import subprocess
import sys
from datetime import UTC, datetime

# Only pseudonymous lookup keys are present; addresses are never logged.
EMAIL_BUCKET = "55e3b2fd79708109437152ae9e8bc856c72f5f4175613a8e62a97032f59ab580"
COOLDOWN_BUCKET = "28389a08192c8e32fe896a796d2f8b081dd6da488cb6ea135790358eaf3fd95a"
PAYLOAD = """
import json, math, sys
from sqlalchemy import create_engine, text
from app.core.config import Settings
try:
    specs = json.loads(sys.stdin.read(4096))
    engine = create_engine(Settings().database_url.get_secret_value(), hide_parameters=True,
        connect_args={"connect_timeout":5,"options":"-c default_transaction_read_only=on -c statement_timeout=3000"})
    rows=[]
    with engine.connect() as connection:
        now=connection.execute(text("SELECT now()")).scalar_one()
        for label, digest, maximum, window in specs:
            row=connection.execute(text("SELECT window_started_at, attempts FROM auth_limits WHERE key_hash=:digest"), {"digest":digest}).first()
            retry=0 if row is None or row.attempts < maximum else max(0, math.ceil(window-(now-row.window_started_at).total_seconds()))
            rows.append({"bucket":label,"retry_seconds":retry})
    engine.dispose()
    print(json.dumps({"buckets":rows}))
except Exception:
    print(json.dumps({"result":"read_failed"}))
    raise SystemExit(1)
"""


def read(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
    if result.returncode or len(result.stdout) > 16384:
        raise ValueError("read_failed")
    return result.stdout.strip()


def one(service):
    ids = read(
        [
            "docker",
            "ps",
            "--quiet",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=joblens-release",
            "--filter",
            "label=com.docker.compose.service=" + service,
        ]
    ).splitlines()
    if len(ids) != 1 or len(ids[0]) != 64 or any(c not in "0123456789abcdef" for c in ids[0]):
        raise ValueError("expected_one_service")
    return ids[0]


def inspect(container, field):
    return json.loads(read(["docker", "inspect", "--format", "{{json " + field + "}}", container]))


def main():
    try:
        expected = sys.argv[1]
        if len(expected) != 40 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("bad_revision")
        api, gateway = one("api"), one("gateway")
        for container, service in ((api, "api"), (gateway, "gateway")):
            labels = inspect(container, ".Config.Labels")
            if (
                labels.get("com.docker.compose.project") != "joblens-release"
                or labels.get("com.docker.compose.service") != service
                or labels.get("org.opencontainers.image.revision") != expected
            ):
                raise ValueError("identity_mismatch")
        api_networks = inspect(api, ".NetworkSettings.Networks")
        gateway_networks = inspect(gateway, ".NetworkSettings.Networks")
        shared = set(api_networks) & set(gateway_networks)
        if len(api_networks) != 1 or len(shared) != 1:
            raise ValueError("network_boundary_unverified")
        network = next(iter(shared))
        labels = json.loads(
            read(
                [
                    "docker",
                    "network",
                    "inspect",
                    "--format",
                    "{{json .Labels}}",
                    network,
                ]
            )
        )
        if labels.get("com.docker.compose.project") != "joblens-release":
            raise ValueError("wrong_project_network")
        gateway_ip = gateway_networks[network]["IPAddress"]
        ipaddress.ip_address(gateway_ip)
        api_ports = inspect(api, ".NetworkSettings.Ports") or {}
        api_has_host_binding = any(api_ports.values())
        mode = inspect(api, ".HostConfig.NetworkMode")
        gateway_ports = inspect(gateway, ".NetworkSettings.Ports") or {}
        boundary = {
            "api_has_host_port_binding": api_has_host_binding,
            "api_host_network": mode == "host",
            "single_joblens_project_network": True,
            "gateway_revision_matches": True,
            "gateway_publishes_public_https": any(
                p.get("HostPort") == "443" and p.get("HostIp") in ("0.0.0.0", "::")
                for p in gateway_ports.get("443/tcp", []) or []
            ),
        }
        if api_has_host_binding or mode == "host":
            raise ValueError("api_exposure_requires_review")
        specs = [
            (
                "registration_global",
                hashlib.sha256(b"registration:global").hexdigest(),
                120,
                3600,
            ),
            (
                "registration_gateway_client",
                hashlib.sha256(("registration:client:" + gateway_ip).encode()).hexdigest(),
                20,
                3600,
            ),
            ("registration_target_email", EMAIL_BUCKET, 5, 3600),
            ("registration_target_cooldown", COOLDOWN_BUCKET, 1, 60),
        ]
        # A read-only DB session and four exact-key SELECTs; no table scan or UPDATE.
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                api,
                "python",
                "-c",
                PAYLOAD,
            ],
            input=json.dumps(specs),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode or len(result.stdout) > 4096:
            raise ValueError("bucket_read_failed")
        data = json.loads(result.stdout)
        buckets = []
        allowed = {s[0] for s in specs}
        for row in data.get("buckets", []):
            seconds = row.get("retry_seconds")
            if (
                row.get("bucket") not in allowed
                or type(seconds) is not int
                or not 0 <= seconds <= 3600
            ):
                raise ValueError("invalid_bucket_result")
            buckets.append({"bucket": row["bucket"], "retry_seconds": seconds})
        if len(buckets) != 4:
            raise ValueError("incomplete_buckets")
        print(
            json.dumps(
                {
                    "observed_at": datetime.now(UTC).isoformat(),
                    "boundary": boundary,
                    "buckets": buckets,
                },
                sort_keys=True,
            )
        )
    except Exception:
        print(json.dumps({"result": "read_only_diagnostic_failed"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
