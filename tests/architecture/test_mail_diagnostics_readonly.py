import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/read_mail_diagnostics.py"
SPEC = importlib.util.spec_from_file_location("mail_diagnostics", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
REVISION = "a" * 40
API = "b" * 64
LINE = (
    "2026-10-04T11:35:00.123456789Z WARNING:job_lens.email:"
    "email_delivery_failed category=provider_http provider_status=403 "
    "provider_code=validation_error trace_id=mail-trace-1"
)


def test_log_output_is_reconstructed_and_allowlisted():
    raw = "private-key recipient@example.invalid\n" + LINE + "\nprivate-body"
    count, rows = module.filter_records(raw)
    assert count == 1
    assert rows == [
        {
            "timestamp": "2026-10-04T11:35:00.123456789Z",
            "category": "provider_http",
            "provider_status": "403",
            "provider_code": "validation_error",
            "trace_id": "mail-trace-1",
        }
    ]
    assert "private" not in json.dumps(rows)


@pytest.mark.parametrize(
    "line",
    [
        LINE + " recipient=private@example.invalid",
        LINE.replace("validation_error", "private_secret"),
        LINE.replace("provider_http", "private_secret"),
        LINE.replace("403", "999"),
        LINE.replace("mail-trace-1", "private@example.invalid"),
        LINE.replace("mail-trace-1", "x" * 65),
        LINE.replace("mail-trace-1", "mail-trace-1/private"),
        LINE.replace("2026-10-04T11:35:00.123456789Z", "private"),
        LINE + "\x1b[0m",
        "private" * 200 + LINE,
    ],
)
def test_untrusted_or_partial_records_are_discarded(line):
    assert module.filter_records(line) == (0, [])


def test_unknown_fields_and_output_count_are_bounded():
    line = LINE.replace("403", "unknown").replace("validation_error", "unknown")
    count, rows = module.filter_records("\n".join([line] * 45))
    assert count == 45 and len(rows) == 40
    assert rows[0]["provider_code"] == "unknown"


def test_collect_only_uses_three_fixed_docker_reads(tmp_path):
    marker = tmp_path / "deployed-sha"
    marker.write_text(REVISION + "\n")
    read = Mock(side_effect=[API + "\n", "joblens-release api " + REVISION, LINE])
    result = module.collect(REVISION, read=read, marker=marker)
    assert result["matching_record_count"] == 1
    assert result["api_revision_verified"] is True
    calls = [call.args[0] for call in read.call_args_list]
    assert calls == [
        [
            "docker",
            "ps",
            "--quiet",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=joblens-release",
            "--filter",
            "label=com.docker.compose.service=api",
        ],
        [
            "docker",
            "inspect",
            "--format",
            (
                '{{index .Config.Labels "com.docker.compose.project"}} '
                '{{index .Config.Labels "com.docker.compose.service"}} '
                '{{index .Config.Labels "org.opencontainers.image.revision"}}'
            ),
            API,
        ],
        ["docker", "logs", "--since", "24h", "--tail", "20000", "--timestamps", API],
    ]


@pytest.mark.parametrize(
    "ids,identity,reason",
    [
        ("", "", "expected_one_joblens_api"),
        (API + "\n" + API, "", "expected_one_joblens_api"),
        ("--malicious-option", "", "expected_one_joblens_api"),
        (API, "other-project api " + REVISION, "api_identity_mismatch"),
        (API, "joblens-release worker " + REVISION, "api_identity_mismatch"),
        (API, "joblens-release api " + "c" * 40, "api_identity_mismatch"),
    ],
)
def test_wrong_container_or_revision_stops_before_logs(tmp_path, ids, identity, reason):
    marker = tmp_path / "deployed-sha"
    marker.write_text(REVISION)
    read = Mock(side_effect=[ids, identity])
    with pytest.raises(module.DiagnosticError, match=reason):
        module.collect(REVISION, read=read, marker=marker)
    assert all(call.args[0][1] != "logs" for call in read.call_args_list)


def test_marker_mismatch_stops_before_docker(tmp_path):
    marker = tmp_path / "deployed-sha"
    marker.write_text("c" * 40)
    read = Mock()
    with pytest.raises(module.DiagnosticError, match="deployed_revision_mismatch"):
        module.collect(REVISION, read=read, marker=marker)
    read.assert_not_called()


def test_no_records_is_explicitly_inconclusive(tmp_path):
    marker = tmp_path / "deployed-sha"
    marker.write_text(REVISION)
    read = Mock(side_effect=[API, "joblens-release api " + REVISION, "private-log"])
    result = module.collect(REVISION, read=read, marker=marker)
    assert result["result"] == "no_matching_records_inconclusive"
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "program,limit,timeout,reason",
    [
        ("print('private-' * 10000)", 100, 3, "read_limit_exceeded"),
        ("import time; time.sleep(10)", 100, 0.1, "read_timeout"),
        ("import sys; print('private-error'); sys.exit(1)", 100, 3, "docker_read_failed"),
    ],
)
def test_capture_fails_closed(program, limit, timeout, reason):
    with pytest.raises(module.DiagnosticError, match=reason) as error:
        module.capture([sys.executable, "-c", program], limit=limit, timeout=timeout)
    assert "private" not in str(error.value)


def test_capture_success():
    assert module.capture([sys.executable, "-c", "print('safe')"]) == "safe\n"


def test_cli_suppresses_exception_details():
    result = subprocess.run(
        [sys.executable, str(SOURCE), "not-a-sha"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1 and not result.stderr
    assert json.loads(result.stdout) == {
        "result": "diagnostic_failed",
        "reason": "invalid_expected_revision",
    }


def test_workflow_uses_existing_input_and_keeps_deployment_main_only():
    doc = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text())
    jobs = doc["jobs"]
    diagnostic = jobs["mail-diagnostics"]
    assert "github.ref == 'refs/heads/main'" in jobs["deploy"]["if"]
    assert "github.event_name == 'workflow_dispatch'" in diagnostic["if"]
    assert "refs/heads/diagnose/email-logs-readonly-42" in diagnostic["if"]
    assert diagnostic["environment"]["name"] == "Production"
    assert doc["permissions"] == {"contents": "read", "actions": "read"}
    assert doc["concurrency"] == {"group": "joblens-production", "cancel-in-progress": False}
    diagnostic_text = json.dumps(diagnostic)
    assert "${{ inputs.revision ||" in diagnostic_text
    assert "b4cd4c687dd06c81fe17df81cf63422787f1342e" in diagnostic_text
    assert doc[True]["push"] == {"branches": ["diagnose/email-logs-readonly-42"]}
    assert "github.event_name == 'push'" in diagnostic["if"]
    assert "StrictHostKeyChecking=yes" in diagnostic_text
    assert "python3 - $EXPECTED_REVISION" in diagnostic_text
    for forbidden in ["scp", "docker exec", "docker run", "deploy_joblens.sh", "ssh-keyscan"]:
        assert forbidden not in diagnostic_text
