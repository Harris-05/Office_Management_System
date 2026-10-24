# Project decisions

Last updated: 23 October 2026.

This file records agreed project decisions. Approval of a design does not mean its implementation is complete. The assignment brief remains in Task.md; current progress is tracked in Context.md.

## 1. Git branch policy

**User instruction:** Keep work on `feature/basic-login`. Do not create additional branches until the user explicitly asks.

- Switched back to `feature/basic-login`.
- Fast-forwarded it to include the existing database commit `836444f` so completed work is preserved without rewriting history.
- The previously created `feature/database-foundation` branch still exists; it has not been deleted.
- Do not create a worktree on a new branch as a workaround for this instruction. Remain in the current checkout unless the user requests otherwise.
- The earlier feature -> dev -> main PR workflow remains the integration approach, subject to this explicit restriction on creating branches.

## 2. Application stack

- Backend: Python and FastAPI.
- Frontend: React, TypeScript and Vite.
- Database: PostgreSQL, accessed through SQLAlchemy 2.
- Schema changes: Alembic migrations, applied explicitly rather than creating tables at application startup.
- Local database: Docker Compose with persistent storage.
- CI: GitHub Actions, including backend tests/coverage, migration checks and frontend builds.
- Required deployment target: Render; deployment is not implemented yet.
- Current frontend styling uses plain CSS. Tailwind was proposed earlier but has not been adopted.

## 3. Database engineering

Implemented foundation:

- User accounts live in PostgreSQL rather than an in-memory dictionary.
- Database constraints enforce normalized unique emails and valid system roles.
- Keep configuration, session lifecycle, models, HTTP handlers and account logic separated.
- Use request-scoped database sessions and explicit transactions for writes.
- Demo seeding is explicit and idempotent; preserve existing users, names, roles and passwords on reruns.
- Integration tests use a separate PostgreSQL database and roll back test transactions. Do not fall back to the application database or SQLite.
- Future branch, member and finance tables will be added with reviewed migrations when their workflows are designed.

## 4. Authentication approach

**Approved:** Server-side session cookies rather than JWT access/refresh tokens for this first-party browser application.

Approved design: [API security and session-cookie design](docs/superpowers/specs/2026-10-22-api-security-design.md).

Implementation is pending:

- Store sessions in PostgreSQL; send only an opaque random session token in an HttpOnly cookie.
- Store a digest of the bearer session token, not the raw token, in the database.
- Production cookies use Secure, SameSite=Lax, Path=/, no Domain and a __Host- name. Explicit localhost development configuration uses a different cookie name without Secure.
- Authenticated sessions expire after 30 minutes idle or 8 hours total. Anonymous pre-login sessions expire after 15 minutes.
- Rotate the session and CSRF token on successful login; revoke the server-side session on logout.
- Restore the authenticated user after page refresh through `/api/me`; do not store session tokens in browser localStorage/sessionStorage.
- Check the current user's active status and role on authenticated requests.
- Make session rotation, revocation and activity updates safe under concurrent requests.

## 5. Password hashing

**User choice:** bcrypt for new password hashes. Password hashing is one-way; this is not reversible encryption.

Implementation is pending:

- Start with bcrypt cost 12, configurable with a minimum of 10 and performance verification.
- Enforce the 72-byte UTF-8 limit for bcrypt without silent truncation.
- Keep verification of existing Argon2 hashes during migration. Rehash to bcrypt after successful eligible logins; never reset existing passwords to migrate them.
- Existing Argon2 passwords exceeding bcrypt's byte limit retain Argon2 verification until a password-change/reset flow exists.
- Conditional hash updates must not overwrite concurrent password changes.
- Do not reveal passwords/hashes in responses, logs or validation errors. Unknown/inactive accounts receive generic credential failures with hashing work on those paths.

The current implementation still uses Argon2. The approved bcrypt change has not been applied yet.

## 6. Rate limiting

**Approved:** Redis-backed shared, atomic limits rather than independent in-memory counters per worker.

