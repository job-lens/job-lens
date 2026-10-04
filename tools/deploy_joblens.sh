#!/usr/bin/env bash
# Invoked only after an approved release bundle has been securely transferred.
# Does not bootstrap credentials, DNS, firewall, a scanner, or a shared proxy.
set -euo pipefail
umask 077
readonly root=/opt/job-lens
readonly config=/etc/job-lens/joblens.env
sha=${1:?Usage: deploy_joblens.sh EXACT_SHA}
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ -f "$root/runtime-override.yaml" && -d "$root/releases/$sha" && -f "$config" && ! -L "$config" ]] || {
  echo 'JobLens release or separately provisioned configuration is missing' >&2; exit 1;
}
[[ $(stat -c %a "$config") == 600 ]] || { echo 'Configuration must have mode 0600' >&2; exit 1; }
cd "$root/releases/$sha"
exec 9>"$root/deploy.lock"
flock -n 9 || { echo 'Another JobLens deployment is active' >&2; exit 1; }
# Explicit file/project prevents a neighboring or inherited Compose override.
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES
export JOBLENS_API_IMAGE="joblens-api:$sha" JOBLENS_WEB_IMAGE="joblens-web:$sha"
export JOBLENS_POSTGRES_IMAGE="joblens-postgres:$sha"
compose=(docker compose --project-name joblens-release --env-file "$config" -f "$PWD/compose.production.yaml" -f "$root/runtime-override.yaml")
"${compose[@]}" config --quiet
sha256sum --check SHA256SUMS --status
# Do not extract/build code on the shared production machine.
for image in api web postgres; do gzip -dc "$image.tar.gz" | docker load >/dev/null; done
# The loaded images must match the exact CI-recorded identities.
while read -r name id; do
  [[ "$name" =~ ^joblens-(api|web|postgres):$sha$ && "$id" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 1
  actual=$(python3 verify_image_identity.py verify image-identities.json "$name" "$id")
  case "$name" in
    joblens-api:*) export JOBLENS_API_IMAGE="$actual" ;;
    joblens-web:*) export JOBLENS_WEB_IMAGE="$actual" ;;
    joblens-postgres:*) export JOBLENS_POSTGRES_IMAGE="$actual" ;;
  esac
done < image-ids.txt
[[ $(wc -l < image-ids.txt) == 3 ]] || exit 1
# Preserve the running database image; this release never upgrades Postgres.
db=$(docker ps -q --filter label=com.docker.compose.project=joblens-release --filter label=com.docker.compose.service=db)
[[ -n "$db" ]] || { echo 'Existing JobLens database required; stop' >&2; exit 1; }
export JOBLENS_POSTGRES_IMAGE=$(docker inspect "$db" --format '{{.Image}}')
backup="$root/backups/$(date -u +%Y%m%dT%H%M%SZ)-$sha"
mkdir -p "$backup"
cp "$root/deployed-sha" "$backup/previous-sha"
docker ps -q --filter label=com.docker.compose.project=joblens-release |
  xargs docker inspect --format '{{ index .Config.Labels "com.docker.compose.service" }} {{.Image}}' > "$backup/previous-images.txt"
trap 'code=$?; if (( code != 0 )); then printf "Release failed; retained prior images and backup at %s. Stop; database rollback requires review.\n" "$backup" >&2; printf "%s\n" "$code" > "$backup/FAILED"; fi' EXIT
"${compose[@]}" exec -T db pg_dump -U job_lens -d job_lens -Fc > "$backup/database.dump.tmp"
[[ -s "$backup/database.dump.tmp" ]]
"${compose[@]}" exec -T db pg_restore --list < "$backup/database.dump.tmp" >/dev/null
mv "$backup/database.dump.tmp" "$backup/database.dump"
# Check actual production Settings and mail configuration, without sending mail.
# When uploads are enabled, test scanner availability via PING, without a user file.
"${compose[@]}" run --rm --no-deps -T api python - <<'PYCODE'
import socket
from app.core.config import Settings
from app.infrastructure.email import require_delivery
try:
    cfg = Settings()
    require_delivery(cfg)
    if cfg.scan_enabled:
        with socket.create_connection((cfg.scan_host, cfg.scan_port), timeout=5) as sock:
            sock.sendall(b"zPING\0")
            if sock.recv(64).rstrip(b"\0\n") != b"PONG":
                raise ValueError("Unexpected scanner response")
        print("Scanner PING passed; file scan acceptance remains separate")
    else:
        print("Scanning explicitly disabled: uploads unavailable (503); account services can start")
except Exception as exc:
    print("Production dependency preflight failed:", type(exc).__name__)
    raise SystemExit(1)
print("Production settings and mail configuration passed; delivery/storage acceptance remains separate")
PYCODE
# Validate configuration without producing certificates or contacting mail.
"${compose[@]}" run --rm --no-deps gateway caddy validate --config /etc/caddy/Caddyfile >/dev/null
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 180
# Restore independently published native downloads after a gateway replacement.
if [[ -d "$root/downloads" ]]; then
  gateway=$("${compose[@]}" ps -q gateway)
  [[ -n "$gateway" ]]
  docker exec "$gateway" mkdir -p /srv/downloads
  docker cp "$root/downloads/." "$gateway:/srv/downloads/"
fi
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8126/api/v1/health/ready >/dev/null
curl --fail --silent --show-error --max-time 15 https://j.qunxue.xyz/api/v1/health/ready >/dev/null
version=$(curl --fail --silent --show-error --max-time 15 https://j.qunxue.xyz/version.json)
python3 -c 'import json,sys; assert json.loads(sys.argv[1])["sha"] == sys.argv[2]' "$version" "$sha"
# API and worker must be running the verified immutable application image.
for service in api worker; do
  id=$("${compose[@]}" ps -q "$service")
  [[ -n "$id" && $(docker inspect "$id" --format '{{.Image}}') == "$JOBLENS_API_IMAGE" ]]
done
printf '%s\n' "$sha" > "$root/deployed-sha.tmp"
mv "$root/deployed-sha.tmp" "$root/deployed-sha"
echo "JobLens HTTP deployment verified at $sha; mail/upload acceptance is separate"
# Keep previous releases and all volumes; never run prune/down -v or Windup commands.

