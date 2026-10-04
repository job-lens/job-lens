#!/usr/bin/env bash
# Publish a tested APK only. No service restart, database access, or Windup changes.
set -euo pipefail
root=/opt/job-lens
sha=${1:?expected APK SHA256}
revision=${2:?exact source revision}
[[ "$sha" =~ ^[0-9a-f]{64}$ && "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 2
incoming="$root/android-incoming/$sha.apk"
[[ -f "$incoming" && ! -L "$incoming" ]] || exit 2
printf '%s  %s\n' "$sha" "$incoming" | sha256sum --check --status
exec 9>"$root/deploy.lock"
flock -w 120 9
mapfile -t gateways < <(docker ps -q --filter label=com.docker.compose.project=joblens-release --filter label=com.docker.compose.service=gateway)
[[ ${#gateways[@]} == 1 && -n "${gateways[0]}" ]] || { echo 'Expected exactly one JobLens gateway' >&2; exit 1; }
gateway=${gateways[0]}
downloads="$root/downloads"
install -d -m 0755 "$downloads"
name="joblens-android-test-$revision.apk"
install -m 0644 "$incoming" "$downloads/$name.tmp"
mv "$downloads/$name.tmp" "$downloads/$name"
printf '%s  %s\n' "$sha" "$name" > "$downloads/$name.sha256"
chmod 0644 "$downloads/$name.sha256"
docker exec "$gateway" mkdir -p /srv/downloads
docker cp "$downloads/$name" "$gateway:/srv/downloads/$name.tmp"
docker exec "$gateway" mv "/srv/downloads/$name.tmp" "/srv/downloads/$name"
docker cp "$downloads/$name.sha256" "$gateway:/srv/downloads/$name.sha256"
# Only advertise latest after the versioned public URL returns the correct bytes.
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
curl --fail --silent --show-error --max-time 90 "https://j.qunxue.xyz/downloads/$name" -o "$tmp"
printf '%s  %s\n' "$sha" "$tmp" | sha256sum --check --status
ln -sfn "$name" "$downloads/joblens-android-test.apk"
docker exec "$gateway" ln -sfn "$name" /srv/downloads/joblens-android-test.apk
printf '{"sha256":"%s","revision":"%s","channel":"test"}\n' "$sha" "$revision" > "$downloads/android.json.tmp"
chmod 0644 "$downloads/android.json.tmp"
mv "$downloads/android.json.tmp" "$downloads/android.json"
docker cp "$downloads/android.json" "$gateway:/srv/downloads/android.json.tmp"
docker exec "$gateway" mv /srv/downloads/android.json.tmp /srv/downloads/android.json
printf 'Verified https://j.qunxue.xyz/downloads/%s\n' "$name"
