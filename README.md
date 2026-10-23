# Branch-to-Head-Office Management Platform

A web platform connecting volunteer branches with head office, alongside the organisation's public website. Built for the ShipLens 1.0 challenge.

## Project status

**Staff account and authentication foundation.** Super Admins can create staff accounts and issue temporary-password resets. Staff complete a mandatory first-login password change. Login uses PostgreSQL-backed HttpOnly sessions, bcrypt with legacy-hash migration, CSRF protection and shared Redis rate limits. Business workflows, branch-scoped permissions and deployment remain to be implemented. See [security and account operations](SECURITY.md).

The authentication and staff account foundation is implemented; the business workflows and deployment are still planned. See [the development guide](docs/DEVELOPMENT.md) for local setup, CI checks and branch protection instructions.

## The problem

Branches currently manage volunteers and collected funds through scattered spreadsheets and WhatsApp messages. Head office manually combines weekly figures without reliable approvals or a history of changes. The public also needs a dependable place to learn about the organisation and apply to volunteer.

The platform will centralise branch records, volunteer applications, offline collections and weekly reporting. Head office will review financial reports, monitor branch activity and trace changes through an audit trail.

## Technology stack

FastAPI is the intended backend. The remaining application choices are the proposed stack from planning and may change as the architecture is finalised. PostgreSQL, GitHub Actions, Docker and Render are assignment requirements.

| Layer | Technology | Purpose |
| --- | --- | --- |
| Backend API | Python and FastAPI | Business workflows, validation and protected endpoints |
| API validation | Pydantic | Validate request and response data |
| Database | PostgreSQL | Persistent relational records |
| Data access | SQLAlchemy | Database models and queries |
| Migrations | Alembic | Versioned database schema changes |
| Rate limits | Redis | Atomic shared limits across API workers |
| Passwords | bcrypt through pwdlib | New hashes, with existing Argon2 verification during migration |
| Frontend | React and TypeScript | Public pages and role-based management screens |
| Frontend tooling | Vite | Development server and production build |
| Styling | Tailwind CSS | Responsive layouts and UI styling |
| Backend tests | pytest and coverage tooling | Verify workflows, permissions and backend coverage |
| CI | GitHub Actions | Automated checks for pushes and pull requests |
| Packaging | Docker | Reproducible application container |
| Hosting | Render with PostgreSQL | Live application and database |

Backend runtime dependencies are pinned in `backend/requirements.txt`; `backend/requirements-dev.txt` adds development tools. Frontend dependencies are locked in `frontend/package-lock.json`. The UI uses plain CSS; Tailwind remains proposed. Translation and PDF libraries remain to be selected.

## Run the staff portal

Start Docker Desktop, then set up PostgreSQL and the backend from the repository root in one PowerShell terminal. Copy the example environment file only on first setup; keep an existing configuration. See [database setup and design](docs/DATABASE.md) for details.

```powershell
docker compose up -d --wait db redis
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Copy-Item backend/.env.example backend/.env
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed --demo
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --no-proxy-headers
```

Start the frontend in a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite forwards `/api` requests to FastAPI on port 8000. The frontend requires Node 22.12+ (CI uses Node 24). The development proxy is not a production deployment configuration.

For local development only, explicitly seeded sample accounts use password `Demo123!` (existing passwords are never overwritten). Credential shortcuts are not shipped in the frontend:

| Role | Demo email |
| --- | --- |
| Super Admin | admin@example.test |
| Finance Reviewer | finance@example.test |
| Content Editor | editor@example.test |
| Branch Lead | branch@example.test |
| HR Lead | hr@example.test |

Sign in as the sample Super Admin and select **Manage staff accounts**. Enter a staff member's name, existing email, assigned role and temporary password, then share the credentials directly. The user signs in and sets a personal password before accessing their workspace. Temporary credentials expire in 48 hours; administrators can reset them from the staff list. No public signup, email-mailbox creation or email delivery is included.

Login survives refresh via a server-side session and logout revokes it. Sessions expire after 30 minutes idle or 8 hours total. New passwords require at least 15 characters and at most 72 UTF-8 bytes. On a fresh non-demo installation, create the first Super Admin with `python -m app.bootstrap` from backend; it prompts for credentials without exposing a password in command arguments. Demo seeding is refused in production. See [SECURITY.md](SECURITY.md) for endpoint contracts, deployment settings and current limitations.

## Planned architecture

