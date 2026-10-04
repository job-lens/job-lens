"""Record exact source/config/rootfs identity for affected images only."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from image_layers import export_archive
from verify_image_identity import archive_identity, inspect


def main():
    revision = sys.argv[1]
    bundle = Path('bundle')
    scope = json.loads((bundle / 'release.json').read_text())
    records = []
    for kind in ('api', 'web'):
        if not scope[kind]:
            continue
        tag = f'joblens-{kind}:{revision}'
        with tempfile.NamedTemporaryFile(suffix='.tar') as saved:
            subprocess.run(['docker', 'save', tag], stdout=saved, check=True)
            saved.flush()
            canonical = archive_identity(saved.name, tag)
            info = inspect(tag)
            if canonical['revision'] != revision or info['RootFS']['Layers'] != canonical['diff_ids']:
                raise ValueError('Built image differs from checked source/rootfs')
            recipe = export_archive(saved.name, Path('blobs'))
        (bundle / f'{kind}.recipe.json').write_text(json.dumps(recipe) + '\n')
        records.append({'tag': tag, 'producer_id': info['Id'], 'canonical': canonical})
    (bundle / 'image-identities.json').write_text(json.dumps(records) + '\n')


if __name__ == '__main__':
    main()
