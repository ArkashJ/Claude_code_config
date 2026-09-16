# Visual checks (vcheck)

Two-layer visual verification for frontend dev work: a deterministic pixel-diff gate (`vcheck`, at `~/.local/bin/vcheck`) decides *which* pages changed; the agent (multimodal) judges *whether* the change is correct. Never eyeball unchanged pages — the differ already cleared them.

Use whenever making UI/frontend changes (CSS, components, templates, layout), or when asked to "visual check" / "did my change break anything visually".

## The loop

1. **Before touching frontend code** (or first time on a project): write the app's key URLs to `urls.txt` (one per line, `#` comments ok), make sure a playwright-cli session is open — log in through it if the app needs auth — then:

   ```bash
   vcheck base urls.txt
   ```

2. **After the change** (dev server reloaded):

   ```bash
   vcheck diff urls.txt
   ```

   Exit 0 = nothing changed visually — say so, done. Exit 1 = per-page `CHANGED`/`NEW` lines with paths.

3. **Judge only the CHANGED pages**: `Read` the diff PNG (changed pixels highlighted) and the cur PNG for each. Decide: intended change, or regression (broken layout, overlap, missing element, clipped text)? Report per page.

4. **If all changes are intended**, refresh the baseline so the next diff is clean:

   ```bash
   vcheck base urls.txt
   ```

## Notes

- All state lives in `./.vcheck/` (base/, cur/, diff/) in the cwd — per-project, gitignore it.
- `vcheck` captures one canonical 1440×900 desktop view. Add device/theme variants only for changed or explicitly required behavior.
- Captures run in parallel via `references/pcap.sh`, inherit the session's login, and disable animations/transitions/caret for determinism.
- Every capture inherits one active CLI session's role. `vcheck` parallelizes URLs, not RBAC actors or cross-role workflows.
- If the worktree is disposable or the images are review evidence, copy `urls.txt` and `.vcheck/` to a durable run-specific directory before refreshing the baseline or deleting the worktree; verify cited paths still exist.
- Flaky diff on a page with live data (clocks, feeds, ads)? Don't loosen the threshold globally — note the dynamic region in the judgment, or drop that URL from urls.txt.
- Bulk capture without diffing: `bash ~/.claude/skills/playwright-cli/references/pcap.sh urls.txt out/ 6` (parallel screenshots, inherits login).
- CI-grade upgrade path (when a project has a real test suite): `@playwright/test` `toHaveScreenshot()` with `mask:` for dynamic regions and `animations: 'disabled'`, baselines generated in CI/Docker. vcheck is the dev-loop tool, not the CI gate.
