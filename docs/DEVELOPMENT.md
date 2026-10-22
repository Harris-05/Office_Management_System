# Branching and CI

## Workflow

```text
feature/<name> -> pull request -> dev -> release pull request -> main
                       CI         CI             CI              CI
```

- Create each feature branch from an up-to-date `dev`.
- Push the feature branch, then open a pull request targeting `dev`.
- CI runs when the PR opens and whenever new commits are pushed to it. Pushing a feature branch without a PR does not trigger this workflow.
- Merge after CI succeeds. CI also verifies the resulting commit on `dev`.
- When ready to release, open a PR from `dev` into `main`.
- CI checks that PR and runs again on `main` after the merge.
- Manual runs are available through Actions once the workflow is on the default branch.

CI does not automatically open or merge PRs, or deploy the application.

## Initial repository setup

The workflow and application foundation must first be committed and pushed through a bootstrap PR. Create/publish `dev` from the existing `main` if it does not exist, then branch the CI work from `dev` and open its PR back into `dev`. Promote `dev` to `main` through a release PR once checks pass. These remote actions have not been performed by the local setup.

Subsequent feature work:

```sh
git switch dev
git pull --ff-only origin dev
git switch -c feature/short-description
# Make changes, stage specific files, and commit.
git push -u origin feature/short-description
# Open a GitHub PR with base branch dev.
```

## Current checks

The `CI` workflow exposes a `Backend checks` job using Python 3.12:

1. Install backend development dependencies.
2. Run Ruff lint checks.
3. Check Ruff formatting.
4. Run pytest with branch coverage and a minimum 60% backend coverage gate.

The backend currently has a liveness endpoint and a demo login endpoint with tests. Its coverage does not demonstrate completion of the business requirements. Add permission and workflow tests as features are implemented.

The `Frontend build` job uses Node 24, installs from `frontend/package-lock.json` with `npm ci`, and runs `npm run build` (TypeScript validation and Vite production build). Run these commands from `frontend` locally too. PostgreSQL integration tests and Docker validation must be added when those components exist.

## Local validation (PowerShell)

From the repository root, using Python 3.12 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Set-Location backend
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Visit `/health` for process liveness or `/docs` for the generated API documentation. The endpoint does not check database readiness.

## Protect dev and main on GitHub

Workflow files run checks; repository rules enforce whether a merge is allowed. Configure branch rules for both `dev` and `main` after the first CI run:

- Require a pull request before merging.
- Require the `Backend checks` status check from GitHub Actions.
- Also require `Frontend build` once the basic-login workflow has run.
- Require branches to be up to date before merging.
- Block force pushes and branch deletion.
- Apply rules to administrators/bypass users as appropriate.
- For a solo project, do not require approval from a second person unless a reviewer is available.

Keep job names stable because branch rules refer to them. The documented `dev`-to-`main` promotion convention is not enforced by the YAML; branch permissions/rules should govern who can merge release PRs. Repository settings have not been changed by this setup.

References: [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).
