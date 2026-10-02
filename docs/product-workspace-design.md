# Product workspace: route and interaction design

## Scope and ownership

This increment builds a complete authenticated workspace on commit `5c0f0b1d94a341a8faebe24b7d37ba8863226e73`. It preserves the approved public homepage and companion, the existing account service, and all real training, feedback, support, and file APIs. The workspace uses the existing local Everplain-derived semantic tokens and controls; it does not import another product's domain or runtime.

The application layer owns the floating sidebar, current location, responsive drawer and account entry. Feature modules own their page actions, queries, forms, and error states. No feature may import another feature's internals. Navigation must not grant roles or disclose objects outside existing authorization.

## Route inventory

| Area | Routes | Existing capability | Work in this increment |
| --- | --- | --- | --- |
| Public | `/` | Approved gray/white homepage and companion | Preserve unchanged |
| Account | `/login`, `/register`, `/forgot-password`, `/reset-password` | Real Cookie/CSRF login, learner registration, one-use reset | Preserve; expose clear account controls |
| Workspace | all authenticated routes | Top text navigation | Floating left sidebar, role-specific destinations, collapsed desktop rail, accessible mobile drawer, current location and account identity |
| Learner | `/learner`, `/learner/tasks/:id`, `/learner/records` | Real tasks, step progress, submission, feedback and rework | Keep workflows; turn action links into explicit controls |
| Counselor | `/counselor`, `?tab=cases`, `/counselor/cases/:id` | Dashboard, scoped cases, profile, match | Overview cards, clear next actions, query-backed filters, cursor pagination and refresh |
| SOP and review | `/counselor/sop/:id`, `/counselor/tasks/:id`, `/counselor/submissions/:id` | Draft/save/publish, review/rework | Keep functionality, consistent action styling |
| Support | learner case support and counselor support/detail | Text messages, requests, acceptance and resolution | Keep real routes and visible action controls |
| Notifications | `/notifications`, `/counselor/notifications` | Persistent notification reads and read state | One discoverable sidebar destination |
| Settings | `/profile`, `/preferences`, new `/settings` | Versioned server profile and preferences | One settings hub with profile, reading/prompts and account-security sections; retain old deep links |
| Administration | none | No admin role, no approvals or assignment API | Separate required increment after #22 Q02 decision; do not present case access as global user management |
| Service | `/status` | Actual API/database readiness | Retain separate engineering route |

## Interaction rules

- Navigation remains a link with a clear selected background; actions use real buttons, not clickable prose.
- Desktop: a floating rounded sidebar, one main content area, and a stable page toolbar. Mobile: the same navigation in a modal drawer with Escape, focus containment, focus return, background inertness and close-on-navigation.
- One dominant action per task. Use subdued panels, clear grouping, stable spacing and at least 44px touch controls. No flashing, unexpected sound, medical promises, or childlike rewards.
- Role navigation comes only from the existing confirmed session. Learners never see counselor management destinations.
- Lists distinguish initial load, empty/filter-empty, page error, background-refresh error and retry. Counts describe the actual server total or explicitly the loaded subset.
- Unsaved settings stay mounted when switching sections. Browser history restores the selected section. Server saves preserve ETag/conflict handling.

## Required verification

Typecheck, lint, boundaries, formatting, all frontend tests and production build. New component tests cover role navigation, drawer dismissal/focus, location state, settings tabs and pagination errors. Browser inspection covers wide and mobile layouts, reduced motion, full-size text, navigation and current real APIs where a disposable database is available. Mock-driven UI checks must be labelled as such and cannot count as a real account/training end-to-end pass.

## Remaining release gates

User management and counselor approval rules (#22 Q02), independent email delivery, real ClamAV acceptance, upload/annotation UI and complete production preflight remain distinct acceptance items. This increment is for review; it does not authorize a deployment or a production role grant.
