#!/usr/bin/env bash
# Independent JobLens update: only explicitly selected services, never neighboring projects.
set -euo pipefail
umask 077
readonly root=/opt/job-lens
readonly config=/etc/job-lens/joblens.env
sha=${1:?Usage: deploy_joblens.sh EXACT_SHA}
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ -f "$root/runtime-override.yaml" && -d "$root/releases/$sha" && -f "$config" && ! -L "$config" ]] || exit 1
[[ $(stat -c %a "$config") == 600 ]] || exit 1
cd "$root/releases/$sha"
exec 9>"$root/deploy.lock"
flock -n 9 || { echo 'Another JobLens deployment is active' >&2; exit 1; }
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES
sha256sum --check SHA256SUMS --status
base=$(python3 -c 'import json; print(json.load(open("release.json"))["base"])')
[[ $(cat "$root/deployed-sha") == "$base" ]] || { echo 'Production baseline changed; stop' >&2; exit 1; }
api=$(python3 -c 'import json; print(str(json.load(open("release.json"))["api"]).lower())')
web=$(python3 -c 'import json; print(str(json.load(open("release.json"))["web"]).lower())')
migrations=$(python3 -c 'import json; print(str(json.load(open("release.json"))["migrations"]).lower())')
[[ "$migrations" == false ]] || { echo 'New migration requires an audited compatible maintenance release; no service changed' >&2; exit 1; }
started=$SECONDS
# Snapshot IDs only; no configuration or environment secrets are logged.
previous_api=$(docker ps -q --filter label=com.docker.compose.project=joblens-release --filter label=com.docker.compose.service=api)
previous_worker=$(docker ps -q --filter label=com.docker.compose.project=joblens-release --filter label=com.docker.compose.service=worker)
previous_web=$(docker ps -q --filter label=com.docker.compose.project=joblens-release --filter label=com.docker.compose.service=gateway)
previous_db=$(docker ps -q --filter label=com.docker.compose.project=joblens-release --filter label=com.docker.compose.service=db)
[[ -n "$previous_api" && -n "$previous_worker" && -n "$previous_web" && -n "$previous_db" ]]
old_api=$(docker inspect "$previous_api" --format '{{.Image}}')
old_web=$(docker inspect "$previous_web" --format '{{.Image}}')
export JOBLENS_API_IMAGE="$old_api" JOBLENS_WEB_IMAGE="$old_web"
export JOBLENS_POSTGRES_IMAGE=$(docker inspect "$previous_db" --format '{{.Image}}')
previous_dir=$(docker inspect "$previous_web" --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}')
[[ "$previous_dir" == "$root/"* && -f "$previous_dir/compose.production.yaml" ]]
compose=(docker compose --project-name joblens-release --env-file "$config" -f "$PWD/compose.production.yaml" -f "$root/runtime-override.yaml")
"${compose[@]}" config --quiet
for kind in api web; do
  selected=$api; [[ "$kind" == api ]] || selected=$web
  [[ "$selected" == true ]] || continue
  # Reconstruct verified archive locally; unchanged blobs are reused, never retransmitted.
  python3 image_layers.py assemble "$kind.tar" "$root/image-blobs" "$kind.recipe.json"
  docker load < "$kind.tar" >/dev/null
  rm "$kind.tar"
  producer=$(python3 -c 'import json,sys; print(next(x["producer_id"] for x in json.load(open("image-identities.json")) if x["tag"]==sys.argv[1]))' "joblens-$kind:$sha")
  actual=$(python3 verify_image_identity.py verify image-identities.json "joblens-$kind:$sha" "$producer")
  if [[ "$kind" == api ]]; then export JOBLENS_API_IMAGE="$actual"; else export JOBLENS_WEB_IMAGE="$actual"; fi
done
services=()
[[ "$api" != true ]] || services+=(api worker)
[[ "$web" != true ]] || services+=(gateway)
# A failed health check rolls back only selected code, never DB volumes or schema.
changed=false
rollback() {
  code=$?
  if (( code != 0 )) && [[ "$changed" == true ]]; then
    trap - EXIT HUP INT TERM
    export JOBLENS_API_IMAGE="$old_api" JOBLENS_WEB_IMAGE="$old_web"
    docker compose --project-name joblens-release --env-file "$config" -f "$previous_dir/compose.production.yaml" -f "$root/runtime-override.yaml" up -d --no-deps --no-build --pull never --wait --wait-timeout 180 "${services[@]}" || { echo 'Rollback failed: operator required' >&2; exit 1; }
    curl --fail --silent --show-error --max-time 15 http://127.0.0.1:8126/api/v1/health/ready >/dev/null || { echo 'Rollback health failed: operator required' >&2; exit 1; }
    echo 'Affected application images rolled back; database untouched' >&2
  fi
  exit "$code"
}
trap rollback EXIT
trap 'exit 1' HUP INT TERM
if [[ "$api" == true ]]; then
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
fi
if [[ "$web" == true ]]; then
  "${compose[@]}" run --rm --no-deps gateway caddy validate --config /etc/caddy/Caddyfile >/dev/null
fi
changed=true
"${compose[@]}" up -d --no-deps --no-build --pull never --wait --wait-timeout 180 "${services[@]}"
# Preserve independently published native downloads after a gateway replacement.
if [[ "$web" == true && -d "$root/downloads" ]]; then
  gateway=$("${compose[@]}" ps -q gateway)
  [[ -n "$gateway" ]]
  docker exec "$gateway" mkdir -p /srv/downloads
  docker cp "$root/downloads/." "$gateway:/srv/downloads/"
fi
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:8126/api/v1/health/ready >/dev/null
curl --fail --silent --show-error --max-time 15 https://j.qunxue.xyz/api/v1/health/ready >/dev/null
if [[ "$web" == true ]]; then
  version=$(curl --fail --silent --show-error --max-time 15 https://j.qunxue.xyz/version.json)
  python3 -c 'import json,sys; assert json.loads(sys.argv[1])["sha"] == sys.argv[2]' "$version" "$sha"
fi
for service in api worker; do
  id=$("${compose[@]}" ps -q "$service")
  [[ -n "$id" && $(docker inspect "$id" --format '{{.Image}}') == "$JOBLENS_API_IMAGE" ]]
done
[[ $("${compose[@]}" ps -q db) == "$previous_db" ]]
[[ "$api" == true ]] || { [[ $("${compose[@]}" ps -q api) == "$previous_api" && $("${compose[@]}" ps -q worker) == "$previous_worker" ]]; }
[[ "$web" == true ]] || [[ $("${compose[@]}" ps -q gateway) == "$previous_web" ]]
printf '%s\n' "$sha" > "$root/deployed-sha.tmp"
mv "$root/deployed-sha.tmp" "$root/deployed-sha"
changed=false
printf 'Deployment seconds=%s; restarted services=%s; database image/ID unchanged; database backup bytes=0\n' "$((SECONDS-started))" "${services[*]}"
# Previous image IDs/releases remain available for finite code rollback; no prune/down.
