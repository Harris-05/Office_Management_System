# Local acceptance record

Verified 2 November 2026. Implemented on `feature/branch-management`; latest observed user commit `3fa6197`. The assistant made no commits, pushes or branch changes. The application is running at **http://localhost:18080**; staff entry is **http://localhost:18080/staff**.

## Delivered scope

- Public seven-page English/Urdu website, RTL, contact/volunteer forms and published catalogue.
- Staff cookie-session authentication, bcrypt, CSRF/origin/role checks, shared Redis limits and administrator-provisioned accounts.
- Branch lifecycle/assignment/publication, HR application decisions and separate member records.
- Exact PKR collections with immutable creation-based 168-hour editing, post-lock whole-entry transfers and independent Finance confirmation.
- Automatic weekly drafts; immutable submission revisions; Finance Return/resubmission/approval; approved locking and later-source discrepancy warnings.
- Scoped head-office dashboard, monthly trends, cumulative transfer reconciliation, outstanding collections and complete bounded CSV exports.
- Bilingual staff CMS with separate drafts/public copies, protected preview, publication history and lifecycle-aware events.
- Unicode/Urdu font-embedded PDF reports, formula-safe UTF-8 CSV and authenticated downloads that show errors without losing forms.
- Non-root same-origin Docker image, schema/Redis readiness, hourly maintenance, Compose, container CI checks and a Render Blueprint.

The architecture, permission matrix, financial definitions, API map, local setup and deployment/recovery instructions are in [HANDOVER.md](HANDOVER.md). Decisions are in [desicions.md](desicions.md).

## Executed checks

| Check | Observed result |
| --- | --- |
| Full PostgreSQL/Redis-backed backend suite | **207 passed**, **92.78%** branch-aware coverage; unchanged 60% gate |
| Full frontend suite | **116 passed**, 20 files; no increased timeouts or skipped assertions |
| TypeScript and Vite production build | Passed; public entry/staff code split into separate chunks |
| Ruff lint/format | Passed, 84 Python files |
| Schema migration | Dedicated test database 0007 -> 0009 downgrade/re-upgrade and model drift passed; development head 0009 retained existing data |
| Production image | Build passed; healthy non-root `10001:10001`; exact final image identifier recorded locally |
| Production-mode route/header smoke | 12 SPA/API/status checks passed, CSP/HSTS, health probe and actual maintenance command |
| Render configuration | Validates locally against Render's official JSON Schema; no hosted services created |
| Frontend dependency audit | Zero known vulnerabilities in the committed dependency lock |
| Production Python dependency audit | 35 runtime packages, zero known vulnerabilities after upgrading `fpdf2` to patched 2.8.8 |
| Diff whitespace check | Passed |

The PDF audit initially identified two upstream image/HTML advisories. The exporter handles plain text and fixed local fonts, and the pin was still upgraded. Actual PDF exports, embedded fonts and Arabic shaping were rechecked on the final image. See the [official patched release](https://github.com/py-pdf/fpdf2/releases/tag/2.8.8). Audit results reflect available advisory data at check time, not a complete security certification.

## Browser acceptance

Actual Chrome workflows verified the weekly report Draft -> Submit -> Return -> Resubmit -> Approve sequence, two frozen revisions, seven audit steps, rejected approved edits, Unicode CSV/PDF downloads, Finance dashboard reconciliation, Admin read-only access and HR denial. Twelve report/dashboard layouts at 320/390/768/1440px had no horizontal overflow and one h1; no runtime exceptions.

Actual CMS browser checks verified create/publish, edit a separate private draft, protected escaped preview, HTTP 409 input preservation/explicit reload, republish, Urdu RTL public rendering, unpublish and seven attributed history entries. Twelve layouts passed with no overflow or runtime exceptions.

The final performance changes were additionally checked in Chrome: eight Home layouts in English/Urdu at 320/390/768/1440px; locally loaded licensed fonts; no public request for staff code or remote fonts; natural globe spin, pause/resume/reduced motion; one-panel story progression and reversal with scroll; native wheel; lazy staff login/dashboard and a real patched-library font-embedded PDF download. No runtime errors were observed. Screenshots/PDF pages were visually inspected.

## Mobile Lighthouse

Initial Home performance was 48. Measured changes: lazy staff import, self-hosted font subsets, public static JS/CSS gzip and depth-batched canvas strokes. Private API responses remain uncompressed; security/rate limits and motion preferences remain unchanged.

Final Home: **performance 98 / accessibility 100 / best practices 100 / SEO 100**; FCP/LCP 1.6s, total blocking time 140ms, CLS 0. Measurements use Lighthouse 13.6.0's default simulated mobile throttling against the production build served locally by Docker. All seven routes meet the local 90+ performance target: Local synthetic measurements do not replace checks on a deployed HTTPS hostname.

| Public route | Performance | Accessibility | Best practices | SEO |
| --- | ---: | ---: | ---: | ---: |
| / | 98 | 100 | 100 | 100 |
| /about | 90 | 100 | 100 | 100 |
| /programs | 96 | 100 | 100 | 100 |
| /branches | 99 | 100 | 100 | 100 |
| /events | 93 | 100 | 100 | 100 |
| /get-involved | 100 | 100 | 100 | 100 |
| /contact | 99 | 100 | 100 | 100 |


## Evidence and fixture handling

Durable local evidence (ignored by Git) includes:

- `.venv/completion-backend-final.log`, `.venv/completion-frontend-final.log`, `.venv/completion-docker-final.log`.
- `.venv/production-smoke.json`, `.venv/render-blueprint-validation.json`, `.venv/completion-runtime-audit.json`.
- `.venv/report-ui-review/checks.json`, `.venv/content-ui-review/checks.json`, `.venv/performance-ui-review/checks.json` and screenshots.
- `.venv/lighthouse-*-final.json`, `.venv/lighthouse-public-summary.json`.
- `.venv/final-report-fixes-review.md`, `.venv/final-ops-content-review.md`, `.venv/final-performance-review.md`.

Synthetic browser data is labelled. The new CMS programme finishes unpublished. Report verification branch BR-000006 finishes Closed/unpublished with an approved zero-value report and audit history retained. The demo Branch Lead is unassigned again. Original collection business dates/editing deadlines were not changed, and no business data was deleted. Previously labelled synthetic transfers remain historical fixtures, not bank receipts.

The repository's existing ignore policy still excludes docs/Context and local evidence. This tracked root record and HANDOVER preserve essential submission information; include any chosen ignored formal guides/evidence explicitly when preparing a submission.

## External acceptance still required

- Official organiser sample data and expected dashboard values; approved organisation identity/copy/assets and surprise-task requirements.
- Render account/repository connection, actual service provisioning and deployment; live HTTPS/session/role/cron/recovery checks and real live URL.
- Actual GitHub CI on main, PR/branch-protection verification and the user's genuine qualifying commit history.
- Deadline/history clarification if applicable, final judged commit hash and the participant's own-voice walkthrough video.

No live deployment, official-data reconciliation, remote CI result or submission eligibility is claimed by these local checks. Automatic language translation remains deferred; bilingual editing/rendering is implemented without an external translation or email service.
