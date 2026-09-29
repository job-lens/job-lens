"""Check executable module boundaries; run from any working directory."""

import argparse
import ast
import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/api/app"
# The two files another module may import: values and the read-only lookups returning them.
SURFACES = ("public", "queries")


def imports(source: str, module: str) -> set[str]:
    found = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = importlib.util.resolve_name(
                    "." * node.level + base, module.rpartition(".")[0]
                )
            # `from app.modules.cases import public` imports a module, not package internals.
            if (
                base == "app"
                or base == "app.modules"
                or (base.startswith("app.modules.") and len(base.split(".")) == 3)
            ):
                found.update(f"{base}.{alias.name}" for alias in node.names)
            else:
                found.add(base)
        elif isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name in {"__import__", "importlib.import_module", "import_module"}:
                raise ValueError(
                    f"{module}: dynamic imports are outside the module boundary contract"
                )
    return found


def violations(module: str, source: str, rules: dict) -> list[str]:
    errors = []
    dependencies = imports(source, module)
    own = module.split(".")[2] if module.startswith("app.modules.") else None
    for target in sorted(dependencies):
        if (own or module.startswith(("app.core.", "app.infrastructure."))) and target.split(".")[
            :2
        ] in [
            ["app", "main"],
            ["app", "bootstrap"],
            ["app", "worker"],
            # app.web assembles modules into HTTP; depending on it would invert the layering.
            ["app", "web"],
        ]:
            errors.append(f"{module}: cannot import composition root {target}")
        if module.startswith("app.core.") and target.startswith(
            ("app.modules", "app.infrastructure")
        ):
            errors.append(f"{module}: core cannot import {target}")
        if module.startswith("app.infrastructure.") and target.startswith("app.modules"):
            errors.append(f"{module}: infrastructure cannot import {target}")
        if own and target.startswith("app.modules."):
            parts = target.split(".")
            if len(parts) < 3:
                continue
            other = parts[2]
            if other != own and (
                other not in rules[own]["depends_on"] or len(parts) < 4 or parts[3] not in SURFACES
            ):
                errors.append(f"{module}: {target} must use a declared public surface")
        if (
            own
            and target.startswith("app.")
            and any(p in target.split(".") for p in ("service", "router"))
            and module.endswith(".models")
        ):
            errors.append(f"{module}: models cannot import use cases or routers")
        if (own and module.endswith(".router") or module.startswith("app.web.")) and (
            ".models" in target
        ):
            errors.append(f"{module}: routes must call services, not models")
        # public.py is the only surface other modules may touch. Values and read-only queries
        # cross it; ORM instances do not, or the owning module loses control of its writes.
        if own and module.endswith(".public") and target.startswith(f"app.modules.{own}.models"):
            errors.append(f"{module}: public boundaries cannot expose ORM models")
        # rules.py holds decisions that must stay testable without a database.
        if own and module.endswith(".rules") and target.split(".")[0] == "sqlalchemy":
            errors.append(f"{module}: rules cannot depend on persistence")
        # A read surface that can reach service could trigger writes behind a caller's back.
        if own and module.endswith(".queries") and target.startswith(f"app.modules.{own}.service"):
            errors.append(f"{module}: queries cannot import use cases")
    return errors


def used_dependencies() -> dict[str, set[str]]:
    """Which other modules each module actually imports, whatever the manifest claims."""
    found: dict[str, set[str]] = {}
    for path in (APP / "modules").rglob("*.py"):
        module = ".".join(path.relative_to(APP.parent).with_suffix("").parts)
        own = module.split(".")[2]
        for target in imports(path.read_text(), module):
            parts = target.split(".")
            if len(parts) > 2 and parts[:2] == ["app", "modules"] and parts[2] != own:
                found.setdefault(own, set()).add(parts[2])
    return found


def unused_declarations(rules: dict, used: dict[str, set[str]]) -> list[str]:
    """A declaration nobody imports is intent, not fact; say so before the two drift apart."""
    return [
        f"{name}: declares {dep} but never imports it"
        for name in sorted(rules)
        for dep in sorted(set(rules[name]["depends_on"]) - used.get(name, set()))
    ]


def check() -> list[str]:
    manifest = tomllib.loads((ROOT / "architecture.toml").read_text())
    rules = manifest["backend"]
    errors = []
    for directory in (APP / "modules").iterdir():
        if directory.is_dir() and not directory.name.startswith("_"):
            if directory.name not in rules:
                errors.append(f"unregistered module: {directory.name}")
    for path in APP.rglob("*.py"):
        module = ".".join(path.relative_to(APP.parent).with_suffix("").parts)
        errors += violations(module, path.read_text(), rules)
    visiting, visited = set(), set()

    def visit(name):
        if name in visiting:
            raise ValueError(f"cyclic module dependency at {name}")
        if name in visited:
            return
        visiting.add(name)
        for dep in rules[name]["depends_on"]:
            visit(dep)
        visiting.remove(name)
        visited.add(name)

    for name in rules:
        visit(name)
        if not (APP / "modules" / name / "public.py").exists():
            errors.append(f"missing public boundary: {name}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict", action="store_true", help="fail on declared dependencies nothing imports"
    )
    args = parser.parse_args()
    problems = check()
    manifest = tomllib.loads((ROOT / "architecture.toml").read_text())
    unused = unused_declarations(manifest["backend"], used_dependencies())
    if args.strict:
        problems += unused
    else:
        for line in unused:
            print(f"WARNING {line}")
    if problems:
        raise SystemExit("\n".join(problems))
    print("Backend architecture boundaries: PASS")
