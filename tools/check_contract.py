import json
from pathlib import Path

import yaml
from app.core.config import Settings
from app.main import create_app
from fastapi.routing import APIRoute
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[1]

METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}


def catalog(spec):
    return {
        op["operationId"]: (method, path, op)
        for path, item in spec["paths"].items()
        for method, op in item.items()
        if method in METHODS
    }


def check():
    spec = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text())
    validate(spec)
    operations = catalog(spec)
    assert len(operations) == 55, "contract operations lost or duplicated"
    implemented = json.loads((ROOT / "contracts/implemented.json").read_text())
    settings = Settings(
        database_url=SecretStr("postgresql+psycopg://unused:unused@localhost/unused")
    )
    app = create_app(settings)
    actual = app.openapi()
    runtime = catalog(actual)
    assert runtime.keys() == implemented.keys(), "runtime/implementation coverage drift"
    for route in app.routes:
        if isinstance(route, APIRoute):
            assert route.operation_id in implemented

    def expand(node, doc):
        if isinstance(node, dict):
            if "$ref" in node:
                target = doc
                for part in node["$ref"][2:].split("/"):
                    target = target[part]
                return expand(target, doc)
            return {
                k: expand(v, doc)
                for k, v in node.items()
                if k not in {"title", "description", "examples"}
            }
        if isinstance(node, list):
            return [expand(v, doc) for v in node]
        return node

    for oid, (method, path, op) in runtime.items():
        expected_method, expected_path, expected_op = operations[oid]
        assert (method, path) == (expected_method, "/api/v1" + expected_path), oid
        assert not op.get("requestBody") and not expected_op.get("requestBody")
        actual_success = op["responses"]["200"]["content"]["application/json"]["schema"]
        desired = expected_op["responses"]["200"]["content"]["application/json"]["schema"]
        # Pydantic singleton Literal uses const, JSON Schema uses a one-item enum.
        a, b = expand(actual_success, actual), expand(desired, spec)

        def normalize(node):
            if isinstance(node, dict):
                node = {k: normalize(v) for k, v in node.items()}
                if "const" in node:
                    node["enum"] = [node.pop("const")]
            return node

        assert normalize(a) == normalize(b), f"response drift: {oid}"
        assert "application/problem+json" in op["responses"]["default"]["content"]
    schemas = spec["components"]["schemas"]
    assert "preferences" in schemas["CaseProfile"]["required"]
    assert "preferences" not in schemas["ProfileWrite"]["properties"]
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    print(
        f"Contract: {len(spec['paths'])} paths / {len(operations)} operations / {len(schemas)} models; {len(runtime)} runtime operations verified"
    )


if __name__ == "__main__":
    check()
