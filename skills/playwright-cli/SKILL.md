---
name: playwright-cli
description: Automate browser interactions, test web pages and work with Playwright tests. Also covers automated visual regression checks for frontend dev work (vcheck — capture baseline screenshots, pixel-diff after UI/CSS changes, judge only changed pages) and parallel bulk screenshot capture (pcap.sh).
allowed-tools: Bash(playwright-cli:*) Bash(npx:*) Bash(npm:*) Bash(vcheck:*) Bash(odiff:*)
---

# Browser Automation with playwright-cli

## Quick start

```bash
# open new browser
playwright-cli open
# navigate to a page
playwright-cli goto https://playwright.dev
# interact with the page using refs from the snapshot
playwright-cli click e15
playwright-cli type "page.click"
playwright-cli press Enter
# take a screenshot (rarely used, as snapshot is more common)
playwright-cli screenshot
# close the browser
playwright-cli close
```

## Visual checks & bulk capture

For frontend changes, run automated visual regression via `vcheck` (baseline → pixel-diff → judge only CHANGED pages): read `references/visual-checks.md` for the loop. For parallel bulk screenshots of many URLs (inherits the session's login): `bash ~/.claude/skills/playwright-cli/references/pcap.sh urls.txt out/ 6`.

Default to one canonical desktop viewport and theme. Add mobile, dark mode, or other variants only when the change touches that behavior, the product requires it, or a known bug needs it. Do not create a device × theme matrix by habit.

## Execution policy

### Preserve evidence

When screenshots, snapshots, traces, videos, console logs, or request logs are proof of work, write or copy them to a durable run-specific directory outside disposable worktrees and temporary directories. Before reporting completion, verify every referenced absolute path still exists. Record the automation surface, session name, role, URL, command, and expected state with the artifacts.

### Name every role session

Use a different named session for each authenticated actor. Do not exercise multiple RBAC roles through the unnamed/default session.

```bash
playwright-cli -s=rbac-admin open https://app.example.com
playwright-cli -s=rbac-member open https://app.example.com
playwright-cli -s=rbac-viewer open https://app.example.com
```

Element refs and storage belong to one session. Never reuse a ref across sessions. Roles communicate only through application state and explicit record IDs, never by copying cookies or storage between roles.

### Parallelize only independent work

- Use `pcap.sh` for parallel screenshots of independent URLs under one role.
- Run independent named-role or scenario sessions concurrently only when their test data cannot collide.
- Keep cross-role dependencies sequential at business-state barriers: create → observe committed record ID/status → approve → observe new status → audit.
- Use unique run IDs for shared records. Do not synchronize through “newest row” or fixed sleeps.

### Batch only deterministic stretches

Normal ref-driven exploration observes after each state-changing action. If several steps require no decision from intermediate state, test batching them with `run-code` and return one final assertion/result. Observe again at navigation, popup, frame, rerender, or role-handoff boundaries. Do not batch merely to hide an intermediate failure; a batch must identify the failed step.

### Record an audit preflight

Before a material, repeatable, or performance-sensitive run, record:

- the actual automation surface and `playwright-cli --version`;
- application revision/base URL and whether the app is cold or prewarmed;
- run ID, named session, role, and durable evidence root;
- the exact expected terminal business state, not just “page loaded”;
- tracing/output policy and any concurrent workloads.

For performance claims, also record the resolved executable/runtime and compare matched A/B arms with warmups and repeated alternating trials. Change one variable at a time and run the control before accepting a fix.

### Prove RBAC in layers

For each shared entity, retain its exact ID and test three distinct claims:

1. **UI affordance:** the role sees only allowed controls.
2. **UI path:** the allowed control sends the expected request and reaches the committed business state.
3. **Server enforcement:** a forbidden operation under the denied role is rejected and leaves the entity unchanged.

Label `eval`/`fetch` calls as direct API evidence; they do not prove that the UI dispatched the request. Sanitize tokens, cookies, and sensitive request data from retained artifacts. Stop and preserve evidence immediately if a forbidden mutation succeeds.

Exercise forbidden mutations only in an authorized non-production environment with disposable data. Require the application's documented authorization denial and verify the entity stayed unchanged; authentication, validation, CSRF, or conflict failures are inconclusive RBAC evidence.

### Wait for business state

Prefer a stable record ID/status/version, matching response, exact locator state, or URL plus content assertion. Do not use `networkidle` as a universal readiness signal; long polling, WebSockets, background fetches, and delayed application commits make network quiet unrelated to readiness.

## Persona sessions from the QA harness

`qa` (frontend-verify) signs each persona in through the app's own `verify.auth-launcher.mjs` and measures in its own Playwright contexts. Those logins live in a private lease that is deleted after every run, so a playwright-cli session never inherits them. To explore as the same principal the sweep measures, run the launcher yourself and load its state into a named session:

```bash
LEASE=$(mktemp -d "$TMPDIR/qa-lease.XXXX") && chmod 700 "$LEASE"
QA_BASE=https://app.example.com node verify.auth-launcher.mjs staff 3<<<"{\"leaseDir\":\"$LEASE\"}"
# prints {"ok":true,"stateFile":"staff.json"}
playwright-cli -s=staff open https://app.example.com
playwright-cli -s=staff state-load "$LEASE/staff.json"
playwright-cli -s=staff reload
```

One session per persona, named after it, so the RBAC rules above hold. If the app keeps its credential in sessionStorage the launcher writes `<persona>.session.json` beside the state; replay it with `sessionstorage-set` after `open`. Delete `$LEASE` when done; never copy it into `.verify/` or a repo.

The durable output of the session is a selector or journey file for `qa`, never the session itself. Going the other way, a launcher can be as small as copying a `state-save` file into the lease at mode 0600.

## Keep it fast

Browser startup is amortized by the daemon. Per-command cost is one shell spawn, one socket round trip, and the snapshot. Snapshot cost scales with rendered DOM nodes, so speed means fewer and smaller snapshots.

- **Chain when the next ref is known.** Every action returns a snapshot; act on refs you already hold and snapshot once at the end. Never snapshot twice with no state change between.
- **Batch deterministic stretches in `run-code`.** Login plus three clicks plus one assertion is one process and one snapshot, not five. Return a result that names the failed step.
- **Log in once.** `state-save auth.json` after the first login, `state-load auth.json` on later opens. Use `--persistent` for state that should survive days.
- **Read scalars with `--raw` or `--json`.** A cookie value or count is one line, not a page snapshot.
- **Skip `--boxes` unless you need geometry.** It adds layout reads for every node.
- **Snapshot the region, not the page** when a large list or table is on screen; scope via `eval` on a ref when only one value matters.

## Commands

### Core

```bash
playwright-cli open
# open and navigate right away
playwright-cli open https://example.com/
playwright-cli goto https://playwright.dev
playwright-cli type "search query"
playwright-cli click e3
playwright-cli dblclick e7
# --submit presses Enter after filling the element
playwright-cli fill e5 "user@example.com"  --submit
playwright-cli drag e2 e8
# drop files or data onto an element (from outside the page)
playwright-cli drop e4 --path=./image.png
playwright-cli drop e4 --data="text/plain=hello world"
playwright-cli hover e4
playwright-cli select e9 "option-value"
playwright-cli upload ./document.pdf
playwright-cli check e12
playwright-cli uncheck e12
playwright-cli snapshot
playwright-cli eval "document.title"
playwright-cli eval "el => el.textContent" e5
# get element id, class, or any attribute not visible in the snapshot
playwright-cli eval "el => el.id" e5
playwright-cli eval "el => el.getAttribute('data-testid')" e5
playwright-cli dialog-accept
playwright-cli dialog-accept "confirmation text"
playwright-cli dialog-dismiss
playwright-cli resize 1920 1080
playwright-cli close
```

### Navigation

```bash
playwright-cli go-back
playwright-cli go-forward
playwright-cli reload
```

### Keyboard

```bash
playwright-cli press Enter
playwright-cli press ArrowDown
playwright-cli keydown Shift
playwright-cli keyup Shift
```

### Mouse

```bash
playwright-cli mousemove 150 300
playwright-cli mousedown
playwright-cli mousedown right
playwright-cli mouseup
playwright-cli mouseup right
playwright-cli mousewheel 0 100
```

### Save as

```bash
playwright-cli screenshot
playwright-cli screenshot e5
playwright-cli screenshot --filename=page.png
playwright-cli pdf --filename=page.pdf
```

### Tabs

```bash
playwright-cli tab-list
playwright-cli tab-new
playwright-cli tab-new https://example.com/page
playwright-cli tab-close
playwright-cli tab-close 2
playwright-cli tab-select 0
```

### Storage

```bash
playwright-cli state-save
playwright-cli state-save auth.json
playwright-cli state-load auth.json

# Cookies
playwright-cli cookie-list
playwright-cli cookie-list --domain=example.com
playwright-cli cookie-get session_id
playwright-cli cookie-set session_id abc123
playwright-cli cookie-set session_id abc123 --domain=example.com --httpOnly --secure
playwright-cli cookie-delete session_id
playwright-cli cookie-clear

# LocalStorage
playwright-cli localstorage-list
playwright-cli localstorage-get theme
playwright-cli localstorage-set theme dark
playwright-cli localstorage-delete theme
playwright-cli localstorage-clear

# SessionStorage
playwright-cli sessionstorage-list
playwright-cli sessionstorage-get step
playwright-cli sessionstorage-set step 3
playwright-cli sessionstorage-delete step
playwright-cli sessionstorage-clear
```

### Network

```bash
playwright-cli route "**/*.jpg" --status=404
playwright-cli route "https://api.example.com/**" --body='{"mock": true}'
playwright-cli route-list
playwright-cli unroute "**/*.jpg"
playwright-cli unroute
```

### DevTools

```bash
playwright-cli console
playwright-cli console warning
playwright-cli requests
playwright-cli request 5
playwright-cli run-code "async page => await page.context().grantPermissions(['geolocation'])"
playwright-cli run-code --filename=script.js
playwright-cli tracing-start
playwright-cli tracing-stop
playwright-cli video-start video.webm
playwright-cli video-chapter "Chapter Title" --description="Details" --duration=2000
playwright-cli video-stop

# annotate each subsequent action (click, type, ...) with a callout naming the action and highlighting the target
playwright-cli video-show-actions --duration=600 --position=top-right
playwright-cli video-hide-actions

# launch the dashboard for UI review / design feedback — user annotates the page, you receive the annotated screenshot, snapshot, and notes
playwright-cli show --annotate

# generate a Playwright locator for an element from its ref or selector
playwright-cli generate-locator e5 --raw

# show a persistent highlight overlay for an element, optionally with a custom style
playwright-cli highlight e5
playwright-cli highlight e5 --style="outline: 3px dashed red"
# hide a single element highlight, or all page highlights when no target is given
playwright-cli highlight e5 --hide
playwright-cli highlight --hide
```

## Raw output

The global `--raw` option strips page status, generated code, and snapshot sections from the output, returning only the result value. Use it to pipe command output into other tools. Commands that don't produce output return nothing.

```bash
playwright-cli --raw eval "JSON.stringify(performance.timing)" | jq '.loadEventEnd - .navigationStart'
playwright-cli --raw eval "JSON.stringify([...document.querySelectorAll('a')].map(a => a.href))" > links.json
playwright-cli --raw snapshot > before.yml
playwright-cli click e5
playwright-cli --raw snapshot > after.yml
diff before.yml after.yml
TOKEN=$(playwright-cli --raw cookie-get session_id)
playwright-cli --raw localstorage-get theme
```

For structured output wrapping every reply as JSON, pass --json
```bash
playwright-cli list --json
```

## Open parameters
```bash
# Use specific browser when creating session
playwright-cli open --browser=chrome
playwright-cli open --browser=firefox
playwright-cli open --browser=webkit
playwright-cli open --browser=msedge

# Use persistent profile (by default profile is in-memory)
playwright-cli open --persistent
# Use persistent profile with custom directory
playwright-cli open --profile=/path/to/profile

# Connect to browser via Playwright Extension
playwright-cli attach --extension=chrome

# Connect to a running Chrome or Edge by channel name
playwright-cli attach --cdp=chrome
playwright-cli attach --cdp=msedge

# Connect to a running browser via CDP endpoint
playwright-cli attach --cdp=http://localhost:9222

# Start with config file
playwright-cli open --config=my-config.json

# Close the browser
playwright-cli close
# Detach from an attached browser (leaves the external browser running)
playwright-cli -s=msedge detach
# Delete user data for the default session
playwright-cli delete-data
```

## URLs with `&` on Windows

On Windows, `cmd.exe` and PowerShell treat `&` as a command separator, so URLs with multiple query parameters get truncated before `playwright-cli` runs. Escape `&` with `^&` in `cmd.exe`, or use `--%` in PowerShell:

```batch
playwright-cli goto "https://example.com/?a=1^&b=2"
```

```powershell
playwright-cli --% goto "https://example.com/?a=1&b=2"
```

## Snapshots

After each command, playwright-cli provides a snapshot of the current browser state.

```bash
> playwright-cli goto https://example.com
### Page
- Page URL: https://example.com/
- Page Title: Example Domain
### Snapshot
[Snapshot](.playwright-cli/page-2026-02-14T19-22-42-679Z.yml)
```

You can also take a snapshot on demand using `playwright-cli snapshot` command. All the options below can be combined as needed.

```bash
# default - save to a file with timestamp-based name
playwright-cli snapshot

# save to file, use when snapshot is a part of the workflow result
playwright-cli snapshot --filename=after-click.yaml

# snapshot an element instead of the whole page
playwright-cli snapshot "#main"

# limit snapshot depth for efficiency, take a partial snapshot afterwards
playwright-cli snapshot --depth=4
playwright-cli snapshot e34

# include each element's bounding box as [box=x,y,width,height]
playwright-cli snapshot --boxes
```

## Targeting elements

By default, use refs from the snapshot to interact with page elements.

```bash
# get snapshot with refs
playwright-cli snapshot

# interact using a ref
playwright-cli click e15
```

You can also use css selectors or Playwright locators.

```bash
# css selector
playwright-cli click "#main > button.submit"

# role locator
playwright-cli click "getByRole('button', { name: 'Submit' })"

# test id
playwright-cli click "getByTestId('submit-button')"
```

## Browser Sessions

```bash
# create new browser session named "mysession" with persistent profile
playwright-cli -s=mysession open example.com --persistent
# same with manually specified profile directory (use when requested explicitly)
playwright-cli -s=mysession open example.com --profile=/path/to/profile
playwright-cli -s=mysession click e6
playwright-cli -s=mysession close  # stop a named browser
playwright-cli -s=mysession delete-data  # delete user data for persistent session

playwright-cli list
# Close all browsers
playwright-cli close-all
# Forcefully kill all browser processes
playwright-cli kill-all
```

## Installation

If global `playwright-cli` command is not available, try a local version via `npx playwright-cli`:

```bash
npx --no-install playwright-cli --version
```

When local version is available, use `npx playwright-cli` in all commands. Otherwise, install `playwright-cli` as a global command:

```bash
npm install -g @playwright/cli@latest
```

## Example: Form submission

```bash
playwright-cli open https://example.com/form
playwright-cli snapshot

playwright-cli fill e1 "user@example.com"
playwright-cli fill e2 "password123"
playwright-cli click e3
playwright-cli snapshot
playwright-cli close
```

## Example: Multi-tab workflow

```bash
playwright-cli open https://example.com
playwright-cli tab-new https://example.com/other
playwright-cli tab-list
playwright-cli tab-select 0
playwright-cli snapshot
playwright-cli close
```

## Example: Debugging with DevTools

```bash
playwright-cli open https://example.com
playwright-cli click e4
playwright-cli fill e7 "test"
playwright-cli console
playwright-cli requests
playwright-cli close
```

```bash
playwright-cli open https://example.com
playwright-cli tracing-start
playwright-cli click e4
playwright-cli fill e7 "test"
playwright-cli tracing-stop
playwright-cli close
```

## Example: Interactive session

Ask the user for UI review or design feedback. The user draws boxes on the live page and types comments; you receive the annotated screenshot, the snapshot of the marked region, and the user's notes. Use this whenever the user asks for "UI review", "design feedback", or to "ask the user what they think / want / mean":

```bash
playwright-cli open https://example.com
playwright-cli show --annotate
```

## Specific tasks

* **Running and Debugging Playwright tests** [references/playwright-tests.md](references/playwright-tests.md)
* **Request mocking** [references/request-mocking.md](references/request-mocking.md)
* **Running Playwright code** [references/running-code.md](references/running-code.md)
* **Browser session management** [references/session-management.md](references/session-management.md)
* **Spec-driven testing (plan / generate / heal)** [references/spec-driven-testing.md](references/spec-driven-testing.md)
* **Storage state (cookies, localStorage)** [references/storage-state.md](references/storage-state.md)
* **Test generation** [references/test-generation.md](references/test-generation.md)
* **Tracing** [references/tracing.md](references/tracing.md)
* **Video recording** [references/video-recording.md](references/video-recording.md)
* **Inspecting element attributes** [references/element-attributes.md](references/element-attributes.md)
* **Deep browser architecture, interaction-graph exploration, RBAC choreography, and optimization experiments** [BROWSER_AUTOMATION_DEEP_DIVE.md](BROWSER_AUTOMATION_DEEP_DIVE.md) — search for `interaction-graph`, `Evidence-first`, or `first genuine Playwright CLI bundle`.
