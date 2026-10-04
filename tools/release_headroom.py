"""Bound additional disk use for the JobLens-only streaming image importer."""
import json
import re
import sys
from pathlib import Path


def required_bytes(release, cache):
    missing = {}
    archive_bytes = 0
    for recipe in release.glob('*.recipe.json'):
        for item in json.loads(recipe.read_text()):
            key, size = item['sha256'], item['size']
            if not re.fullmatch('[0-9a-f]{64}', key) or not isinstance(size, int) or size < 0:
                raise ValueError('Invalid content recipe')
            archive_bytes += size
            blob = cache / key
            if blob.is_symlink() or (blob.exists() and blob.stat().st_size != size):
                raise ValueError('Invalid cached content')
            if not blob.exists():
                missing[key] = size
    # Missing cache members + Docker load temporary/import growth (2x raw archive).
    # Streaming avoids a second saved tar; 512 MiB remains for runtime/log growth.
    return sum(missing.values()) + archive_bytes * 2 + 512 * 1024 * 1024


if __name__ == '__main__':
    print(required_bytes(Path(sys.argv[1]), Path(sys.argv[2])))
