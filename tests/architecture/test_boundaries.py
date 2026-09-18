import pytest

from tools.check_architecture import check, violations
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
    ],
)
def test_forbidden_dependency_is_rejected(module, source):
    assert violations(module, source, RULES)


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
