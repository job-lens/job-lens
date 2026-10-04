import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


class DatabaseProbe:
    def __init__(self, available=True, error=False):
        self.available, self.error = available, error

    def ready(self):
        if self.error:
            raise RuntimeError("postgres-secret-connection-string")
        return self.available


@pytest.fixture
def settings():
    return Settings(
        database_url="postgresql+psycopg://test@localhost/job_lens_test",
        trusted_hosts=["testserver"],
        _env_file=None,
    )


@pytest.mark.parametrize(
    "available,error,status", [(True, False, 200), (False, False, 503), (False, True, 503)]
)
def test_health_checks(settings, available, error, status):
    with TestClient(create_app(settings, DatabaseProbe(available, error))) as client:
        assert client.get("/api/v1/health/live").json() == {"status": "ok"}
        result = client.get("/api/v1/health/ready")
        assert result.status_code == status
        assert result.headers["cache-control"] == "no-store"
        assert "postgres-secret" not in result.text
        if status == 503:
            assert result.headers["content-type"].startswith("application/problem+json")
            assert result.json()["trace_id"] == result.headers["x-request-id"]


def test_readiness_failure_logs_exception_type_without_connection_secrets(settings, caplog):
    with TestClient(create_app(settings, DatabaseProbe(error=True))) as client:
        assert client.get("/api/v1/health/ready").status_code == 503
    assert "database_readiness_failed type=RuntimeError" in caplog.text
    assert "postgres-secret-connection-string" not in caplog.text


def test_business_routes_require_auth_and_errors_keep_http_status(settings):
    with TestClient(create_app(settings, DatabaseProbe())) as client:
        result = client.get("/api/v1/tasks")
        assert result.status_code == 401
        assert result.json()["status"] == 401
        assert result.json()["code"] == "UNAUTHENTICATED"
        paths = client.get("/api/openapi.json").json()["paths"]
        assert "/api/v1/tasks" in paths
        result = client.get("/api/v1/health/live", headers={"X-Request-ID": "trace-123"})
        assert result.headers["x-request-id"] == "trace-123"
        result = client.get("/api/v1/health/live", headers={"X-Request-ID": "a" * 1000})
        assert len(result.headers["x-request-id"]) == 32
        assert (
            client.get("/api/v1/health/live", headers={"Host": "evil.invalid"}).status_code == 400
        )


def test_host_rejection_uses_the_shared_problem_contract(settings):
    with TestClient(create_app(settings, DatabaseProbe())) as client:
        result = client.get("/api/v1/health/live", headers={"Host": "untrusted.invalid"})
        assert result.status_code == 400
        assert result.headers["content-type"].startswith("application/problem+json")
        assert result.json()["trace_id"] == result.headers["x-request-id"]


def test_method_rejection_preserves_allow_header(settings):
    with TestClient(create_app(settings, DatabaseProbe())) as client:
        result = client.post("/api/v1/health/live")
        assert result.status_code == 405
        assert "GET" in result.headers["allow"]
        assert result.json()["status"] == 405
        assert result.headers["content-type"].startswith("application/problem+json")


def test_me_requires_a_session_cookie(settings):
    with TestClient(create_app(settings, DatabaseProbe())) as client:
        result = client.get("/api/v1/me")
        assert result.status_code == 401
        assert result.headers["content-type"].startswith("application/problem+json")
        assert result.json()["code"] == "UNAUTHENTICATED"
        assert result.headers["cache-control"] == "no-store"
