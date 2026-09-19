import pytest

from tools.check_architecture import check, unused_declarations, used_dependencies, violations
from tools.generate_architecture import ROOT, artifacts

RULES = {"sop": {"depends_on": ["cases"]}}


def test_repository_boundaries():
    assert check() == []


@pytest.mark.parametrize(
    "module,source",
    [
        ("app.core.fake", "from app.infrastructure.db import Base"),
        ("app.infrastructure.fake", "import app.modules.cases.public"),
        ("app.modules.sop.service", "from app.modules.cases.models import Case"),
        ("app.modules.sop.service", "from ..cases.models import Case"),
        ("app.modules.sop.models", "from .service import publish"),
        ("app.modules.sop.router", "from .models import SopPlan"),
        ("app.modules.sop.service", "from app import bootstrap"),
        ("app.infrastructure.fake", "import app.main"),
        ("app.modules.sop.service", "from app.web.deps import actor"),
        ("app.core.fake", "from app.web import deps"),
        ("app.modules.sop.public", "from app.modules.sop.models import SopPlan"),
        ("app.modules.sop.public", "from .models import SopPlan"),
        ("app.modules.sop.rules", "from sqlalchemy import select"),
        ("app.modules.sop.rules", "from sqlalchemy.orm import Session"),
        ("app.web.sop", "from app.modules.sop.models import SopPlan"),
        ("app.modules.sop.service", "from app.modules.cases.service import read_access"),
        ("app.modules.sop.queries", "from app.modules.sop.service import publish"),
    ],
)
def test_forbidden_dependency_is_rejected(module, source):
    assert violations(module, source, RULES)


@pytest.mark.parametrize(
    "module,source",
    [
        # public may expose read-only queries, so the session type itself is allowed.
        ("app.modules.sop.public", "from sqlalchemy.orm import Session"),
        ("app.modules.sop.public", "from app.core.types import Actor"),
        ("app.modules.sop.rules", "from app.core.errors import conflict"),
        ("app.modules.sop.rules", "from app.modules.cases.public import CaseAccess"),
        # The assembly layer is allowed to reach services and public boundaries.
        ("app.web.sop", "from app.modules.sop.service import publish"),
        ("app.web.sop", "from app.modules.cases.public import CaseAccess"),
        # queries.py is the second declared cross-module surface, next to public.py.
        ("app.modules.sop.service", "from app.modules.cases.queries import load_access"),
        ("app.modules.sop.service", "from app.modules.cases import queries"),
        ("app.modules.sop.queries", "from app.modules.sop.models import SopPlan"),
    ],
)
def test_allowed_dependency_is_accepted(module, source):
    assert not violations(module, source, RULES)


def test_public_dependency_is_allowed():
    assert not violations(
        "app.modules.sop.service", "from app.modules.cases.public import CaseAccess", RULES
    )


def test_dynamic_import_is_rejected():
    with pytest.raises(ValueError):
        violations("app.modules.sop.service", "__import__('app.modules.cases.models')", RULES)


def test_generated_artifacts_match_code():
    for path, content in artifacts().items():
        assert (ROOT / path).read_text() == content, path


def test_database_constraint_names_are_unique():
    from app.bootstrap import metadata

    for table in metadata.tables.values():
        names = [constraint.name for constraint in table.constraints if constraint.name]
        assert len(names) == len(set(names)), table.name


def test_package_public_import_is_allowed():
    assert not violations("app.modules.sop.service", "from app.modules.cases import public", RULES)


def test_declared_dependency_without_an_import_is_reported():
    assert unused_declarations({"sop": {"depends_on": ["cases"]}}, {})
    assert unused_declarations({"sop": {"depends_on": ["cases"]}}, {"sop": {"training"}})


def test_declared_dependency_that_is_imported_is_not_reported():
    assert not unused_declarations({"sop": {"depends_on": ["cases"]}}, {"sop": {"cases"}})
    assert not unused_declarations({"sop": {"depends_on": []}}, {})


def test_used_dependencies_reads_the_real_tree():
    used = used_dependencies()
    assert used.get("training") == {"cases"}, used
