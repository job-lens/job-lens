"""One-time generation of the initial migration; refuses to overwrite history."""
from pathlib import Path

from app.bootstrap import metadata
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

root = Path(__file__).resolve().parents[1]
path = root / "apps/api/migrations/versions/0001_foundation.py"
if path.exists():
    raise SystemExit("Migration already exists; create a new Alembic revision instead")

statements = []
for table in metadata.sorted_tables:
    statements.append(str(CreateTable(table).compile(dialect=postgresql.dialect())).strip())
    for index in sorted(table.indexes, key=lambda item: item.name):
        statements.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())).strip())
statements.append("""CREATE FUNCTION jl_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'immutable history: %', TG_TABLE_NAME USING ERRCODE = '23514';
END $$""")
for table in ("submissions", "feedback", "support_messages", "audit_events"):
    statements.append(f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION jl_append_only()")
statements.append("""CREATE FUNCTION jl_frozen_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state IN ('published','confirmed') THEN
    RAISE EXCEPTION 'immutable published resource: %', TG_TABLE_NAME USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$""")
for table in ("sop_revisions", "annotations", "support_matches"):
    statements.append(f"CREATE TRIGGER frozen_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION jl_frozen_state()")
statements.append("""CREATE FUNCTION jl_step_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_state text; new_state text;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    SELECT state INTO old_state FROM sop_revisions WHERE id = OLD.revision_id FOR UPDATE;
    IF old_state = 'published' THEN RAISE EXCEPTION 'published step is immutable' USING ERRCODE = '23514'; END IF;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    SELECT state INTO new_state FROM sop_revisions WHERE id = NEW.revision_id FOR UPDATE;
    IF new_state = 'published' THEN RAISE EXCEPTION 'cannot add or move a step into a published revision' USING ERRCODE = '23514'; END IF;
    RETURN NEW;
  END IF;
  RETURN OLD;
END $$""")
statements.append("CREATE TRIGGER frozen_sop_steps BEFORE INSERT OR UPDATE OR DELETE ON sop_steps FOR EACH ROW EXECUTE FUNCTION jl_step_guard()")
source = '''"""Initial relational foundation with immutable training history."""
from alembic import op
revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

DDL = (
'''
source += "".join("    " + repr(statement) + ",\n" for statement in statements)
source += ")\n\ndef upgrade() -> None:\n    for statement in DDL:\n        op.execute(statement)\n\ndef downgrade() -> None:\n"
for table in reversed(metadata.sorted_tables):
    source += f'    op.execute("DROP TABLE {table.name}")\n'
for function in ("jl_step_guard", "jl_frozen_state", "jl_append_only"):
    source += f'    op.execute("DROP FUNCTION {function}()")\n'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(source, encoding="utf-8")
print(f"Frozen {len(metadata.tables)} tables and {len(statements)} DDL statements")
