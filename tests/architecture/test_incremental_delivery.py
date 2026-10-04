import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


class IncrementalTests(unittest.TestCase):
    def test_service_scope(self):
        from release_scope import classify
        self.assertEqual(classify(['apps/web/src/main.tsx']), {'api': False, 'web': True, 'migrations': False})
        self.assertEqual(classify(['apps/api/app/main.py']), {'api': True, 'web': False, 'migrations': False})
        self.assertEqual(classify(['README.md', '.github/workflows/deploy.yml', 'tools/deploy_joblens.sh']), {'api': False, 'web': False, 'migrations': False})
        self.assertTrue(classify(['apps/api/alembic/versions/new.py'])['migrations'])
        self.assertTrue(classify(['infra/Caddyfile.production'])['web'])

    def test_layers_are_reused_and_corruption_fails_closed(self):
        from image_layers import assemble, export_archive
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'image.tar'
            with tarfile.open(source, 'w') as archive:
                for name, data in [('manifest.json', b'[]'), ('layers/base.tar', b'shared-base'), ('config.json', b'{}')]:
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            recipe = export_archive(source, root / 'blobs')
            first = set((root / 'blobs').iterdir())
            self.assertEqual(export_archive(source, root / 'blobs'), recipe)
            self.assertEqual(set((root / 'blobs').iterdir()), first)
            target = root / 'restored.tar'
            assemble(recipe, root / 'blobs', target)
            with tarfile.open(target) as archive:
                self.assertEqual(archive.extractfile('layers/base.tar').read(), b'shared-base')
            next(iter(first)).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'digest'):
                assemble(recipe, root / 'blobs', root / 'bad.tar')

    def test_archive_traversal_is_rejected(self):
        from image_layers import export_archive
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with tarfile.open(root / 'bad.tar', 'w') as archive:
                archive.addfile(tarfile.TarInfo('../escape'), io.BytesIO())
            with self.assertRaises(ValueError):
                export_archive(root / 'bad.tar', root / 'blobs')


if __name__ == '__main__':
    unittest.main()
