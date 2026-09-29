"""Validate the product contract and compare each wired operation with runtime OpenAPI."""

import json
import tomllib
from pathlib import Path

import yaml
from app.core.config import Settings
from app.main import create_app
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]
METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}


def catalog(spec):
    result = {}
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            oid = operation["operationId"]
            if oid in result:
                raise ValueError(f"Duplicate operationId: {oid}")
            result[oid] = (method, path, operation)
    return result


def expand(node, spec, visited=()):
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/"):
                raise ValueError("Contract references must be local")
            if ref in visited:
                raise ValueError("Recursive schemas require an explicit comparison policy")
            target = spec
            for part in ref[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            return expand(
                {**target, **{k: v for k, v in node.items() if k != "$ref"}}, spec, (*visited, ref)
            )
        result = {}
        for key, value in node.items():
            if key == "properties":
                result[key] = {
                    name: expand(schema, spec, visited) for name, schema in value.items()
                }
            elif key not in {"title", "description", "examples", "example"}:
                result[key] = expand(value, spec, visited)
        if "const" in result:
            result["enum"] = [result.pop("const")]
        if "required" in result and isinstance(result["required"], list):
            result["required"] = sorted(result["required"])
        return result
    if isinstance(node, list):
        return [expand(value, spec, visited) for value in node]
    return node


def owner(operation_id):
    prefix = operation_id.split("_")[0]
    return {
        "auth": "identity",
        "health": "platform",
        "files": "infrastructure",
        "notifications": "infrastructure",
    }.get(prefix, prefix)


def parameters(spec, path, operation):
    merged = {}
    for item in [*spec["paths"][path].get("parameters", []), *operation.get("parameters", [])]:
        item = expand(item, spec)
        merged[(item["in"], item["name"].lower() if item["in"] == "header" else item["name"])] = {
            "required": item.get("required", False),
            "schema": item.get("schema"),
        }
    return merged


def validate_runtime(spec, runtime_spec, implemented):
    planned, actual = catalog(spec), catalog(runtime_spec)
    assert set(actual) == set(implemented), "Runtime/implementation registry drift"
    for oid, (method, path, operation) in actual.items():
        assert oid in planned, f"Undeclared operation: {oid}"
        expected_method, expected_path, expected = planned[oid]
        assert implemented[oid] == owner(oid), f"Wrong module owner: {oid}"
        assert (method, path) == (expected_method, "/api/v1" + expected_path), f"Route drift: {oid}"
        assert parameters(runtime_spec, path, operation) == parameters(
            spec, expected_path, expected
        ), f"Parameter drift: {oid}"
        assert expand(operation.get("requestBody"), runtime_spec) == expand(
            expected.get("requestBody"), spec
        ), f"Request body drift: {oid}"
        security = operation.get("security", runtime_spec.get("security", []))
        expected_security = expected.get("security", spec.get("security", []))
        assert security == expected_security, f"Security declaration drift: {oid}"
        codes = {str(code) for code in operation["responses"] if str(code).startswith("2")}
        expected_codes = {str(code) for code in expected["responses"] if str(code).startswith("2")}
        assert codes == expected_codes, f"Success status drift: {oid}"
        for code in codes:
            response = expand(operation["responses"][code], runtime_spec)
            desired = expand(expected["responses"][code], spec)
            assert response.get("content", {}) == desired.get("content", {}), (
                f"Response schema drift: {oid}/{code}"
            )
            assert response.get("headers", {}) == desired.get("headers", {}), (
                f"Response header drift: {oid}/{code}"
            )
        assert "default" in operation["responses"], f"Missing error fallback: {oid}"
        for code, response in operation["responses"].items():
            if str(code).startswith("2"):
                continue
            response = expand(response, runtime_spec)
            content = response.get("content", {})
            assert set(content) == {"application/problem+json"}, f"Error media drift: {oid}/{code}"
            schema = content["application/problem+json"]["schema"]
            desired = spec["components"]["schemas"]["Problem"]
            assert set(schema["required"]) >= set(desired["required"]), (
                f"Problem fields drift: {oid}/{code}"
            )
            for field in desired["required"]:
                assert (
                    schema["properties"][field]["type"] == desired["properties"][field]["type"]
                ), f"Problem field type drift: {oid}/{field}"


def check():
    spec = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text())
    validate(spec)
    operations = catalog(spec)
    modules = tomllib.loads((ROOT / "architecture.toml").read_text())["backend"]
    assert all(owner(oid) in {*modules, "platform", "infrastructure"} for oid in operations), (
        "Unowned operation"
    )
    implemented = json.loads((ROOT / "contracts/implemented.json").read_text())
    settings = Settings(database_url="postgresql+psycopg://unused@localhost/unused", _env_file=None)
    runtime = create_app(settings).openapi()
    validate(runtime)
    validate_runtime(spec, runtime, implemented)
    schemas = spec["components"]["schemas"]
    assert "preferences" in schemas["CaseProfile"]["required"]
    assert "preferences" not in schemas["ProfileWrite"]["properties"]
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    print(
        f"Contract: {len(spec['paths'])} paths / {len(operations)} operations / {len(schemas)} models; {len(implemented)} runtime operations verified"
    )


if __name__ == "__main__":
    check()
