"""Content-address Docker save members; SSH/rsync sends only absent blobs.

The cache is confined to JobLens. Each release keeps its immutable recipe;
untrusted or partially transferred cache bytes are checked before docker load.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name:
        raise ValueError('Unsafe image archive path')


def export_archive(source, blobs):
    blobs.mkdir(parents=True, exist_ok=True)
    recipe = []
    names = set()
    with tarfile.open(source, 'r:*') as archive:
        for member in archive:
            if member.isdir():
                continue
            safe_name(member.name)
            if not member.isfile() or member.name in names:
                raise ValueError('Image links/devices/duplicate members forbidden')
            names.add(member.name)
            with archive.extractfile(member) as stream, tempfile.NamedTemporaryFile(dir=blobs, delete=False) as target:
                temporary = Path(target.name)
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
                    target.write(chunk)
            key = digest.hexdigest()
            destination = blobs / key
            if destination.exists():
                temporary.unlink()
            else:
                os.replace(temporary, destination)
            recipe.append({'name': member.name, 'sha256': key, 'size': member.size})
    return recipe


def assemble(recipe, blobs, target):
    names = set()
    # Validate the entire cache before emitting anything to Docker.
    for item in recipe:
        safe_name(item['name'])
        if item['name'] in names or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid image recipe')
        names.add(item['name'])
        path = blobs / item['sha256']
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item['size']:
            raise ValueError('Image blob size/digest mismatch')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                raise ValueError('Image blob digest mismatch')
    options = {'fileobj': target, 'mode': 'w|'} if hasattr(target, 'write') else {'name': target, 'mode': 'w'}
    with tarfile.open(**options) as archive:
        for item in recipe:
            member = tarfile.TarInfo(item['name'])
            member.size = item['size']
            member.mode = 0o644
            with (blobs / item['sha256']).open('rb') as stream:
                archive.addfile(member, stream)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['export', 'assemble'])
    parser.add_argument('archive', type=Path)
    parser.add_argument('blobs', type=Path)
    parser.add_argument('recipe', type=Path)
    args = parser.parse_args()
    if args.mode == 'export':
        args.recipe.write_text(json.dumps(export_archive(args.archive, args.blobs)) + '\n')
    else:
        assemble(json.loads(args.recipe.read_text()), args.blobs, sys.stdout.buffer if str(args.archive) == '-' else args.archive)


if __name__ == '__main__':
    main()
