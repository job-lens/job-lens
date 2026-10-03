# User management: guarded first version

This extends the existing email registration, Argon2 credentials, opaque cookie sessions,
CSRF checks, roles, case grants, transaction boundaries and audit records. It does not add a
second authentication system. Source decision: #22, comment 5887467020; account/session work: #26.

## Product boundary and deployment decisions

Open registration creates a learner account only. An existing account may apply for counselor
certification; being registered or first to register never creates a counselor or administrator.
Administrator is a separate, explicitly provisioned capability, not a counselor account type.

Before deployment, the owner must name the initial administrator/reviewer and approve the
operational assignment policy. This implementation proposes manual administrator assignment,
with multiple explicitly assigned certified counselors supported by the existing grant model.
No institution, reviewer account, assignment, eligibility criterion, or production privilege is
selected by the code or migration. No automatic matching or reviewer selection is implemented.
The migration creates empty capability/certification/audit tables and never backfills grants.
Existing counselor roles remain usable; new manual assignment requires explicit certification.

## API workflow

All endpoints reuse the authenticated cookie session. Writes require matching Origin and
X-CSRF-Token. Every resource write requires a quoted If-Match resource version; stale versions
return 412, missing versions 428. Errors use the existing Problem response. API definitions and
client types are registered in the existing contract. No public homepage changes are needed.

1. GET /me/counselor-certification returns the caller's application and ETag (initial version 1).
2. PUT the same URL with statement and If-Match submits an application. Pending and approved
   applications cannot be edited. Rejected/revoked applications may be resubmitted.
3. GET /me/administration reports whether the caller has the explicit management capability.
4. GET /admin/counselor-certifications lists applications, filterable by state. PUT
   /admin/counselor-certifications/{user_id} accepts decision approved/rejected/revoked and reason.
   Only pending requests can be approved/rejected; only approved certifications can be revoked.
   Self-review is forbidden. Approval adds the existing counselor role. Revocation removes it,
   clears existing case grants, and bumps affected case versions. Review invalidates existing
   sessions; freshly approved counselors must sign in again.
5. GET /admin/users returns minimal account metadata, not login names, password digests or private
   profiles. PUT /admin/users/{user_id}/status accepts active and reason. Self-status changes and
   status changes to active administrators are forbidden. Changes invalidate all target sessions;
   suspension also revokes case grants. Reactivation never silently restores case access.
6. GET /admin/cases returns IDs, grants and versions only. PUT
   /admin/cases/{case_id}/counselors/{counselor_id} accepts assigned and reason. Assignment requires
   an active, approved counselor and a nonclosed case. Administrators cannot assign themselves,
   their own learner case, or a case's learner as its counselor. Unassignment is allowed even
   after a counselor becomes ineligible. No administrator bypass exists for case content.
7. GET /admin/audit returns append-only management events with actor, target, timestamp, action,
   reason and trace ID. Assignment case IDs are recorded in the existing case audit with the
   same trace ID. There is no HTTP update/delete audit endpoint. Keep infrastructure/database
   access separately restricted: the application audit is not a tamper-proof external ledger.

Admin lists accept limit (1–100) and offset (0–100000), sorted deterministically. Under concurrent
writes, offset pagination may shift; it is an operator queue, not a snapshot export. Statements
and reasons are bounded; avoid health information and credentials in them. Applications are
visible only to their owner or administrators. Administrative access does not expose case notes,
materials or health profiles.

## Controlled operator bootstrap

There is no startup hook or first-user grant. An authorized operator can inspect the command:

    PYTHONPATH=apps/api uv run python tools/manage_administrator.py --help

After the owner explicitly approves the named existing account, use its exact UUID and a
change-control reason. The command defaults to dry-run; --apply explicitly grants the capability.
--revoke removes it. Both operations invalidate sessions and append an operator audit event.
Use the existing protected database configuration. Do not put credentials in commands or logs.
Never run this merely because setup is incomplete. An operator revocation may remove the last
administrator intentionally; recovery is the same controlled operator process. No web endpoint
can grant or revoke administrator capability.

## Verification

Run make check and pytest with a disposable JOB_LENS_TEST_DATABASE_URL whose database name ends
in _test. Tests truncate that database. HTTP tests seed test-only actors and grants, cover
missing auth/role/CSRF/ETag, no-self-review, stale writes, session invalidation, private case
boundaries, pagination, certification transitions, and manual assignment constraints. Production
bootstrap or privilege changes are outside the tests and must never be used for verification.

### Verified on 2026-10-02

- Isolated PostgreSQL 17.11: full backend/architecture suite, 246 passed, zero skipped,
  including 32 new management HTTP/CLI regressions and migration/schema checks.
- Ruff, Mypy, backend/frontend boundaries, 68-operation contract, generated architecture
  and runtime OpenAPI snapshots: passed.
- Frontend typecheck, production build and 64 tests: passed. ESLint has zero errors and
  three existing Fast Refresh warnings in unchanged files. Generated client format passed.
- Independent static security review fixes include snapshot-consistent session roles,
  credential-generation checks after account locks, serialized admin lock ordering,
  baseline learner access after legacy counselor-only revocation, missing-target rejection,
  and atomic audit persistence. Existing auth/session regression tests passed.
- No production account, capability, configuration or credentials were changed. The operator
  command was exercised only with mocks (and --help); the database contains synthetic fixtures.
- Remote CI and human review remain required. No new admin UI or browser visual acceptance is
  claimed; this deliverable is the backend and typed API workflow.
