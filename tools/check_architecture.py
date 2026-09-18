"""Check executable module boundaries; run from any working directory."""

import ast
import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/api/app"


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
                other not in rules[own]["depends_on"] or len(parts) < 4 or parts[3] != "public"
            ):
                errors.append(f"{module}: {target} must use a declared public dependency")
        if (
            own
            and target.startswith("app.")
            and any(p in target.split(".") for p in ("service", "router"))
            and module.endswith(".models")
        ):
            errors.append(f"{module}: models cannot import use cases or routers")
        if own and module.endswith(".router") and ".models" in target:
            errors.append(f"{module}: routes must call services, not models")
    return errors


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
    problems = check()
    if problems:
        raise SystemExit("\n".join(problems))
    print("Backend architecture boundaries: PASS")