Use one repository containing a React frontend and a modular FastAPI backend, connected to one PostgreSQL database. Backend modules will separate authentication, branches, applications, members, collections, reports, content and auditing.

```text
Public visitors and authenticated staff
                  |
           React frontend
                  |
             FastAPI API
                  |
             PostgreSQL
```

Serving the production frontend and API on one origin is the intended deployment layout; Render deployment configuration remains pending. Authentication uses server-side session cookies.

The backend must enforce permissions, branch boundaries, report transitions and record locks. Frontend controls alone do not provide access protection.

## Users and roles

The public can browse published information and apply to volunteer. Authenticated staff use five system roles:

| Role | Intended responsibility |
| --- | --- |
| Super Admin | Platform administration; exact administrative permissions to be defined |
| Finance Reviewer | Review weekly reports and approve or return submissions |
| Content Editor | Manage website content through draft and published states |
| Branch Lead | Manage permitted branch operations and submit weekly reports |
| HR Lead | Review volunteer applications and accept or decline applicants |

This table summarises responsibilities, rather than defining the final authorisation policy. A detailed permission matrix must specify each action and its branch scope. Organisational member roles are separate from system access roles; membership does not automatically imply a login account.

## Required features

### Public website and languages

- Seven pages: Home, About, Programs, Branches, Events, Get Involved and Contact.
- Branch listings, programme information and events.
- Volunteer application form with full validation.
- English and Urdu support, including right-to-left layouts for Urdu.

### Branch management

- Branch register with automatically generated codes.
- Branch statuses: Forming, Active, Paused and Closed.
- Defined lifecycle transitions and branch access rules.

### Volunteer applications and members

- HR can accept or decline applications.
- Acceptance automatically creates a member with a generated ID.
- Member records support teams, organisational roles, status, search and filters.

### Offline collections and transfers

- Record offline collections; online payments are outside the assignment scope.
- Collection entries lock after seven days.
- Identify collections not yet sent to the main account.
- Transfer tracking and confirmation rules must be defined before implementation.

### Weekly reporting

- Automatically draft weekly reports.
- Branch Leads submit reports for review.
- Finance Reviewers return reports for correction or approve them.
- Returned reports can be resubmitted.
- Approved reports lock against further modification.
- Every workflow action is recorded in the audit trail.

```text
Draft -> Submitted -> Approved (locked)
             |
             v
          Returned -> Resubmitted -> Review again
```

These labels describe the required workflow; internal status names are still to be designed.

### Head office dashboard and exports

- KPIs and monthly trends across branches.
- List of collections not yet sent to the main account.
- Correct calculations against the supplied sample data and expected values.
- CSV and PDF report exports.

### Content management and auditing

- Website content with draft and publish states.
- Audit trail of all changes, including report transitions.
- Planned audit details include the actor, timestamp, action, affected record and changed values. Sensitive fields must be handled appropriately when the audit design is finalised.

## Quality and acceptance criteria

The completed submission must demonstrate:

1. Correct dashboard values after loading the provided sample data.
2. A complete report sequence: draft, submit, return, resubmit, approve and lock, with an audit record for every step.
3. Automated tests proving roles cannot access forbidden data or actions.
4. A working Render deployment and a passing GitHub Actions pipeline on `main`.

Additional requirements include at least **60% backend test coverage**, security against OWASP Top 10 risks, a Dockerfile and a health endpoint. Lighthouse **90+** is included in the judging criteria.

Priority test areas will include cross-branch access, role permissions, application acceptance, collection lock boundaries, report transitions, approved-report immutability and financial calculations. On 23 October 2026, the authentication foundation passed 55 PostgreSQL/Redis-backed tests with 89.47% backend coverage on Python 3.14; Ruff lint/format and Alembic drift checks passed. The frontend passed 12 tests and its TypeScript/Vite production build. A browser walkthrough verified account creation, first-login password change, refresh restoration, role-specific UI and logout at desktop/tablet/mobile widths. One upstream Starlette/httpx deprecation warning remains. These results do not measure completion of the business features or verify the feature's GitHub CI run.

## Development roadmap

