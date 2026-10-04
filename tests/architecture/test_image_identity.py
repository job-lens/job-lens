import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "identity", Path(__file__).resolve().parents[2] / "tools/verify_image_identity.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(path, layer=b"approved-rootfs", actual_layer=None, extra=None, tag=None):
    config = {
        "os": "linux",
        "architecture": "amd64",
        "rootfs": {"diff_ids": ["sha256:" + hashlib.sha256(layer).hexdigest()]},
        "config": {"Labels": {"org.opencontainers.image.revision": "a" * 40}},
    }
    if extra:
        config["config"].update(extra)
    raw = json.dumps(config).encode()
    manifest = [
        {
            "Config": "config.json",
            "RepoTags": [tag or "joblens-web:" + "a" * 40],
            "Layers": ["layer.tar"],
        }
    ]
    with tarfile.open(path, "w") as tar:
        for name, data in [
            ("config.json", raw),
            ("manifest.json", json.dumps(manifest).encode()),
            ("layer.tar", layer if actual_layer is None else actual_layer),
        ]:
            item = tarfile.TarInfo(name)
            item.size = len(data)
            tar.addfile(item, io.BytesIO(data))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "image.tar"
        fixture(self.path)
        self.canonical = m.archive_identity(self.path)
        self.meta = {
            "tag": "joblens-web:" + "a" * 40,
            "producer_id": "sha256:" + "b" * 64,
            "canonical": self.canonical,
        }
        self.actual = "sha256:" + "c" * 64

    def export(self, command, stdout, check):
        self.assertEqual(command[-1], self.actual)
        stdout.write(self.path.read_bytes())

    def test_different_engine_id_requires_same_config_and_layers(self):
        info = {"Id": self.actual, "RootFS": {"Layers": self.canonical["diff_ids"]}}
        with (
            patch.object(m, "inspect", return_value=info),
            patch.object(m.subprocess, "run", side_effect=self.export),
        ):
            self.assertEqual(m.verify(self.meta, self.meta["producer_id"]), self.actual)

    def test_modified_config_is_rejected_despite_identical_rootfs(self):
        fixture(self.path, extra={"Env": ["TAMPER=1"]})
        info = {"Id": self.actual, "RootFS": {"Layers": self.canonical["diff_ids"]}}
        with (
            patch.object(m, "inspect", return_value=info),
            patch.object(m.subprocess, "run", side_effect=self.export),
        ):
            with self.assertRaisesRegex(ValueError, "config or layer"):
                m.verify(self.meta, self.meta["producer_id"])

    def test_corrupt_layer_is_rejected(self):
        fixture(self.path, actual_layer=b"tampered-rootfs")
        with self.assertRaisesRegex(ValueError, "Layer content"):
            m.archive_identity(self.path)

    def test_record_on_docker_without_platform_inspect(self):
        revision = "a" * 40
        directory = Path(self.tmp.name)
        for kind in ("api", "web", "postgres"):
            fixture(directory / f"{kind}.tar.gz", tag=f"joblens-{kind}:{revision}")
        metadata = directory / "identities.json"
        info = {"Id": self.actual, "RootFS": {"Layers": self.canonical["diff_ids"]}}

        def docker(command, **kwargs):
            if "--platform" in command:
                raise subprocess.CalledProcessError(125, command)
            return subprocess.CompletedProcess(command, 0, json.dumps([info]).encode())

        with (
            patch.object(
                m.sys, "argv", ["verify", "record", str(metadata), str(directory), revision]
            ),
            patch.object(m.subprocess, "run", side_effect=docker),
        ):
            m.main()
        recorded = json.loads(metadata.read_text())
        self.assertEqual(len(recorded), 3)
        self.assertEqual(recorded[0]["producer_id"], self.actual)
        self.assertEqual(recorded[0]["canonical"]["architecture"], "amd64")

    def test_unknown_tag_and_producer_are_rejected(self):
        with self.assertRaises(ValueError):
            m.archive_identity(self.path, "unknown:latest")
        with patch.object(m, "inspect") as inspect:
            with self.assertRaisesRegex(ValueError, "Producer ID"):
                m.verify(self.meta, "sha256:" + "d" * 64)
            inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
