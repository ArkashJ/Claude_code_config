# Workflow rules (apply to every repo)

These exist because past sessions over-planned, faked visual verification, and
leaned on Docker for loops that don't need it. They override default caution.

## 1. Don't plan when you can just do it

- Do NOT enter plan mode unless I explicitly ask for a plan.
- For changes touching ~5 files or fewer: make the edit, then show me the diff.
  Brainstorm first only for genuinely non-trivial / architectural changes.
- One round of clarifying questions is fine. A long written plan for a small
  change is not — it burns the turn before any code lands.

## 2. Screenshot / visual honesty (never fake "I verified it")

- I cannot see a rendered UI by intuition. The ONLY way I "see" a page is by
  driving a headless browser, which produces a file.
- Every screenshot claim MUST include the absolute file path of the PNG AND the
  URL the browser actually landed on. No path printed = I have not seen it, and
  I must say so plainly.
- If a capture lands on a login/sign-in page, that is a FAILURE, not a success.
  Say "the session expired / I hit the auth wall" — never present a blank or a
  login page as the thing you asked for.
- Prefer a repo-local screenshot script that loads a SAVED auth session and
  exits non-zero when it bounces to login (template: `web/scripts/shot.ts` in
  the Strata repo). Reuse the e2e auth setup; don't reinvent the login flow.

## 3. Docker is for deploy parity, not the dev loop

- For making and verifying a frontend/UI change, use the local dev server plus a
  saved auth session. Do NOT spin up Docker just to render or screenshot a page.
- Reach for Docker only when the task is explicitly about prod build/parity,
  containers, or deploy.
