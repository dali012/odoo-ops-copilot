# Contributing to Odoo Ops Copilot

Thanks for your interest in contributing! This document explains how to propose
changes and the one legal step required before your first contribution can be
merged.

## Contributor License Agreement (required)

Odoo Ops Copilot is **dual-licensed**: the public repository is
[AGPL-3.0](LICENSE), and a separate commercial license is offered to users who
can't accept AGPL terms. To keep that model viable, every contributor must agree
to the [Contributor License Agreement](CLA.md) before their contribution is
merged.

In short, the CLA lets the project maintainer include your contribution in
**both** the AGPL edition and the commercially-licensed edition, while you retain
copyright in your contribution. You only need to agree once.

**How to sign:** on your first pull request, add a comment with exactly:

```
I have read the CLA and I agree to its terms on behalf of myself and, where
applicable, my employer.
```

If you're contributing on behalf of a company, please make sure you're
authorized to agree to the CLA for that company.

## Development setup

See the [Local Setup](README.md#local-setup) section of the README for the full
stack (Odoo 18 + Postgres + FastAPI backend + Next.js frontend). Local
development targets **Odoo Community 18**.

## Before you open a pull request

Run the same checks CI runs — all must pass:

**Backend** (from `backend/`):

```bash
ruff check .        # lint
pytest              # offline unit tests (no Odoo/API needed)
```

**Frontend** (from `frontend/`):

```bash
npm run lint
npx jest
npm run build
```

**If you change agent tools, the seed, or write-backs**, also run the live
checks against a seeded Odoo 18 stack (these mutate Odoo, so use a throwaway
instance):

```bash
cd backend
RUN_LIVE_TESTS=1 python -m unittest test_writeback_live test_sql_guardrails
python -m app.eval_harness --fail-under 0.85   # golden-question suite
```

> Why the live tests matter: mocked tests assert on the arguments passed to a
> fake `odoo.execute` — they cannot catch real Odoo API breakage (e.g. a field
> renamed between Odoo versions, or a model constraint). The live writeback
> tests execute against a real Odoo 18 instance and are the regression guard.

## Conventions

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `test:`, `ci:`, `refactor:`, `chore:`).
- **Python:** PEP 8, type annotations on function signatures, `ruff`-clean.
  Prefer many small focused modules over large ones.
- **TypeScript:** explicit types on public/exported APIs and component props;
  avoid `any`; `eslint`-clean.
- **Tests:** add or update tests for any behavior change. New pure logic should
  be unit-tested; new Odoo-touching code should have a live test.
- **No secrets** in code or fixtures.

## Reporting bugs / proposing features

Open a GitHub issue describing the problem or proposal. For security issues,
please contact the maintainer privately via [dali012.me](https://dali012.me)
rather than filing a public issue.