Approved initial configurable defaults, pending implementation:

| Scope | Limit |
| --- | --- |
| General `/api` requests | 120 per minute per trusted client IP |
| Login | 10 attempts per minute per trusted client IP |
| Login account/IP pair | 5 attempts per minute |
| CSRF bootstrap | 20 requests per minute per trusted client IP |

- Return HTTP 429 with Retry-After when a limit is exceeded.
- A Redis outage returns a generic 503 for gated API requests; do not silently disable protection.
- Normalize account keys consistently and avoid raw emails in Redis keys.
- Do not trust arbitrary forwarded-IP headers; proxy trust must be configured explicitly for the deployment.
- Keep process liveness independent of Redis/database availability; readiness checks report dependency failures.

## 7. API and browser protection

Approved, pending implementation:

- Require authentication centrally by default for `/api`, with an explicit public method/path allowlist for login and CSRF bootstrap.
- Require CSRF tokens and exact allowed-origin checks on unsafe browser requests, including login/logout.
- Add reusable backend role guards; frontend visibility alone is not authorization.
- Define branch permissions separately before implementing branch-scoped operations. A stored role alone does not prove access rights.
- Use explicit allowed hosts/origins; no wildcard credentialed CORS or default production secrets.
- Enforce request-size limits on actual streamed bytes and sanitize errors/input validation output.
- Add appropriate security/no-store headers, production HTTPS controls and safe security-event logging.
- Disable public interactive API docs by default in production.
- Exclude demo credential shortcuts/constants from production frontend artifacts and refuse demo seeding in production mode.

## 8. Verification and implementation workflow

- Use the requested agent skills for design, implementation planning, test-first development, review and verification.
- The user approved the security design on 22 October 2026. Do not ask for approval of that same design again unless scope changes materially.
- Prepare the implementation plan next and respect the user's branch instruction throughout.
- Extend Compose and CI with Redis and real integration tests. Retain the minimum 60% backend coverage gate.
- Verify password migration, session/CSRF behavior, role denial, distributed rate limits, expiry/revocation races, dependency failures, input redaction, migrations and frontend login/logout restoration.
- Do not describe approved or planned protections as implemented until code and verification support that claim.

## Remaining decisions

### Staff provisioning update

The user selected Super Admin-created staff accounts with directly shared credentials. Do not add email delivery, emailed invitations or public staff signup. The email is an account identifier, not a mailbox created by this application. The administrator assigns the role; staff cannot self-select access.

See [staff account creation design](docs/superpowers/specs/2026-10-22-staff-account-creation-design.md). The user approved temporary passwords, mandatory first-login password change, 48-hour expiry and administrator resets on 22 October 2026. Both this flow and the previously approved security foundation remain pending implementation. The implementation plan is at docs/superpowers/plans/2026-10-22-secure-staff-accounts.md.

The detailed organisation permission table, branch membership model, financial reporting rules, official sample data and deployment-specific hosts/origins/proxy settings are still outstanding. Approval of this authentication design does not settle them.

## Implementation update (23 October 2026)

The previously approved security and staff provisioning design has now been implemented on `feature/basic-login`. This supersedes the earlier “pending implementation” status above; it does not mark the full assignment complete.

- PostgreSQL-backed server-side sessions, HttpOnly cookies, CSRF/origin checks, bcrypt hashing with eligible legacy Argon2 migration, Redis rate limits, production configuration checks and default API guards are implemented.
- Super Admin staff creation/listing/password resets, 48-hour temporary credentials, required first-login password changes, first-admin bootstrap and expired-session cleanup are implemented. No email delivery, public staff signup or account mailbox creation was added.
- The React portal supports session restoration, sign-in/out, password changes and staff account management. Existing demo accounts remain intact; credentials are not embedded in the frontend.
- Root `SECURITY.md` documents operations, API behavior, production settings and known limitations. `AI-USAGE.md` documents the assistance used.
- Full business permissions, branch authorization, remaining workflows, deployment and remote CI verification remain outstanding. Work stays uncommitted on the user-requested branch; do not create a new branch or commit/push without the user's instruction.

