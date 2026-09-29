"""Tighten version identity and align persisted fields with the API projections."""
from alembic import op

revision = "0002_integrity"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sop_revisions DROP CONSTRAINT ck_sop_revisions_state, DROP CONSTRAINT ck_sop_revisions_publication")
    op.execute("ALTER TABLE sop_revisions ADD CONSTRAINT ck_sop_revisions_state CHECK (state IN ('draft','published','archived')), ADD CONSTRAINT ck_sop_revisions_publication CHECK ((state <> 'draft') = (published_at IS NOT NULL))")
    op.execute("ALTER TABLE sop_steps DROP CONSTRAINT ck_sop_steps_duration, ADD CONSTRAINT ck_sop_steps_duration CHECK (estimated_seconds IS NULL OR estimated_seconds BETWEEN 0 AND 86400)")
    op.execute("ALTER TABLE training_tasks ADD COLUMN prompt_reason VARCHAR(500)")
    # Existing non-null overrides have no reason. Refuse the upgrade rather than invent one.
    op.execute("ALTER TABLE training_tasks DROP CONSTRAINT ck_training_tasks_prompt, ADD CONSTRAINT ck_training_tasks_prompt CHECK ((prompt_override IS NULL AND prompt_reason IS NULL) OR (prompt_override IS NOT NULL AND prompt_override BETWEEN 1 AND 3 AND prompt_reason IS NOT NULL AND length(trim(prompt_reason)) BETWEEN 1 AND 500))")
    op.execute("ALTER TABLE task_events ADD COLUMN observed_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE task_events DROP CONSTRAINT ck_task_events_values, ADD CONSTRAINT ck_task_events_values CHECK (sequence >= 1 AND (value IS NULL OR value BETWEEN 0 AND 86400000))")
    op.execute("ALTER TABLE submissions ADD COLUMN note VARCHAR(500) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE submissions ALTER COLUMN note DROP DEFAULT")
    op.execute("""
CREATE OR REPLACE FUNCTION jl_frozen_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state IN ('published','archived','confirmed') THEN
    RAISE EXCEPTION 'immutable published resource: %', TG_TABLE_NAME USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$
""")
    op.execute("""
CREATE OR REPLACE FUNCTION jl_step_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_state text; new_state text;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    SELECT state INTO old_state FROM sop_revisions WHERE id = OLD.revision_id FOR UPDATE;
    IF old_state <> 'draft' THEN RAISE EXCEPTION 'published step is immutable' USING ERRCODE = '23514'; END IF;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    SELECT state INTO new_state FROM sop_revisions WHERE id = NEW.revision_id FOR UPDATE;
    IF new_state <> 'draft' THEN RAISE EXCEPTION 'cannot add or move a frozen step' USING ERRCODE = '23514'; END IF;
    RETURN NEW;
  END IF;
  RETURN OLD;
END $$
""")
    op.execute("""
CREATE FUNCTION jl_task_identity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision_state text;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF ROW(NEW.id, NEW.created_at, NEW.case_id, NEW.revision_id)
      IS DISTINCT FROM ROW(OLD.id, OLD.created_at, OLD.case_id, OLD.revision_id) THEN
      RAISE EXCEPTION 'task identity is immutable' USING ERRCODE = '23514';
    END IF;
  ELSE
    SELECT state INTO revision_state FROM sop_revisions WHERE id=NEW.revision_id FOR SHARE;
    IF revision_state IS DISTINCT FROM 'published' THEN
      RAISE EXCEPTION 'task requires a published revision' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END $$
""")
    op.execute("CREATE TRIGGER task_identity BEFORE INSERT OR UPDATE ON training_tasks FOR EACH ROW EXECUTE FUNCTION jl_task_identity()")
    op.execute("CREATE TRIGGER immutable_task_events BEFORE UPDATE OR DELETE ON task_events FOR EACH ROW EXECUTE FUNCTION jl_append_only()")


def downgrade() -> None:
    # This downgrade intentionally fails when newer values cannot fit the previous schema.
    op.execute("DROP TRIGGER immutable_task_events ON task_events")
    op.execute("DROP TRIGGER task_identity ON training_tasks")
    op.execute("DROP FUNCTION jl_task_identity()")
    op.execute("ALTER TABLE submissions DROP COLUMN note")
    op.execute("ALTER TABLE task_events DROP COLUMN observed_at")
    op.execute("ALTER TABLE task_events DROP CONSTRAINT ck_task_events_values, ADD CONSTRAINT ck_task_events_values CHECK (sequence >= 0 AND (value IS NULL OR value >= 0))")
    op.execute("ALTER TABLE training_tasks DROP CONSTRAINT ck_training_tasks_prompt, DROP COLUMN prompt_reason, ADD CONSTRAINT ck_training_tasks_prompt CHECK (prompt_override IS NULL OR prompt_override BETWEEN 0 AND 3)")
    op.execute("ALTER TABLE sop_steps DROP CONSTRAINT ck_sop_steps_duration, ADD CONSTRAINT ck_sop_steps_duration CHECK (estimated_seconds IS NULL OR estimated_seconds >= 1)")
    op.execute("ALTER TABLE sop_revisions DROP CONSTRAINT ck_sop_revisions_state, DROP CONSTRAINT ck_sop_revisions_publication")
    op.execute("ALTER TABLE sop_revisions ADD CONSTRAINT ck_sop_revisions_state CHECK (state IN ('draft','published')), ADD CONSTRAINT ck_sop_revisions_publication CHECK ((state = 'published') = (published_at IS NOT NULL))")
    op.execute("""
CREATE OR REPLACE FUNCTION jl_frozen_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state IN ('published','confirmed') THEN
    RAISE EXCEPTION 'immutable published resource: %', TG_TABLE_NAME USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$
""")
    op.execute("""
CREATE OR REPLACE FUNCTION jl_step_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
END $$
""")
