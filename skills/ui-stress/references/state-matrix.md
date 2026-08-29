# The state matrix — what to force, and how

Derive states from what the surface **actually accepts**. Every case below is
worth forcing only if the surface can receive it. A matrix padded with
impossible cases wastes the sweep and buries real findings.

## Where states come from

| Source | What it gives you | How to read it |
|---|---|---|
| Network calls | The highest-yield states, on the real page | DevTools/`playwright-cli` request log; or grep for `fetch(`, `useQuery`, `axios`, the API client |
| Props and types | Per-component states | The TS interface, `propTypes`, or the destructured props |
| Stories/fixtures | An existing catalog — **use it, never rebuild it** | `*.stories.*`, `__mocks__`, MSW handlers, seed scripts |
| Route params | Not-found, forbidden, malformed-id | The router config |
| Auth/roles | The permission states | Role definitions, guard components |

## The catalog

Force these when the surface can receive them.

**Collection shape** — `[]` · one item · many (200+) · more than fits on screen ·
one item with every optional field absent. Note that *empty because new* and
*empty because the filter matched nothing* are different states with different
copy; a surface that renders the same thing for both is a finding.

**Async and failure** — first load (no cache) · refetch over existing data ·
slow (3s+) · `500` · `403` · `404` · network offline · malformed JSON · a request
that never resolves. The last one finds spinners with no timeout.

**Permission** — signed out · signed in without the entitlement · read-only role ·
the owner. A control that is hidden but whose route still works is a finding, and
so is one that is shown but fails on click.

**Content** — normal · 4× length · a 60-character unbreakable string
(`aaaa...`, a URL, a hash) · empty string · only whitespace · leading/trailing
spaces · an emoji · RTL and a non-Latin script if the project ships i18n.

**Data edge cases** — `null` and `undefined` in optional fields · a broken image
`src` · a number in the billions · a negative number · zero · a date in 1970 · a
date in 2099 · a float where an integer was assumed.

**Environment** — 320px and 390px · each breakpoint the project actually declares ·
dark mode where supported · 200% browser zoom · `prefers-reduced-motion` ·
keyboard-only traversal of the primary action.

## Engine 1 — Network forcing (highest yield)

Force the real screen into states nobody built. Set the route, then reload, then
probe.

```bash
playwright-cli -s=stress route "**/api/items*" --body='[]' --content-type=application/json
playwright-cli -s=stress route "**/api/items*" --body='{"error":"forbidden"}' --status=403
playwright-cli -s=stress route "**/api/items*" --status=500
playwright-cli -s=stress route "**/api/items*" --body='{"items":' --content-type=application/json   # malformed
playwright-cli -s=stress unroute                                                                     # reset between cells
```

Many rows, slow responses, and never-resolving requests need `run-code`:

```bash
# 200 rows, generated in-page - no fixture file needed
playwright-cli -s=stress run-code "async page => {
  await page.route('**/api/items*', r => r.fulfill({
    contentType: 'application/json',
    body: JSON.stringify(Array.from({length: 200}, (_, i) => ({
      id: i, name: 'Item ' + i, amount: 999999999, updatedAt: '2099-01-01' })))
  }));
}"

# slow, then never-resolving (finds spinners with no timeout)
playwright-cli -s=stress run-code "async page => {
  await page.route('**/api/**', async r => { await new Promise(f => setTimeout(f, 4000)); r.continue(); });
}"
playwright-cli -s=stress run-code "async page => { await page.route('**/api/**', () => {}); }"

# offline
playwright-cli -s=stress run-code "async page => { await page.context().setOffline(true); }"
```

## Engine 2 — Content stress by DOM mutation

Stresses the **real** layout with hostile content, no fixtures required. Apply,
then probe immediately — a reload reverts it.

```bash
# every leaf text node x5
playwright-cli -s=stress run-code "async page => { await page.evaluate(() => {
  document.querySelectorAll('h1,h2,h3,h4,p,span,td,th,li,button,a,label,legend').forEach(el => {
    if (el.children.length === 0 && el.textContent.trim())
      el.textContent = (el.textContent.trim() + ' ').repeat(5).trim();
  }); }); }"

# an unbreakable string in every heading and label
playwright-cli -s=stress run-code "async page => { await page.evaluate(() => {
  const s = 'Wolfeschlegelsteinhausenbergerdorff'.repeat(2);
  document.querySelectorAll('h1,h2,h3,label,button,td').forEach(el => {
    if (el.children.length === 0) el.textContent = s;
  }); }); }"

# break every image
playwright-cli -s=stress run-code "async page => { await page.evaluate(() => {
  document.querySelectorAll('img').forEach(i => { i.src = '/__broken__.png'; i.srcset = ''; });
}); }"

# inflate every number (no dollar sign anywhere - see the note below)
playwright-cli -s=stress run-code "async page => { await page.evaluate(() => {
  document.querySelectorAll('td,span,strong,b').forEach(el => {
    const t = el.textContent.trim();
    if (el.children.length === 0 && t && !/[^\d,.\s-]/.test(t))
      el.textContent = '-9,876,543,210.99';
  }); }); }"
```

> **Shell quoting:** `run-code` snippets are passed as double-quoted shell
> arguments, so a bare `$` or a backtick is expanded by the shell before
> Playwright ever sees it. Write JavaScript here with neither — use string
> concatenation instead of template literals, and anchor regexes with a negated
> character class rather than a trailing `$`.

## Engine 3 — Viewport and theme

```bash
playwright-cli -s=stress resize 320 720
playwright-cli -s=stress resize 390 844
playwright-cli -s=stress resize 1440 900
playwright-cli -s=stress run-code "async page => { await page.emulateMedia({ colorScheme: 'dark' }); }"
playwright-cli -s=stress run-code "async page => { await page.emulateMedia({ reducedMotion: 'reduce' }); }"
```

Zoom to 200% (finds layouts that break on text scaling, distinct from a narrow
viewport):

```bash
playwright-cli -s=stress run-code "async page => { await page.evaluate(() => document.body.style.zoom = '2'); }"
```

## Engine 4 — Keyboard reachability

Cheap and catches what neither the probe nor a screenshot can:

```bash
playwright-cli -s=stress run-code "async page => {
  const seen = [];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab');
    seen.push(await page.evaluate(() => {
      const a = document.activeElement;
      if (!a || a === document.body) return '(lost focus to body)';
      const r = a.getBoundingClientRect();
      const off = r.top < 0 || r.left < 0 || r.bottom > innerHeight || r.right > innerWidth;
      return a.tagName.toLowerCase() + ':' + (a.textContent || a.getAttribute('aria-label') || '')
        .trim().slice(0, 24) + (off ? ' [OFFSCREEN]' : '');
    }));
  }
  return JSON.stringify(seen);
}"
```

Read the sequence for: focus lost to `body` (a trap or a removed element), an
order that does not match the visual order, `[OFFSCREEN]` entries that never
scroll into view, and the primary action never being reached at all.

## Loop shape

```
for each surface:
  for each state:            # engines 1 + 2
    for each viewport:       # 390 first, 1440 only for cells that passed
      apply → reload if needed → probe → record (surface, state, viewport, theme)
  unroute                    # always reset before the next state
```

Probing is free; screenshotting is not. Sweep the whole matrix with the probe,
then screenshot only what it flagged.
