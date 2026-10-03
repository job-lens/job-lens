#!/usr/bin/env bash
# Read-only host gate before transferring/loading images. No Windup commands.
set -euo pipefail
bytes=${1:?Pass total compressed bundle bytes}
[[ "$bytes" =~ ^[0-9]+$ ]] || exit 2
[[ -d /opt/job-lens && -f /etc/job-lens/joblens.env ]] || {
  echo 'Missing separately provisioned JobLens directory/configuration' >&2; exit 1;
}
[[ $(stat -c %a /etc/job-lens/joblens.env) == 600 ]] || exit 1
# Conservative transfer + image-layer + runtime/backup allowance. Do not prune.
free_bytes=$(df --output=avail -B1 /opt/job-lens | tail -1 | tr -d ' ')
(( free_bytes > bytes * 4 + 2147483648 )) || {
  echo 'Insufficient disk headroom; do not clean or resize Windup automatically' >&2; exit 1;
}
# This is a floor, not proof of peak shared-host safety. Existing services retain their caps.
available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( available_kib >= 2097152 )) || { echo 'Less than 2 GiB currently available; stop' >&2; exit 1; }
getent ahosts j.qunxue.xyz >/dev/null || { echo 'JobLens public DNS does not resolve' >&2; exit 1; }
# Do not replace another service's ports; an existing JobLens deployment is allowed.
ports=$(ss -ltnH '( sport = :443 or sport = :8126 )')
if [[ -n "$ports" ]]; then
  ids=$(docker ps -q --filter label=com.docker.compose.project=joblens-release --filter label=com.docker.compose.service=gateway)
  [[ -n "$ids" ]] || { echo 'JobLens ports are already occupied by another service' >&2; exit 1; }
fi
docker compose version >/dev/null
echo 'Read-only host preflight passed; resource snapshot is not a peak-load guarantee'