- [x] Review the assignment and discuss requirements.
- [x] Record project context and create the initial README.
- [x] Add a minimal FastAPI foundation and GitHub Actions CI workflow.
- [x] Add a basic demo login page, endpoint and frontend CI build.
- [x] Add PostgreSQL account storage, Alembic migrations, password hashing and database integration tests.
- [ ] Publish branches, verify the first GitHub CI run and configure branch protection.
- [ ] Finalise the permission matrix, reporting rules and database schema.
- [x] Implement the initial authentication and staff account provisioning foundation (see [SECURITY.md](SECURITY.md)); full business permissions and audit coverage remain open.
- [ ] Implement branch management and organisation-wide auditing.
- [ ] Implement applications and member management.
- [ ] Implement collections, transfer tracking and weekly report review.
- [ ] Implement dashboard calculations and CSV/PDF exports.
- [ ] Build public pages, content management and English/Urdu support.
- [ ] Complete security checks, automated tests and coverage requirements.
- [ ] Add Docker packaging, health checks and Render deployment.
- [ ] Verify sample-data acceptance checks and complete submission materials.

The first planned end-to-end workflow is: create a branch, receive an application, accept it into membership, log a collection, submit a report, return and resubmit it, then approve and lock it.

## CI and deployment plan

The [CI workflow](.github/workflows/ci.yml) runs on pull requests targeting `dev` or `main`, on pushes to either branch (including merges), and manually. The development flow is **feature branch -> PR into dev -> release PR into main**. Updated commits on an open PR rerun CI.

Current checks use Python 3.12, Ruff lint/format and pytest against PostgreSQL 16 and Redis 7 with a 60% backend coverage gate. CI applies migrations, checks model drift, and verifies downgrade/re-upgrade against its disposable database. A frontend job uses Node 24, `npm ci`, frontend tests and `npm run build`. See [branching and CI setup](docs/DEVELOPMENT.md) and [database instructions](docs/DATABASE.md). Application Docker image checks will follow when a Dockerfile exists; local Compose currently runs PostgreSQL and Redis only. No live deployment is available yet.

## Repository and documentation

Current project documents:

- [Task.md](Task.md): original assignment brief.
- [Context.md](Context.md): discussion history, proposed decisions, progress and open questions.
- [README.md](README.md): project overview and development entry point.

Planned documentation includes:

- Architecture decisions and system design.
- API documentation.
- Detailed permission table.
- Local setup, environment configuration and deployment instructions.
- Handover guide.
- [AI-USAGE.md](AI-USAGE.md): AI assistance declaration.
- [SECURITY.md](SECURITY.md): implemented authentication and staff-account operations, API behavior and deployment security settings.
- Open-source library credits and an MIT licence file.

## Outstanding decisions and inputs

- Organisation identity, brand assets and public content.
- Provided sample data and expected dashboard calculations.
- Surprise twist requirements.
- Exact permissions, global versus branch scope and user role assignments.
- Branch lifecycle rules, branch code format and member ID format.
- Application fields and duplicate handling.
- Collection lock reference time, correction rules and transfer confirmation.
- Reporting periods, automatic drafting mechanism and report snapshot behaviour.
- KPI definitions and whether each figure uses approved reports or live records.
- Translation scope and final deployment layout.

These details are not fully specified by the available brief and should not be treated as settled business rules.

## Submission requirements

- Public GitHub repository with an MIT licence.
- At least 25 genuine commits across at least seven days, with three merged pull requests.
- Work within the permitted build window; the brief disallows commits before 12 October 2026.
- Live Render application with PostgreSQL.
- Final commit hash identifying the judged version.
- One test login for each of the five roles.
- README, AI usage declaration and required documentation.
- Walkthrough video of up to five minutes, explained in the participant's own voice.
- For pairs, real commits from both participants and both speaking in the video.

Use only the supplied sample data, produce original work and credit open-source libraries. AI assistance is allowed when declared and the participant can explain the implementation.

The stated deadline is **26 October 2026, 11:59 PM PKT**. Starting on 21 October leaves six calendar dates through the deadline, which appears insufficient for the seven-day history requirement unless qualifying work already exists or the organisers clarify an exception. This remains unresolved; preserve genuine commit dates.

## Judging

| Category | Points |
| --- | ---: |
| Architecture and code quality | 15 |
| Head office features working end to end | 15 |
| Roles, permissions and audit trail | 10 |
| OWASP Top 10 security | 15 |
| Automated testing and passing CI | 15 |
| Docker and deployment | 10 |
| Content manager, bilingual support and performance | 10 |
| Surprise twist | 5 |
| Documentation and demo | 5 |

## Licence

The assignment requires the MIT licence. The licence file has not been added yet; its copyright holder must be established during repository setup.
