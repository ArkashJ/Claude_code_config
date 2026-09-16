#!/usr/bin/env bash
# Parallel bulk screenshots against the LIVE playwright-cli session (inherits your login).
# Usage:
#   playwright-cli open            # log in / navigate as needed first
#   pcap.sh urls.txt [out_dir] [concurrency] [full]
#     out_dir     default: shots
#     concurrency default: 6
#     full        pass "full" for full-page captures
#
# run-code runs in a vm sandbox (no fs/require), so we inline the URL list into the snippet.
set -euo pipefail
URLS_FILE="${1:?usage: pcap.sh urls.txt [out] [conc] [full]}"
OUT="${2:-shots}"
CONC="${3:-6}"
FULL="false"; [ "${4:-}" = "full" ] && FULL="true"

URLS_JSON=$(grep -vE '^\s*(#|$)' "$URLS_FILE" | sed 's/[[:space:]]*$//' \
  | node -e 'let a=[];require("readline").createInterface({input:process.stdin}).on("line",l=>a.push(l)).on("close",()=>process.stdout.write(JSON.stringify(a)))')
[ "$URLS_JSON" != "[]" ] || { echo "no URLs in $URLS_FILE" >&2; exit 2; }
mkdir -p "$OUT"

playwright-cli run-code "async page => {
  const urls = ${URLS_JSON};
  const out = ${OUT@Q}, conc = ${CONC}, full = ${FULL};
  const browser = page.context().browser();
  const state = await page.context().storageState();
  const slug = u => u.replace(/^https?:\/\//,'').replace(/[^\w.-]+/g,'_').slice(0,120);
  const failures = [];
  const waitUntilReady = async (pg, url) => {
    const deadline = Date.now() + 30000;
    let previous = '', stable = 0, reason = 'page is blank';
    while (Date.now() < deadline) {
      const state = await pg.evaluate(() => {
        let doc = document;
        const preview = document.querySelector('#storybook-preview-iframe');
        if (preview) {
          try { doc = preview.contentDocument; }
          catch { return { ready: false, signature: '', reason: 'Storybook preview is unavailable' }; }
          if (!doc) return { ready: false, signature: '', reason: 'Storybook preview is not loaded' };
        }
        const root = doc.querySelector('#storybook-root, main, [role=main], #root > *, #__next > *, body');
        if (!root) return { ready: false, signature: '', reason: 'no application or story root' };
        const view = doc.defaultView;
        const style = view && view.getComputedStyle(root);
        const rect = root.getBoundingClientRect();
        const visible = rect.width > 0 && rect.height > 0 && style && style.visibility !== 'hidden' && style.display !== 'none';
        const text = (root.innerText || '').replace(/\s+/g, ' ').trim();
        const waiting = /^(?:loading(?: story)?|preparing story|please wait|starting)[.!…\s]*$/i.test(text);
        return {
          ready: Boolean(visible && text.length > 1 && !waiting),
          signature: text + '|' + root.querySelectorAll('*').length + '|' + Math.round(root.scrollWidth) + 'x' + Math.round(root.scrollHeight),
          reason: !visible ? 'application root is not visible' : text.length <= 1 ? 'application root is blank' : waiting ? 'application root is spinner-only' : '',
        };
      });
      reason = state.reason;
      if (state.ready) {
        stable = state.signature === previous ? stable + 1 : 1;
        if (stable >= 3) return;
      } else {
        stable = 0;
      }
      previous = state.signature;
      await pg.waitForTimeout(250);
    }
    throw new Error('readiness timeout: ' + reason);
  };
  let i = 0, done = 0;
  const worker = async () => {
    const ctx = await browser.newContext({ storageState: state, viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    const pg = await ctx.newPage();
    await pg.addInitScript(() => { const s = document.createElement('style'); s.textContent = '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'; document.addEventListener('DOMContentLoaded', () => document.head.appendChild(s)); });
    while (i < urls.length) {
      const url = urls[i++];
      try {
        await pg.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await waitUntilReady(pg, url);
        await pg.screenshot({ path: out + '/' + slug(url) + '.png', fullPage: full });
      } catch (e) {
        failures.push(url + ' :: ' + e.message);
      }
      done++;
    }
    await ctx.close();
  };
  await Promise.all(Array.from({ length: conc }, worker));
  if (failures.length) throw new Error('capture failed (' + failures.length + '/' + urls.length + '):\\n' + failures.join('\\n'));
  console.log('done: ' + done + ' ready shots -> ' + out + '/');
}"