## Public Home (23 October 2026)

- User approved keeping the green-and-cream identity and Branch Office working name, then approved the short public-home design with “Approve and build”.
- `/` is now public Home, independent of authentication API availability. `/staff` opens the existing staff login/workspace. No public staff signup was added.
- Home supports English/Urdu, RTL, responsive section navigation, mobile keyboard controls and a participation chooser. Language preference is the only new browser-storage value; no credentials are stored there.
- The six other required public pages use Home section destinations until implemented separately. The volunteer application, CMS and actual published branch/event/contact records are still pending. Do not invent organisation data or claim this slice completes all seven pages.
- Keep public components/content/styles separate from staff authentication. No routing dependency was added for these two document routes. Deployment must support the `/staff` document route.
- Locally hosted CC0 photographs are illustrative, with source/license metadata and readable footer credits. They do not depict claimed Branch Office activities.
- Verification passed 20 frontend tests, production build and English/Urdu browser checks. Independent review found no required issues; Lighthouse remains unmeasured. Stay on `feature/basic-login` and retain user-controlled commits.

## Public palette and hierarchy update (23 October 2026)

- The user selected the burgundy preview and explicitly requested light grey, white, black text, proper spacing, animations and varied text sizes. This replaces the earlier green/cream choice for the public website.
- Use semantic public CSS tokens: burgundy #7D0C14, hover #5C0910, white #FFFFFF, light grey #F2F2F2, near-black body #202020 and secondary text #4B4B4B. Burgundy fields/buttons use white labels. Keep staff styling separate.
- Use a shared responsive typography and spacing scale rather than unrelated values per section. Hero, section titles, subheadings, body and notes have distinct roles; preserve English/Urdu readability.
- Motion should clarify transitions: finite entrances and photo settling, program-image changes, hover/press feedback and menu-link entrances. Menu backgrounds remain opaque; content stays visible without the observer; reduced-motion preferences disable effects.
- Existing frontend tests/build and real browser checks passed after the refinement. No Lighthouse score is claimed. Keep feature/basic-login and user-controlled integration.

## Darker hero and scroll interaction (23 October 2026)

- The user requested darker burgundy, a changed hero colour scheme and on-scroll animation. The current public brand is #500F1C (hover #3D0A14), with a #300910 hero, white headline and #F4E7EA primary action. This supersedes the preceding public burgundy values. Light-grey/white sections retain near-black text.
- Use viewport-triggered, finite staggered reveals, an outlined reading-progress track and hero-image movement capped at 24px on desktop. Passive scroll events share one animation frame; avoid scroll hijacking and new animation dependencies.
- Keep content visible without IntersectionObserver, on cleanup and under reduced motion. Respect focus visibility, localized content replacement and RTL progress direction. Staff styling remains separate.
- Verification passed 26 frontend tests, TypeScript/Vite build and English/Urdu browser checks at 1440/768/390px. A fresh reviewer identified the progress indicator blending into burgundy sections; a light track and white edges resolve that finding. Branch remains feature/basic-login; commits and integration remain user controlled.

## Remove unrelated community photographs (23 October 2026)

- The user clarified that these are office branches and requested removal of the photos. Remove all four community photos from the public website, including hero/About/Programs/Branches placements, downloadable assets, captions and obsolete credits. Do not substitute unrelated office stock photos or imply authentic branch imagery exists.
- Use a text-led hero, full-width About/Branches content and a text detail panel for participation choices. Retain the dark burgundy palette, bilingual content, viewport reveals, reading progress and reduced-motion support. Remove photo-specific parallax and styling.
- Verified 26 passing frontend tests, production build and six English/Urdu browser layouts. Home renders/requests no photos; production output includes no image assets. Existing interactions, reduced-motion support and staff theme isolation passed.

## Public composition, scroll story and separate pages (23 October 2026)

