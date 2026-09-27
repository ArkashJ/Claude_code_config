# Changelog

## v1.5.0 — 2026-09-27

- **Hosted CI is not a gate** (user policy). /wrap, /start and /mission now require local gates, batched pushes,
  and an `--admin` merge when protection blocks only on hosted CI. qa `review.py` no longer blocks PRs whose CI
  never ran; failing checks still block.
- **Built-in SWEEP families**, calibrated on fixtures: `export_opportunity`, `bulk_opportunity`,
  `destructive_ungated` (persists × ungated), `notify_recipients`. First real runs found extractor bugs, not
  model errors (`removeItem`, `removeEventListener`, a `def send_email(` line); those are fixed in code.
- `sweep.py`: `--since` for session-end runs, inline fixture labels, an `absent` filter that skips pages which
  already have the feature, and "fixture-calibrated" marking.
- qa SKILL: a lens map giving every "what to look at" area its one owning mechanism. It came from a Jev pass
  over 679 human turns in 187 sessions.
- harvest step 0c runs every calibrated family on the session's changed files.

## v1.4.0 — 2026-09-27

- **qa SWEEP (`skills/qa/sweep.py`)**: a port of the per-repo Jev pattern sweep that produced repo A's
  swallowed-failure and tenant-scope fixes. Code extracts every site of a pattern (`grep` to the enclosing
  function, `py_except`, `file`), Jev asks one narrow question per site, and code ranks the answers. A family
  lives in `<repo>/.qa/families.json`, so client wording stays in the client repo. `run` refuses a family that
  has not passed `calibrate` on labelled sites (positives >= 0.70, negatives <= 0.30). A label can be a fix's
  own pre-fix revision. Per-label MISS lines, FLAT-question warnings, cross-file `facts` computed by code,
  secret redaction, and a cache keyed on state+questions+model are included. On repo A it found 654 sites
  (the original run found 652) with 0 errors; flags dropped from 35 to 13 after one false-positive class was
  fixed with code-computed evidence.
- harvest step 0b / wrap: each fix from a session becomes a calibrated family swept with `--all-repos`.
  The vague `signals.py --related` questions are deleted: in 3 runs they never scored above 0.68,
  and `same_gap` barely varied (sd 0.03-0.05).
- `hunt.py --since`: a Jev pass over only the code a session changed. /mission phase wraps run the asks ledger.

## v1.3.0 — 2026-09-27

- **harvest reads the transcript, not memory.** `skills/harvest/signals.py` has Jev judge every human turn
  (correction, re-ask, doubted claim, wants depth) and route every ask to the command that proves it. Added
  because each studied harvest was followed by "are you sure thats ALL YOU LEARNT???". Harvest now ends with
  `acted X of N`.
- **`--related` carries a session's fix across repos.** It finds code under `~/Developer` and `~/Benmore` that
  shares the session's identifiers, and Jev judges whether it has the same concern, could reuse the fix, or has the same gap.
- **wrap proves asks with commands**: `repo-hygiene.sh --landed` ends with a computed `SAFE TO END` line.
  The Codex `wrap` is generated from `wrap.md`, and `sync.sh` fails on section drift. The broken `~/.Codex/commands` paths are fixed.
- qa: Noul answers read as `{noul}`, a named User-Agent (Cloudflare 1010), conflicting PRs re-tiered correctly.

## v1.2.0 — 2026-09-22

- **One real copy per skill across Claude and Codex** (`commands/bin/link-skills.sh`, run by `claude-sync`).
  A previous sync had duplicated every shared skill; `qa` edits never reached Codex, `document-consolidation`
  was an orphaned submodule with no SKILL.md, and Codex variants of start/wrap/mission shadowed the Claude commands.
- Codex prompts for `review-queue`, `ui-hunt`, `backend-edges`, `featuredev`, `map`; `sync.sh` reads descriptions
  from the command files and never writes through a symlink.
- `qa` skill: HISTORY/HUNT/REVIEW/DOCS modes built on Jev. Generic wrapper-hook detection, repo waivers,
  dependency-provenance fact for draft_clobber, budget-blocked CI detection, PARITY/STATES recipes. Client names removed.
- `skill-collisions.py` moved into `commands/bin/`.

## v1.1.1 — 2026-09-22
- Track `CHANGELOG.md` (the root `/*` ignore rule hid it from v1.1.0).

## v1.1.0 — 2026-09-22

Sync of the rebuilt `~/.claude` after the 2026-09-16 wipe.

### Added
- `hooks/guard-bash.sh` (+ `guard-bash.test.sh`): PreToolUse Bash guard — blocks `sleep N`
  anywhere in a command and `cd X && cmd` chains. Wired in `settings.example.json`.
- Commands: `/backend-edges`, `/review-queue`, `/ui-hunt`.
- Skills: `qa` (merges `qa_skill` + `frontend-verify`), `packet-plan`, `find-skills`,
  `typesafe-ai`, `featuredev`, `map`.
- `CLAUDE.md`: enumeration discipline, no-`sleep` rule, no `cd &&` chains, LSP-first navigation.

- `claude-sync adopt` works on any machine in one command: falls back to HTTPS when no
  SSH key is loaded, always links `~/.local/bin/claude-sync`, and reinstalls every plugin
  and marketplace from `plugins/*.json`.

### Changed
- `claude-sync` (push) pulls with `--rebase --autostash` first, so pushes from several
  machines never get rejected; `claude-sync pull` autostashes local edits.
- `settings.example.json` writes `$HOME` as `~`, so hook paths work for any user, adds a
  SessionStart hook that runs `claude-sync pull` in the background, and no longer carries
  `autoMode` (it held client-specific policy; this repo is public).
- `settings.example.json` regenerated from the live settings: `opus[1m]`, auto permission
  mode, per-model effort, ponytail / typesafe marketplaces.
- Plugin manifests, `agents-skill-lock.json`, `/start`, `/wrap`, `/mission`, `/map`,
  `/checkpoint` refreshed.

### Removed
- `qa_skill`, `frontend-verify` (folded into `qa`).
- `source-command-{checkpoint,start,wrap}` skills, `/harvest` and `/investigate` commands
  (`harvest` lives on as a skill).

## v1.0.2 — 2026-05-30
- hooks: make format-on-edit repo-aware (Prettier vs Biome).

## v1.0.1 — 2026-05-30
- config: prune stale turn-counters, allowlist context-mode MCP, tool prefs.

## v1.0.0 — 2026-05-29
- Initial production release.
