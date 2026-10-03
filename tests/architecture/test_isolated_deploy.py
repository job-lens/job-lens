import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class DeploymentIsolation(unittest.TestCase):
    def test_no_windup_mount_or_shared_port(self):
        doc = yaml.safe_load((ROOT / "infra/compose.production.yaml").read_text())
        self.assertEqual(doc["name"], "joblens-release")
        self.assertEqual(doc["services"]["gateway"]["ports"], ["127.0.0.1:8126:80", "443:443"])
        for name, service in doc["services"].items():
            self.assertNotIn("container_name", service)
            self.assertNotIn("network_mode", service)
            if name != "gateway":
                self.assertNotIn("ports", service)
            self.assertNotIn("build", service)
            for mount in service.get("volumes", []):
                self.assertNotIn("windup", mount.lower())
        self.assertTrue(all(value is None for value in doc["volumes"].values()))
        self.assertEqual(
            doc["networks"]["default"]["driver_opts"]["com.docker.network.driver.mtu"], "1450"
        )

    def test_tls_leaves_host_http_alone(self):
        text = (ROOT / "infra/Caddyfile.production").read_text()
        self.assertIn("auto_https disable_redirects", text)
        self.assertIn("disable_http_challenge", text)
        self.assertIn("https://j.qunxue.xyz", text)
        self.assertIn("reverse_proxy api:8000", text)

    def test_only_explicit_joblens_compose(self):
        text = (ROOT / "tools/deploy_joblens.sh").read_text()
        self.assertIn("--project-name joblens-release", text)
        self.assertIn('-f "$PWD/compose.production.yaml"', text)
        self.assertNotIn("systemctl", text)
        self.assertNotIn("docker system", text)
        self.assertIn("--no-build --pull never", text)

    def test_release_workflow_scoped_and_no_windup_secrets(self):
        text = (ROOT / ".github/workflows/deploy.yml").read_text()
        yaml.safe_load(text)
        self.assertIn("JOBLENS_DEPLOY_PASSWORD", text)
        self.assertNotIn("WINDUP_DEPLOY_", text)
        self.assertIn("git merge-base --is-ancestor", text)
        self.assertIn('.event == "push"', text)
        self.assertIn("StrictHostKeyChecking=yes", text)
        self.assertNotIn("ssh-keyscan", text)

    def test_deploy_revision_gate(self):
        # Execute the actual workflow shell with stubbed Git/GitHub reads.
        doc = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text())
        step = next(s for s in doc["jobs"]["deploy"]["steps"] if s.get("id") == "release")
        script = step["run"]
        self.assertNotIn("gh release", script)
        sha = "a" * 40
        base_run = dict(name="Architecture CI", head_sha=sha, head_branch="main",
                        event="push", status="completed", conclusion="success",
                        run_started_at="2026-01-01T00:00:00Z")
        cases = [
            (sha, [base_run], "0", True),
            ("main", [base_run], "0", False),
            (sha, [base_run], "1", False),
            (sha, [{**base_run, "head_branch": "feature"}], "0", False),
            (sha, [{**base_run, "conclusion": "failure"}], "0", False),
            (sha, [{**base_run, "status": "in_progress"}], "0", False),
            (sha, [], "0", False),
            (sha, [base_run, {**base_run, "run_started_at": "2026-01-02T00:00:00Z",
                              "conclusion": "failure"}], "0", False),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "git").write_text('#!/bin/bash\ncase "$1" in\nrev-parse) printf "%s\\n" "$EXPECTED_SHA";;\nmerge-base) exit "$ANCESTOR_EXIT";;\ncheckout) touch "$CHECKOUT_MARKER";;\n*) exit 99;;\nesac\n')
            (path / "gh").write_text('#!/bin/bash\ncat "$RUNS_JSON"\n')
            for name in ("git", "gh"):
                (path / name).chmod(0o755)
            for revision, runs, ancestor_exit, expected in cases:
                with self.subTest(revision=revision, runs=runs, ancestor_exit=ancestor_exit):
                    marker = path / "checkout"
                    marker.unlink(missing_ok=True)
                    output = path / "output"
                    output.unlink(missing_ok=True)
                    (path / "runs.json").write_text(json.dumps({"workflow_runs": runs}))
                    env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}",
                           "DEPLOY_REVISION": revision, "EXPECTED_SHA": sha,
                           "ANCESTOR_EXIT": ancestor_exit, "CHECKOUT_MARKER": str(marker),
                           "RUNS_JSON": str(path / "runs.json"), "GITHUB_OUTPUT": str(output),
                           "GITHUB_REPOSITORY": "job-lens/job-lens"}
                    result = subprocess.run(["bash", "-c", script], env=env,
                                            capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode == 0, expected, result.stderr)
                    self.assertEqual(marker.exists(), expected)
                    if expected:
                        self.assertEqual(output.read_text(), f"sha={sha}\n")


if __name__ == "__main__":
    unittest.main()