- The user requested a stronger photo-free layout, better spacing using Taste/UI UX Pro Max, scroll-through participation cards and separate public pages, with About developed next. Keep the selected dark burgundy/light-grey/white palette and current typography.
- Replace the empty hero picture area with a functional directory panel linking to branches, participation and staff access. Use balanced heading/copy grids, a shorter Home introduction and a focused next-step section.
- Make your time count uses native document scrolling: a sticky heading/index follows three fully readable cards, and IntersectionObserver marks the current step in either scroll direction. CSS view timelines progressively enhance desktop card movement; no new dependency, wheel interception or overlapping content. Small/short screens and reduced motion retain linear reading.
- Share public language, metadata, header/footer and route definitions. Real URLs: /, /about, /programs, /branches, /events, /get-involved, /contact. About explains purpose, branch/volunteer/head-office roles and coordination. Other pages move the existing introductory information to separate documents with truthful unpublished states. CMS records/application submission remain pending.
- Fresh review identified mobile menu overlap obscuring keyboard focus. Reproduced with actual Tab navigation; the menu now expands in document flow and English/Urdu keyboard checks pass. Removed obsolete previous-section CSS. Keep feature/basic-login, no commit/push, photo-free output and public/auth separation.

## Network globe and one changing participation panel (23 October 2026)

- The user supplied frontend/References/image.png (world connections) and explicitly requested a globe/network figure moving with scroll, plus one changing paragraph/card instead of three visible cards. This supersedes the directory hero and earlier three-card scroll presentation.
- Draw an original spherical network with latitude/longitude lines, nodes and raised connection arcs in Canvas. Movement follows bounded native page scroll; no perpetual animation, geographic branch claims, photos, external mapping service or new package. Keep a static SVG fallback, descriptive caption and reduced-motion still state.
- Use one held participation stage, one current article/paragraph, three step buttons and previous/next controls. Native scrolling selects steps in both directions; directional text entry and a small scroll-linked lift convey change. Preserve the CTA, live region and controls between steps. Direct participation hash links remain supported.
- Reserve card dimensions and enable pinning only when the complete stage fits the viewport. Reduced motion/short screens retain a single manually selectable panel. Do not intercept wheel/touch scrolling or force an oversized panel to stay pinned.
- Fresh review's missing-animation-frame fallback and translated-key focus issues were reproduced with failing tests and corrected. Stable control IDs and a persistent live region preserve access. Narrow Urdu per-step measurements confirmed constant panel/stage height and pinning mode. All 39 tests and production build passed; keep the existing branch and user-controlled integration.

## Public-facing website branch and polish (23 October 2026)

- User explicitly requested a new branch. Created and switched to public-facing-website, preserving all uncommitted work. This supersedes the earlier stay-on-basic-login instruction for the branch move. No commit or push was requested or performed.
- Globe motion now combines a gentle continuous rotation with eased native scroll input. Target about30 canvas paints/second, and stop the loop while offscreen, hidden, user-paused or reduced motion is active. Pause/resume preserves the current orientation; use a visible localized control. Static Canvas/SVG and no-rAF fallback remain available.
- Interpreted second card as the Built around people section: enlarge its reading card and show both grounded paragraphs. Increase the story reading panel on tall screens. Format the closing call-to-action with clear paragraph/action groups and improve footer columns/spacing.
- Reproduced third-section failure: stage height654px English/718px Urdu exceeded common650px/600px laptop viewports, disabling pinning. Reduce compact-stage overhead and set explicit arrow-button line-height1; inherited Urdu line-height had still made controls too tall. This keeps story scrolling active at1280x600 and1366x650 without clipping text.
- Final behavioral suite41 tests passed. Browser checks passed12 English/Urdu layouts, forward/reverse story transitions, idle/scroll spin, pause/resume/offscreen pause and reduced motion. Fresh review found no remaining required issues after the sizing correction. Retain uncommitted work on public-facing-website; no backend or deployment changes.

## Complete public website (24 October 2026)

