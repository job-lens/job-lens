import json
from copy import deepcopy

import pytest
import yaml
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from tools.check_contract import ROOT, catalog, validate_runtime


def documents():
    spec = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text())
    settings = Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        trusted_hosts=["testserver"],
        _env_file=None,
    )
    return (
        spec,
        create_app(settings).openapi(),
        json.loads((ROOT / "contracts/implemented.json").read_text()),
    )


def test_runtime_signatures_and_error_media():
    validate_runtime(*documents())


@pytest.mark.parametrize(
    "change", ["method", "success_type", "required_query", "body", "error_media", "owner"]
)
def test_runtime_drift_is_rejected(change):
    spec, actual, implemented = documents()
    route = actual["paths"]["/api/v1/health/live"]
    operation = route["get"]
    if change == "method":
        route["post"] = route.pop("get")
    elif change == "success_type":
        actual["components"]["schemas"]["Health"]["properties"]["status"] = {"type": "integer"}
    elif change == "required_query":
        operation["parameters"] = [
            {"name": "new_input", "in": "query", "required": True, "schema": {"type": "string"}}
        ]
    elif change == "body":
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": {"type": "string"}}},
        }
    elif change == "error_media":
        operation["responses"]["default"]["content"] = {
            "application/json": {"schema": {"type": "object"}}
        }
    else:
        implemented["health_live"] = "training"
    with pytest.raises(AssertionError):
        validate_runtime(spec, actual, implemented)


def test_duplicate_operations_are_rejected():
    spec, _, _ = documents()
    spec["paths"]["/duplicate"] = deepcopy(spec["paths"]["/health/live"])
    with pytest.raises(ValueError, match="Duplicate"):
        catalog(spec)


def test_actual_http_responses_follow_shared_schema():
    spec, _, _ = documents()
    base = "https://job-lens.invalid/schema"
    registry = Registry().with_resource(
        base, Resource.from_contents(spec, default_specification=DRAFT202012)
    )

    class UnavailableDatabase:
        def ready(self):
            return False

    settings = Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        trusted_hosts=["testserver"],
        _env_file=None,
    )
    with TestClient(create_app(settings, UnavailableDatabase())) as client:
        for route, name, code in [("live", "Health", 200), ("ready", "Problem", 503)]:
            response = client.get("/api/v1/health/" + route)
            assert response.status_code == code
            Draft202012Validator(
                {"$ref": base + "#/components/schemas/" + name}, registry=registry
            ).validate(response.json())
