# Product workspace verification

Baseline: `5c0f0b1d94a341a8faebe24b7d37ba8863226e73` (PR #48).

This change belongs to the shared frontend/workspace work in #32, profile/preferences entry in #34, counselor integration in #37 and workflow regression in #38. The detailed route map and design boundaries are in `product-workspace-design.md`. It is a review increment, not a production deployment or a claim that every release gate is complete.

## Implemented

- Floating, collapsible authenticated sidebar; session-role navigation; current location; account/profile, settings, notifications and real sign-out controls.
- Mobile drawer with background inertness, focus containment, Escape and close-on-navigation; the desktop collapsed state survives navigation. Switching to desktop clears any open mobile drawer, so returning to mobile does not reopen it unexpectedly.
- Shell identity comes from the confirmed session and updates after a profile save. Navigation does not add a second profile request or fail because an unrelated profile request is unavailable.
- Counselor overview uses actual pending training, feedback and assistance counts. It no longer labels all-time backlog as today's completed work.
- Counselor cases use the actual cursor API. Refresh and next-page errors retain existing data; search and status filters are URL-backed and explicitly describe their loaded-data scope.
- One settings entry for profile, reading/prompts and account/security. Existing versioned saves and conflicts are preserved; switching settings sections retains unsaved form values. Old `/profile` and `/preferences` deep links still work.
- Learner action links and account links use shared button styling. The approved homepage and companion source are unchanged.
- Fixed an obsolete HTTP test which still expected an unimplemented `/tasks` route. The implemented route now correctly requires authentication (401).
- The real workflow browser test waits for the task UUID URL before capturing the task ID. The original CI failure is confirmed by the downloaded [Actions trace](https://github.com/job-lens/job-lens/actions/runs/37059221778/artifacts/11248974322): it navigated to `/counselor/tasks/learner` and called `/api/v1/tasks/learner` (422), because it captured `/learner` before React Router navigation completed. The fix retains the complete real review/rework assertions.

## Local results

Executed on the independent cloud checkout with the locked dependency graph and Node 24:

- TypeScript project check: passed.
- Frontend lint: no errors; three Fast Refresh export warnings (two pre-existing preferences warnings, one session-hook export warning).
- Frontend module boundary and negative-fixture checker: passed.
- Frontend Vitest: 21 files, 64 tests passed. Final run used one worker. New coverage includes role navigation, selected URL state, collapse persistence, drawer focus/Escape/repeated open and close/desktop resize, session-identity isolation, settings-history input retention, next-page loading and error recovery.
- Frontend formatting and `git diff --check`: passed.
- Production Vite build: passed. This is a build result, not browser or API acceptance.
- Python suite: 155 passed, 59 PostgreSQL-dependent tests skipped because this checkout has no disposable PostgreSQL service.
- Ruff: passed. Mypy: passed across 68 source files.
- Backend architecture, runtime/product contract agreement (58 operations), architecture generation and runtime OpenAPI snapshots: passed.

The local environment's pnpm wrapper was newer than the repository pin and attempted to alter its workspace build policy. That incidental change was removed; no package or lockfile change belongs to this increment. Validation invoked the installed project tools directly.

## Browser verification boundary

Cloud Chromium could not start because process sockets were denied (EPERM), including the reviewed escalation attempt. The provided cloud-browser tool refused the local preview URL with ERR_BLOCKED_BY_CLIENT. No browser safeguards were bypassed. Consequently, no screenshot or real-browser visual acceptance is claimed here.

The local Vite preview can be run through the repository's normal workflow. The user's computer is needed only for delivery and the remaining real-browser verification; implementation and design were completed independently in the cloud checkout.

## Remaining acceptance checklist

- Verify 1440px desktop, 390px mobile, dark appearance, reduced motion and 1.5x saved text scale using a real browser.
- Verify mobile menu button → drawer → Tab cycle → Escape → focus return; then navigate and reopen. Check browser Back/Forward and sidebar collapse across routes.
- Verify settings profile edits survive switching to reading/prompts, security, and back; save through the real API; verify conflict/error input retention.
- On an isolated test database, run the existing real login, session, training review/rework, support, and full container checks. Do not reset the existing preview database or use it as a disposable integration-test database.
- Run exact-head CI and review the result before merging. No auto-merge or deployment is included.

## Separate product gates

There is still no administrator role or user-management/approval API. #22 Q02 must confirm who grants the first administrator, who approves counselors and how case assignment is governed. No production permission was added. Independent email delivery, real ClamAV acceptance, materials/learner-annotation/support-attachment UI and other list pagination remain separate unfinished scopes.