- User requested repaired scroll, a Taste/UIUX formatting review, Contact form, database-backed sample branches/events, and completion of the public view. Keep public-facing-website; no additional branch, commit or deployment.
- Use existing FastAPI/PostgreSQL/Redis instead of hardcoded public arrays. Migration 0003 adds a published bilingual catalogue and private correspondence. Explicit development-only, idempotent seeding adds three branches, three programs and six events. Clearly identify fictional data; preserve existing records on rerun.
- Story control clicks reposition directly instead of showing a selected paragraph before smoothly scrolling through earlier paragraphs. Reserve the largest text dimensions in an inaccessible sizing layer so changing text cannot change stage height. Keep native wheel/touch input, text transitions, continuous/scroll globe motion and manual reduced-motion/short-screen fallback.
- Contact and volunteer-interest forms store consented details and show receipts without email delivery or public account creation. Keep CSRF/origin protection and Redis limits, session-bound UUID retry deduplication, safe response schemas and private role-filtered staff inbox API. No staff inbox screen/CMS workflow in this public-page task.
- Names, email and correspondence are private PII, retained for the enquiry purpose up to 90 days. Store no IP in submission records. Daily cleanup command removes expired rows; deployment scheduling and backup retention belong to hosting setup.
- Independent review identified missing commit of inbox session activity. Reproduced with a separate request-session regression, fixed, and tested alongside role restrictions and expiry cleanup. Event fragment navigation waits for async catalogue targets. Public labels override inherited staff-form typography.

## Fractional viewport scroll fix and Home mobile layout (24 October 2026)

- Real mobile Chrome can report fractional CSS stage heights while innerHeight is integral. Allow1CSSpixel rounding tolerance when deciding if the story fits, preventing sticky/natural height feedback and document jumps. Keep readable oversized-stage fallback; do not intercept wheel/touch.
- Home stacks at900px to avoid compressed portrait tablet columns. Use consistent20–32px side gutters; compact the header below380px so menu/language controls keep the right gutter. Responsive overrides are scoped to Home.
- Exact375x667 wheel reproduction recorded192pinning changes before and0after; failing regression now passes. Twelve bilingual phone/tablet viewport checks and48frontend tests/build pass.

## Staff login visual consistency (24 October 2026)

- Apply the approved public burgundy theme to the staff entry and shared staff controls. Scope new styles beneath staff-shell to prevent changing public pages. Preserve existing authentication/session and form behavior.
- Keep a split brand/form layout on desktop, stack below760px, use16px labels/inputs and min54px input/56px submit heights. Make public Home reachable from the logo and a labelled backlink. Success/error states keep semantic colour and text, with visible focus.

## Branch management approval and implementation (24 October 2026)

- User approved docs/superpowers/specs/2026-10-24-branch-management-design.md. Extend existing branch records; generated immutable BR codes, Forming/Active/Paused/Closed, one lead/branch and one branch/lead, SA registry management and assigned-only Lead reads. Other internal roles denied in this module.
- Only published Active branches appear publicly or accept new volunteer interests. Pause/close unpublish; reactivation remains draft. Close is terminal, retains audit and releases assignment. No deletion or silent transfer.
- Use PostgreSQL sequence allocation, row locks plus expected revision, uniqueness constraints and atomic BranchAudit snapshots. Failed/conflicting writes retain drafts. POST commands match current CSRF/CORS conventions. Search/control input is bounded and validated before SQL.
- Resolve prior narrow auth findings: generation guards prevent late password callbacks restoring logged-out UI; malformed NUL login is422; reset target NOWAIT lock returns controlled409 rather than entering opposing actor/target waits. Existing wrong JSON shapes already validated correctly.
- Keep direct /staff/branches authenticated entry and browser navigation. Staff uses English controls, bilingual content/RTL Urdu fields, and the burgundy theme. Scoped list/detail/form/audit screens and paged eligible lead selection preserve the pending selected account across pages.
- Full95backend tests/92.22%coverage,57frontend tests/build and actual admin/Lead/public browser checks pass. Local schema0004 applied; original sample relationships retained. User controls commits/integration; branch unchanged.
