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


if __name__ == "__main__":
    unittest.main()
