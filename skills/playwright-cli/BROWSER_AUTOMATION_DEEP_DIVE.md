# Playwright CLI and Agent Browser: A Deep Dive

This guide explains how Playwright CLI and Vercel's `agent-browser` observe pages, resolve elements, dispatch input, interact with JavaScript frameworks, and handle DOM, accessibility, frames, canvas, WebGL, and WebGPU.

## The short answer

- You do **not** need to clone either repository for normal use. Install their published CLI packages and let them launch or connect to a browser.
- Neither tool uses WebGL to automate a page. They control the browser through automation protocols and injected JavaScript. A page may independently use WebGL or WebGPU for rendering.
- A normal click is not usually `element.click()`. The tool resolves an element, calculates an on-screen point, scrolls it into view, checks whether something covers it, and asks the browser to dispatch mouse input.
- React, Vue, Svelte, and similar component abstractions mostly disappear at runtime. Browser automation ultimately interacts with DOM nodes, accessibility nodes, frames, and pixel coordinates.
- Playwright CLI and `agent-browser` are control systems, not autonomous agents. An LLM can drive the loop, but the tools themselves execute deterministic commands.
- Playwright CLI offers strong cross-browser behavior and actionability waiting. Current Vercel `agent-browser` is a fast Rust CLI and daemon that talks directly to Chrome through CDP.

The fundamental loop is:

```text
┌─────────────────┐
│ Observe the page│
│ snapshot/image  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Decide what to do│  ← human, script, or LLM
│ "click Login"   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Execute command │
│ click e17       │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Browser changes │
│ DOM/navigation  │
└────────┬────────┘
         │
         └──────────────> observe again
```

The sophistication lies in translating “Login” into the correct browser object and performing the interaction reliably.

## 1. What actually exists inside a browser

A browser holds several related—but very different—representations of a page.

```text
                         HTML bytes
                             │
                             v
                       ┌──────────┐
 JavaScript mutations ─>│   DOM    │<─ React/Vue/Svelte rendering
                       └────┬─────┘
                            │
             CSS ───────────┼─────────────┐
                            │             │
                            v             v
                    Accessibility     CSSOM/styles
                         tree              │
                            │              v
                            │         Layout boxes
                            │              │
                            │              v
                            │        Paint/compositing
                            │              │
                            v              v
                       Semantic view    Pixels
```

These representations answer different questions:

| Representation | It tells automation… | It does not reliably tell automation… |
|---|---|---|
| DOM | Elements, attributes, text, hierarchy | Actual visibility, overlap, final pixels |
| Accessibility tree | Roles, names, states, relationships | Precise colors, layout, canvas contents |
| Layout boxes | Coordinates and dimensions | Semantic meaning |
| Screenshot | What was rendered visually | Which DOM element owns a pixel |
| JavaScript runtime | Framework state and arbitrary objects | Whether an interaction resembles user input |
| Network | Requests, responses, redirects | Which visual element caused them |

A snapshot is therefore not “the page.” It is a deliberately compressed representation of the page.

For example:

```html
<div class="wrapper">
  <span class="icon"></span>
  <button aria-label="Delete invoice">
    <svg>...</svg>
  </button>
</div>
```

A semantic snapshot may reduce that to:

```yaml
- button "Delete invoice" [ref=e14]
```

The wrapper and SVG are irrelevant to the interaction, so they may disappear from the snapshot. This compression is why accessibility-oriented snapshots are effective for agents: the LLM sees “button Delete invoice,” rather than hundreds of tokens of SVG paths and utility classes.

## 2. Do you need to clone the repositories?

No.

### Normal usage

For Playwright CLI:

```bash
npm install -g @playwright/cli@latest
playwright-cli open https://example.com
```

For Vercel's `agent-browser`:

```bash
npm install -g agent-browser
agent-browser install
agent-browser open https://example.com
```

`agent-browser install` downloads or finds a compatible browser. Its current README also documents Homebrew and Cargo installation. See the [official agent-browser repository](https://github.com/vercel-labs/agent-browser).

### Clone only when you want to…

- modify the tools;
- contribute a patch;
- debug their internal implementation;
- build an unreleased commit;
- study the source offline.

There is an important distinction:

```text
microsoft/playwright-cli
        │
        │ thin CLI entry point
        v
microsoft/playwright / playwright-core
        │
        v
most of the actual browser machinery
```

The published Playwright CLI entry point is extremely small and imports its implementation from `playwright-core`. Cloning only `microsoft/playwright-cli` will not show most of the interesting code. See the [Playwright CLI entry point](https://github.com/microsoft/playwright-cli/blob/main/playwright-cli.js).

Current `agent-browser`, by contrast, contains its native Rust implementation in its own repository. Older articles describing it as a Node/Playwright wrapper describe an earlier architecture.

## 3. Playwright CLI architecture

A useful high-level model is:

```text
Shell
  │
  │ playwright-cli click e17
  v
@playwright/cli
  │
  │ delegates
  v
playwright-core CLI/session machinery
  │
  ├── injected utility JavaScript inside page
  │       ├── selectors
  │       ├── ARIA computation
  │       ├── visibility
  │       └── hit-target checks
  │
  ├── Chromium protocol adapter
  ├── Firefox protocol adapter
  └── WebKit protocol adapter
          │
          v
      Browser process
          │
          v
      page/frame/DOM
```

Playwright is not fundamentally a Chrome-only CDP wrapper. It has browser-specific backends for Chromium, Firefox, and WebKit. Chromium ultimately uses CDP commands such as `Input.dispatchMouseEvent`; Firefox and WebKit use their respective Playwright-supported protocols. See the [Chromium input implementation](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/chromium/crInput.ts) and [Firefox input implementation](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/firefox/ffInput.ts).

Playwright CLI sessions let multiple shell commands continue interacting with the same browser state. Persistent sessions may also retain cookies and storage. See the [Playwright CLI README](https://github.com/microsoft/playwright-cli).

### How its snapshot works

A subtle but important point: Playwright's ref snapshot is not merely a dump of Chrome's native accessibility tree.

Playwright injects utility JavaScript into the page and computes a cross-browser ARIA-oriented representation itself:

```text
DOM and open shadow roots
          │
          v
Playwright injected script
          │
          ├── compute role
          ├── compute accessible name
          ├── compute visible/state properties
          ├── traverse text and ARIA ownership
          └── assign eN references
          │
          v
Semantic snapshot
```

The implementation walks DOM elements, text nodes, slots, open shadow roots, and ARIA-owned elements. It calculates roles, accessible names, visibility, state, boxes, and pointer-event properties. See the [Playwright ARIA snapshot implementation](https://github.com/microsoft/playwright/blob/main/packages/injected/src/ariaSnapshot.ts).

Conceptually, it constructs maps similar to:

```text
e7  ─────────> actual HTMLButtonElement
e8  ─────────> actual HTMLInputElement
e9  ─────────> actual HTMLAnchorElement
```

The generated output might be:

```yaml
- textbox "Email" [ref=e7]
- textbox "Password" [ref=e8]
- button "Sign in" [ref=e9]
```

When you run:

```bash
playwright-cli click e9
```

Playwright's internal `aria-ref` selector engine consults the most recent snapshot mapping and retrieves the corresponding connected DOM element. See the [injected selector implementation](https://github.com/microsoft/playwright/blob/main/packages/injected/src/injectedScript.ts).

### Are Playwright refs permanent?

No. Treat them as short-lived handles for an observe/action loop.

```text
snapshot #1                         snapshot #2
e9 ──> old button                   e14 ──> replacement button
         │
         └── React replaces it ──> old node disconnected
```

If a framework replaces the DOM node, the old reference may stop working. Taking another snapshot also changes the active snapshot context.

This is why:

- refs are excellent for interactive agent loops;
- semantic locators are better for durable tests.

A durable test would prefer:

```ts
page.getByRole('button', { name: 'Sign in' }).click();
```

Playwright locators resolve the current DOM again for every action, rather than retaining one stale element object. See the [Playwright locator documentation](https://playwright.dev/docs/locators).

## 4. What happens during a Playwright click?

Consider:

```bash
playwright-cli click e9
```

The approximate pipeline is:

```text
1. Resolve e9 to the current DOM element
                  │
                  v
2. Ensure exactly one target was found
                  │
                  v
3. Wait for actionability
   ├── visible?
   ├── stable?
   ├── enabled?
   └── receives pointer events?
                  │
                  v
4. Scroll target into view
                  │
                  v
5. Calculate a clickable point
                  │
                  v
6. Verify browser hit testing reaches target
                  │
                  v
7. Dispatch browser mouse input
   ├── mouseMoved
   ├── mousePressed
   └── mouseReleased
                  │
                  v
8. Browser generates DOM events/default behavior
                  │
                  v
9. Wait for resulting navigation/action as needed
```

Playwright calls its preconditions “actionability checks.” A normal click waits for the target to be visible, stable, enabled, and able to receive events. See the [Playwright actionability documentation](https://playwright.dev/docs/actionability).

The implementation retries pointer actions and even tries alternative scroll alignments when sticky headers or overlays interfere. See the [Playwright DOM action implementation](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/dom.ts).

### This is different from `HTMLElement.click()`

Direct JavaScript:

```js
document.querySelector('button').click()
```

does not need a physical location. It can activate an element that is visually covered or outside the viewport.

Browser input:

```text
protocol mouse coordinates
        │
        v
browser hit testing
        │
        ├── overlay gets event → click fails/wrong target
        └── button gets event  → interaction proceeds
```

Protocol-based clicking is much closer to a user interaction because it exercises layout, hit testing, focus, pointer events, and event propagation. It is still automation—not an actual USB mouse moving through the operating system.

Playwright documents this distinction in its [input documentation](https://playwright.dev/docs/input).

## 5. What happens during `fill`?

Filling an input is more complicated than it appears.

A naïve implementation would be:

```js
input.value = "hello"
```

But that alone may not notify React, validation code, masks, analytics, or other event listeners.

Playwright uses a hybrid approach:

```text
Resolve input
    │
    v
Check editable and appropriate input type
    │
    ├── special controls such as date/color
    │      └── set value and dispatch input/change
    │
    └── ordinary text input
           ├── focus/select existing content
           └── ask browser keyboard layer to insert text
```

The browser backend can use commands such as `Input.insertText` on Chromium. The resulting input events give application code an opportunity to update its state.

This matters for controlled React inputs:

```text
Browser inserts text
       │
       v
native input event
       │
       v
React handler calls setState()
       │
       v
React renders new value
       │
       v
DOM and component state agree
```

If you only assign `input.value`, React's state may remain unchanged and overwrite your direct mutation during the next render.

## 6. Current `agent-browser` architecture

The current Vercel implementation is structurally different:

```text
Shell
  │
  │ agent-browser click @e9
  v
Native Rust CLI
  │
  │ IPC
  v
Persistent Rust daemon
  │
  │ direct Chrome DevTools Protocol
  v
Chrome / Chromium
  │
  ├── Accessibility domain
  ├── DOM domain
  ├── Runtime domain
  ├── Input domain
  └── Network domain
          │
          v
        page
```

Its official architecture describes the Rust CLI, Rust daemon, and direct CDP connection. Playwright and Node are not required by the daemon itself. See the [agent-browser architecture](https://github.com/vercel-labs/agent-browser#architecture).

Why a daemon?

```text
command 1: open page  ─┐
command 2: snapshot   ─┼─> same daemon/browser/session
command 3: click      ─┤
command 4: screenshot─┘
```

Launching Chrome for every command would be slow and would lose cookies, page state, open tabs, and JavaScript state.

### How its snapshot works

Unlike Playwright's injected cross-browser ARIA computation, `agent-browser` asks Chrome for the native accessibility tree:

```text
Chrome DOM
    │
    v
Chrome accessibility computation
    │
    v
CDP Accessibility.getFullAXTree
    │
    v
agent-browser filters and annotates nodes
    │
    ├── interactive/content roles
    ├── role
    ├── accessible name
    ├── backendDOMNodeId
    ├── frame
    └── nth/identity information
    │
    v
snapshot containing @eN refs
```

The CDP `Accessibility.getFullAXTree` operation returns accessibility nodes containing roles, names, state, frame information, and links to backend DOM node IDs. See the [CDP Accessibility domain](https://chromedevtools.github.io/devtools-protocol/tot/Accessibility/).

The Rust snapshot implementation supplements the accessibility tree with some cursor-interactive DOM elements, then assigns refs to useful nodes. See the [agent-browser snapshot implementation](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/native/snapshot.rs).

That supplement helps with poorly built pages such as:

```html
<div onclick="save()" style="cursor: pointer">Save</div>
```

But the proper solution remains:

```html
<button type="button">Save</button>
```

Correct semantics improve automation, keyboard access, screen readers, focus behavior, and maintainability simultaneously.

### How an agent-browser ref works

Its ref record is approximately:

```text
@e9
 ├── backendDOMNodeId: 527
 ├── role: button
 ├── name: Sign in
 ├── nth: 0
 └── frame: ...
```

On click:

```text
Try backendDOMNodeId 527
          │
          ├── still valid → fast path
          │
          └── stale
                │
                v
       query accessibility tree again
                │
                v
       role + name + nth fallback
```

This makes refs resilient to some DOM replacement, although a new snapshot is still the safest response after a significant page update. See the native [agent-browser element resolution](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/native/element.rs).

## 7. What happens during an agent-browser click?

Its native click path is lower-level than Playwright's full locator actionability system:

```text
Resolve @e9
    │
    v
DOM.scrollIntoViewIfNeeded
    │
    v
DOM.getBoxModel
    │
    v
Find center of content quad
    │
    v
Check for an intercepting/covering element
    │
    v
Input.dispatchMouseEvent
    ├── mousePressed
    └── mouseReleased
```

The DOM domain provides node resolution, scrolling, and box-model operations. See the [CDP DOM domain](https://chromedevtools.github.io/devtools-protocol/tot/DOM/).

The Input domain dispatches browser mouse events at coordinates. See the [CDP Input domain](https://chromedevtools.github.io/devtools-protocol/tot/Input/).

The exact Rust interaction implementation uses those operations and also handles browser dialogs that can open between mouse-down and mouse-up. See the [agent-browser interaction implementation](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/native/interaction.rs).

The practical difference is:

```text
Playwright:
  richer actionability + auto-waiting + cross-browser abstraction

agent-browser:
  direct, fast CDP element resolution + scrolling + box/hit testing
```

Do not assume every Playwright auto-wait guarantee exists identically in `agent-browser`. With highly animated interfaces, you may need explicit waiting and a fresh snapshot.

Its fill operation is also hybrid:

```text
resolve JS object
      │
      v
focus element
      │
      v
select and clear
      │
      v
dispatch input event
      │
      v
CDP Input.insertText
```

`Runtime.callFunctionOn` is the CDP mechanism that executes a function against a remote JavaScript object. See the [CDP Runtime domain](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/).

## 8. How they “click through components”

The browser does not know what your application considers a component.

Given React:

```jsx
function BuyButton() {
  return (
    <div className="toolbar">
      <Button>
        <span>Buy now</span>
      </Button>
    </div>
  );
}
```

The browser sees something like:

```html
<div class="toolbar">
  <button class="...">
    <span>Buy now</span>
  </button>
</div>
```

The component abstraction has compiled or rendered into DOM nodes.

Automation therefore works like this:

```text
"button Buy now"
       │
       v
accessible role/name lookup
       │
       v
HTMLButtonElement
       │
       v
browser input at button coordinates
       │
       v
native DOM event
       │
       v
React delegated event system
       │
       v
component onClick handler
       │
       v
setState / mutation / request
       │
       v
React commit updates DOM
```

A more detailed event path is:

```text
Input.dispatchMouseEvent
          │
          v
Browser hit-tests coordinates
          │
          v
pointerdown / mousedown
          │
          v
focus may change
          │
          v
pointerup / mouseup
          │
          v
click
          │
          v
capture phase:
window → document → ancestors → target
          │
          v
target listener
          │
          v
bubble phase:
target → ancestors → document
          │
          v
React/Vue/application handlers
          │
          v
default action if not prevented
  ├── anchor navigation
  ├── form submission
  ├── checkbox toggle
  └── button activation
```

### Fragments

A React fragment has no DOM node:

```jsx
<>
  <h2>Title</h2>
  <button>Save</button>
</>
```

You cannot click “the fragment.” You click the button.

### Portals

A modal may be logically owned by one component but rendered under `<body>`:

```text
React component tree                  DOM tree

Page                                  body
└── Dialog component                  ├── #app
                                      └── #portal-root
                                          └── dialog
```

Automation sees the physical DOM/accessibility tree. Portals are usually easy to automate because the dialog is still normal DOM.

### Virtualized lists

A list may have 10,000 records but render only 20 DOM rows:

```text
application data: 10,000 items
DOM right now:          20 items
snapshot sees:          20 items
```

To reach item 8,450, scroll until the virtualization library renders it. There is nothing to locate before that point.

### Hydration

Server-rendered HTML may be visible before JavaScript handlers are attached:

```text
HTML appears
    │
    ├── user/automation clicks too soon
    │
    v
framework hydrates and installs handlers
```

Playwright's visibility checks do not inherently prove that application hydration is complete. A durable app-specific readiness signal is often better than arbitrary sleeps.

### Open shadow DOM

Playwright locators generally pierce open shadow roots automatically. XPath does not, and closed shadow roots are not generally supported as normal locator boundaries. See the [Playwright shadow DOM documentation](https://playwright.dev/docs/locators#locate-in-shadow-dom).

```text
<my-widget>
  #shadow-root (open)
      <button>Save</button>
```

A semantic role locator can usually find that button.

Closed shadow roots intentionally hide their internal DOM:

```text
<my-widget>
  #shadow-root (closed)
      inaccessible internal nodes
```

The robust design is to expose an accessible host interaction or public application hook—not to depend on private component internals.

### Iframes

Each frame has its own document and JavaScript context:

```text
top document
   │
   ├── normal DOM
   │
   └── iframe
          │
          └── separate document
```

Browser automation has privileged protocol access that is not limited exactly like ordinary page JavaScript, but it still must identify and operate in the appropriate frame. Cross-origin out-of-process frames may require separate CDP sessions.

## 9. Do they use WebGL?

Not for ordinary automation.

```text
Playwright / agent-browser
     │
     ├── DOM
     ├── accessibility
     ├── layout
     ├── browser input
     └── JavaScript runtime

Page being automated
     │
     └── may use WebGL/WebGPU to render a canvas
```

WebGL is a JavaScript graphics API for drawing into a canvas using a GPU-oriented graphics pipeline. See the [Khronos WebGL specification](https://registry.khronos.org/webgl/specs/latest/1.0/).

A page may contain:

```html
<canvas id="scene"></canvas>
```

Inside JavaScript memory it might have:

```text
Three.js scene
 ├── camera
 ├── cube
 ├── light
 └── mesh
```

But the DOM contains only:

```text
HTMLCanvasElement
```

The cube is not a DOM node. It has no normal accessibility node, CSS selector, or element reference.

A snapshot might show:

```yaml
- canvas "3D product preview" [ref=e22]
```

It will not show:

```yaml
- mesh "red shoe"
- mesh "blue shoelace"
```

Those objects exist in the application's scene graph and GPU buffers, not the DOM.

### Clicking an object inside WebGL

Automation can only send a coordinate to the canvas:

```text
automation clicks client coordinate (640, 380)
                 │
                 v
browser delivers pointer event to canvas
                 │
                 v
application converts CSS coordinate to canvas coordinate
                 │
                 v
application creates camera ray
                 │
                 v
raycaster intersects 3D scene
                 │
                 v
application decides which mesh was clicked
```

Typical coordinate conversion resembles:

```text
canvasX =
  (clientX - canvasRect.left)
  * canvas.width / canvasRect.width

canvasY =
  (clientY - canvasRect.top)
  * canvas.height / canvasRect.height

normalizedX =  2 * canvasX / canvas.width  - 1
normalizedY =  1 - 2 * canvasY / canvas.height
```

Automation does not normally perform the raycast. The page does.

To automate individual canvas objects, use one of these approaches:

1. Click known coordinates.
2. Use screenshots plus computer vision to estimate coordinates.
3. Ask the application for object coordinates through `evaluate`.
4. Add an accessible DOM overlay or controls.
5. Add a stable testing hook that exposes scene objects.
6. Test the scene's state directly instead of pretending every assertion requires a physical click.

The accessibility/DOM overlay is usually the best product design because it also helps keyboard and assistive-technology users.

### WebGPU

WebGPU is newer and different from WebGL. Current `agent-browser` exposes a `--webgpu` option for pages that need WebGPU, particularly in headless environments where GPU or software Vulkan configuration matters. That is browser-rendering support, not the mechanism used to locate buttons or dispatch clicks.

Headless rendering may use hardware acceleration or software implementations such as SwiftShader depending on the browser, flags, operating system, and environment.

## 10. Which operations actually manipulate the DOM?

“Browser automation manipulates the DOM” is only partially accurate.

| Operation | Main mechanism | Direct DOM mutation? |
|---|---|---|
| Click | Browser protocol mouse input | Usually no |
| Hover | Browser protocol mouse movement | No |
| Key press | Browser protocol keyboard input | Usually no |
| Fill | Injected JS plus browser text input | Sometimes |
| Select option | DOM/control manipulation plus events | Often |
| Drag | Pointer input/data-transfer support | Usually indirect |
| `eval`/`evaluate` | Execute page JavaScript | Yes, if your code does |
| Cookie changes | Browser storage APIs/protocol | No |
| Network mocking | Protocol request interception | No |
| Screenshot | Browser compositor capture | No |
| Snapshot | DOM/ARIA/AX inspection | No |
| Navigation | Browser navigation command | Replaces document |
| Upload files | Input/file chooser protocol support | Changes control state |

The most honest mental model is:

```text
automation can:
  inspect browser state
  inject browser-level input
  execute privileged commands
  execute page JavaScript
  wait for observable conditions

the application/browser then:
  dispatches events
  changes state
  mutates DOM
  paints new pixels
```

## 11. Playwright CLI versus agent-browser

| Concern | Playwright CLI | Current agent-browser |
|---|---|---|
| Core implementation | Node entry point over Playwright Core | Native Rust CLI and daemon |
| Primary connection | Browser-specific Playwright protocols | Direct CDP for Chrome |
| Browsers | Chromium, Firefox, WebKit | Primarily Chrome/Chromium; other documented engines vary |
| Snapshot source | Injected Playwright ARIA computation | Chrome native AX tree plus DOM supplementation |
| Ref syntax | `e17` | `@e17` |
| Ref resolution | Last snapshot maps ref to connected DOM element | Backend node ID with semantic stale fallback |
| Click reliability | Strong actionability and retry system | Direct scroll, box, hit-test, protocol input |
| Durable tests | Excellent Playwright Test ecosystem | Better suited to agent/CLI interaction |
| Traces/debugging | Mature tracing and test tooling | Agent-oriented inspection and CDP tooling |
| WebGL requirement | None | None |
| Best fit | Cross-browser QA and durable tests | Fast Chrome-first agent automation |

Practical recommendation:

```text
Exploration and agent navigation
    ├── either tool works
    └── agent-browser is attractive for fast Chrome/CDP loops

Cross-browser application testing
    └── Playwright

Repeatable CI regression test
    └── Playwright Test

Canvas/WebGL application
    ├── either can click coordinates
    └── neither magically sees internal scene objects
```

For important workflows, do not preserve a 200-command CLI transcript as your final test suite. Explore interactively, then translate the stable outcome into a small Playwright test using role locators and assertions.

## 12. Why “I can see it, but it can't click it” happens

Use this decision tree:

```text
Can snapshot find the target?
│
├── No
│   ├── Is it inside canvas/WebGL?
│   ├── Is it in an iframe?
│   ├── Is it in a closed shadow root?
│   ├── Is it virtualized and not currently rendered?
│   ├── Is it visually drawn with CSS but not semantic DOM?
│   └── Is the accessible role/name missing?
│
└── Yes
    │
    ├── Is the ref stale after a rerender?
    │       └── resnapshot
    │
    ├── Are multiple elements semantically identical?
    │       └── add context or durable unique naming
    │
    ├── Is an overlay intercepting the center point?
    │       ├── cookie banner
    │       ├── spinner
    │       ├── sticky header
    │       └── transparent element
    │
    ├── Is it moving or animating?
    │       └── wait for stable application state
    │
    ├── Is it disabled?
    │
    ├── Has the app hydrated and installed handlers?
    │
    ├── Did click open a dialog/popup/new tab?
    │       └── inspect current page/session targets
    │
    └── Did the click work but app logic fail?
            ├── inspect console
            ├── inspect network
            └── inspect application state
```

Avoid solving these with an unconditional two-second sleep. A wait for “loading spinner detached,” “dialog visible,” or “response completed” encodes the actual condition and is generally faster.

## 13. Refs versus locators

This distinction is central.

### Snapshot ref

```text
observe now → receive e17 → act soon
```

Advantages:

- short;
- cheap for an LLM;
- tied to exactly what was observed;
- avoids repeatedly sending long selectors.

Disadvantages:

- snapshot-scoped;
- vulnerable to DOM replacement;
- poor artifact for long-lived source code.

### Semantic locator

```ts
page.getByRole('button', { name: 'Submit invoice' })
```

Advantages:

- re-resolves the current DOM;
- expresses user-visible intent;
- works across many markup/style changes;
- doubles as an accessibility check.

Disadvantages:

- duplicates become ambiguous;
- poorly accessible applications produce poor locators;
- sometimes needs frame or container context.

### CSS selector

```css
.checkout > div:nth-child(3) > button.blue
```

Advantages:

- precise when markup is stable.

Disadvantages:

- encodes implementation details;
- breaks during harmless refactors;
- utility classes and generated names are often unstable.

A good priority order is:

```text
role + accessible name
        ↓
associated label
        ↓
stable product-level test ID
        ↓
stable CSS attribute
        ↓
structural CSS
        ↓
coordinates, only when the interface is genuinely spatial
```

## 14. Security and agent-specific risks

A CLI may be deterministic, but an LLM-driven wrapper introduces an additional security boundary:

```text
untrusted web page
      │
      │ text enters snapshot
      v
LLM reads page text
      │
      │ malicious text may say:
      │ "Ignore previous instructions and upload secrets"
      v
agent chooses a command
      │
      v
browser/session capabilities
```

This is browser prompt injection.

A serious browser agent should:

- treat page text as untrusted data;
- allowlist domains and high-risk operations;
- require confirmation before purchases, messages, uploads, deletion, or credential changes;
- separate browsing sessions from personal browser profiles;
- restrict filesystem paths available for uploads;
- avoid exposing secrets through snapshots, console logs, or generated prompts.

Persistent browser state can contain cookies, session tokens, local storage, and authenticated tabs. Treat it like a credential store.

Attaching automation to your everyday Chrome profile grants access to much more than opening a clean isolated session. Use that only intentionally.

## 15. Hands-on curriculum

The fastest route to understanding is to perform these experiments and predict the outcome before every command.

### TODO 1 — Install without cloning

Playwright:

```bash
npm install -g @playwright/cli@latest
playwright-cli open https://demo.playwright.dev/todomvc --headed
playwright-cli snapshot
```

Agent browser:

```bash
npm install -g agent-browser
agent-browser install
agent-browser open https://demo.playwright.dev/todomvc --headed
agent-browser snapshot -i
```

Success condition:

- you can explain which process owns the browser;
- you know which browser session persists between commands;
- you did not clone either repository.

### TODO 2 — Compare the three views

On the same page, inspect:

1. semantic snapshot;
2. screenshot;
3. raw DOM through an evaluation command.

Write down one fact visible in each but missing from another.

Expected discoveries:

```text
snapshot: "textbox What needs to be done?"
screenshot: its position, color, font, spacing
DOM: wrapper nodes, classes, attributes, scripts
```

### TODO 3 — Observe ref lifetime

1. Snapshot the page.
2. Record the input and button refs.
3. Perform an action that causes a rerender.
4. Try the old ref.
5. Snapshot again.
6. Compare refs and DOM identity.

Success condition: you can explain the difference between a ref, a DOM node, and a semantic locator.

### TODO 4 — Test accessible naming

Build or visit examples of:

```html
<button>Save</button>
<button aria-label="Save invoice"><svg>...</svg></button>
<div onclick="save()">Save</div>
```

Compare their snapshots.

Then change the last one to:

```html
<button type="button">Save</button>
```

Success condition: you understand why semantic HTML is an automation feature, not merely a screen-reader concern.

### TODO 5 — Record the event sequence

Install temporary listeners for:

```text
pointerdown
mousedown
focus
pointerup
mouseup
click
input
change
submit
```

Click and fill controls, then inspect the console.

Repeat using:

- protocol click;
- `HTMLElement.click()`;
- direct `input.value = ...`;
- normal fill.

Success condition: you can state which operations performed hit testing and which merely executed JavaScript.

### TODO 6 — Break actionability deliberately

Create:

```html
<button id="target">Pay</button>
<div id="overlay"></div>
```

Position the overlay over the button. Try clicking.

Then test:

- `pointer-events: none`;
- a moving animation;
- a disabled button;
- a transparent but intercepting overlay;
- a sticky header covering the target after scroll.

Compare Playwright's behavior with agent-browser's error and retry behavior.

### TODO 7 — Frames and shadow roots

Build:

```text
top page
├── ordinary button
├── same-origin iframe
├── cross-origin iframe
└── custom element
    └── open shadow root
        └── button
```

Find and click each target.

Then switch the shadow root to closed mode and observe the loss of direct locator access.

### TODO 8 — Canvas/WebGL

Use a page containing a WebGL canvas.

1. Take a snapshot.
2. Take a screenshot.
3. Compare what each representation knows.
4. Inspect the canvas bounding box.
5. Click its center.
6. Try locating an internal 3D object semantically.
7. Expose the object through a DOM overlay or testing hook.

Success condition: you can explain why the rendered cube is visible but not a DOM element.

### TODO 9 — Inspect side effects

For one button click, record:

```text
before snapshot
      ↓
click
      ↓
console messages
      ↓
network request/response
      ↓
after snapshot
      ↓
screenshot
```

Success condition: you can determine whether a failure came from element resolution, input dispatch, frontend state, network behavior, or rendering.

### TODO 10 — Convert exploration into a durable test

After discovering a workflow with CLI refs, write a Playwright test using semantic locators:

```ts
import { test, expect } from '@playwright/test';

test('adds a todo', async ({ page }) => {
  await page.goto('https://demo.playwright.dev/todomvc');

  await page
    .getByPlaceholder('What needs to be done?')
    .fill('Understand browser automation');

  await page.keyboard.press('Enter');

  await expect(
    page.getByText('Understand browser automation')
  ).toBeVisible();
});
```

The CLI refs helped you explore. The final test records intent and observable outcome.

## 16. Why Playwright CLI can feel substantially better than agent-browser

The claim that a direct-CDP Rust tool must feel faster or more reliable because it has fewer layers is too simple. The expensive and failure-prone portions of browser automation are rarely argument parsing or IPC alone. They are usually:

```text
target discovery
      +
DOM churn and rerenders
      +
actionability and hit testing
      +
application/network completion
      +
observing the resulting page
```

Playwright has invested heavily in those layers. A technically plausible explanation for a better Playwright experience is:

```text
Playwright CLI
  ├── cross-browser semantic snapshot produced by Playwright
  ├── live Locator abstraction
  ├── strict target resolution
  ├── visibility/stability/enabled checks
  ├── scroll and frame-aware coordinate handling
  ├── hit-target interception
  ├── retry when DOM nodes detach or move
  ├── action-triggered network/navigation settling
  └── mature traces and diagnostics

agent-browser
  ├── direct Chrome AX/DOM/CDP access
  ├── backend-node fast path
  ├── scroll and box-model lookup
  ├── center-point input dispatch
  └── a smaller, lower-level reliability envelope
```

Fewer architectural layers can reduce overhead. They do not automatically solve animation, overlays, hydration, stale nodes, cross-frame transforms, duplicated accessible names, network completion, or a framework replacing the target midway through an action.

Playwright's advantage is therefore less “Node versus Rust” and more:

```text
How much browser ambiguity is handled before and after Input.dispatchMouseEvent?
```

The answer is: considerably more than the high-level CLI command suggests.

## 17. Playwright CLI's exact control plane

The earlier Playwright diagram omitted an important part: current Playwright CLI has both a short-lived command client and a persistent session daemon.

### 17.1 Process ownership

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Shell / coding agent                                                  │
│                                                                       │
│ $ playwright-cli -s=shop click e17                                    │
└─────────────────────────────┬─────────────────────────────────────────┘
                              │ starts a short-lived Node CLI process
                              v
┌───────────────────────────────────────────────────────────────────────┐
│ CLI client                                                            │
│                                                                       │
│ 1. parse args                                                         │
│ 2. identify workspace + session                                       │
│ 3. load session registry entry                                        │
│ 4. connect to Unix socket / Windows named pipe                        │
│ 5. send structured `run` request                                      │
│ 6. print response and exit                                            │
└─────────────────────────────┬─────────────────────────────────────────┘
                              │ local IPC
                              v
┌───────────────────────────────────────────────────────────────────────┐
│ Persistent Playwright CLI daemon                                      │
│                                                                       │
│ owns:                                                                 │
│  - Browser / BrowserContext                                           │
│  - tabs and current tab                                               │
│  - cookies, storage, routes                                           │
│  - console/network event history                                      │
│  - last ARIA snapshot ref mapping                                     │
│  - trace/video state                                                   │
│                                                                       │
│ translates CLI command -> backend tool -> Playwright API              │
└─────────────────────────────┬─────────────────────────────────────────┘
                              │ Playwright browser protocol
                              v
┌───────────────────────────────────────────────────────────────────────┐
│ Chromium / Firefox / WebKit                                           │
│                                                                       │
│ renderer processes, frames, DOM, layout, input, network, compositor   │
└───────────────────────────────────────────────────────────────────────┘
```

The CLI client implementation loads the registry, resolves a session name, and routes normal commands to `Session.run()`. `Session.run()` creates a local socket connection, sends one `run` request, receives one response, and closes that connection. See the current [CLI client program](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/cli-client/program.ts) and [session client](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/cli-client/session.ts).

This means Playwright CLI already avoids the largest obvious performance mistake:

```text
BAD hypothetical architecture

click command
  -> start Chrome
  -> create profile
  -> navigate again
  -> click
  -> close Chrome
```

Instead:

```text
ACTUAL warm-session architecture

open once
  -> daemon owns browser for entire session

click/fill/snapshot commands
  -> start small CLI client
  -> local socket request
  -> reuse existing daemon/browser/page
```

### 17.2 Cold `open` flow

```text
playwright-cli -s=shop open https://shop.example --headed
       │
       v
parse global and open flags
       │
       v
load workspace-scoped session registry
       │
       v
does session "shop" already exist?
       │
       ├── yes -> stop old daemon cleanly
       │
       └── no
       │
       v
spawn detached Node process running cliDaemon.js
       │
       v
daemon launches or attaches to browser
       │
       v
create BrowserContext and BrowserBackend
       │
       v
start local socket/named-pipe server
       │
       v
write session metadata file
       │
       v
print "Daemon listening on"
       │
       v
client sends implicit `goto`
       │
       v
navigate + capture page response/snapshot
```

The client deliberately waits for the daemon's ready message before issuing the implicit navigation. If the post-spawn navigation fails, it stops the new daemon so it does not leave an orphaned browser. This lifecycle is implemented in the [CLI client session source](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/cli-client/session.ts).

### 17.3 Warm command flow

For:

```bash
playwright-cli -s=shop click e17
```

the actual control flow is approximately:

```text
new CLI process
  │
  ├─ parse: command=click, target=e17
  ├─ resolve session=shop
  ├─ load socket path from session metadata
  └─ net.createConnection(socketPath)
          │
          v
send {
  id: 1,
  method: "run",
  params: {
    args: { _: ["click", "e17"] },
    cwd: "/current/workspace",
    raw: false,
    json: false
  }
}
          │
          v
daemon receives message
  │
  ├─ parse CLI command into backend tool name
  │      click -> browser_click
  ├─ map flags/positionals into tool parameters
  ├─ validate parameters using Zod schema
  └─ BrowserBackend.callTool("browser_click", params)
          │
          v
tool performs action and builds Response
          │
          v
daemon sends formatted response
          │
          v
CLI client closes socket, prints response, exits
```

The daemon creates one `BrowserBackend` around the persistent browser context. The backend validates a tool's parameters, creates a response accumulator, runs the tool, drains asynchronous errors, serializes page state, and returns the result. See [daemon.ts](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/cli-daemon/daemon.ts) and [browserBackend.ts](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/backend/browserBackend.ts).

### 17.4 The CLI and MCP share a backend shape

The internal flow is effectively:

```text
CLI syntax
    │
    v
CLI command parser
    │
    v
browser_click / browser_snapshot / browser_fill / ...
    │
    v
shared BrowserBackend tool implementation
    │
    v
Playwright Locator/Page APIs
```

This is why source files and configuration still contain some `mcp` terminology. CLI is a thinner transport and command surface over much of the same browser-tool backend, not an entirely separate automation engine.

### 17.5 What persists and what does not

| State | Persists between CLI commands? | Owner |
|---|---:|---|
| Browser process | Yes | daemon |
| BrowserContext | Yes | daemon |
| Open pages/tabs | Yes | BrowserContext/daemon |
| In-page JavaScript state | Yes, until navigation/reload | renderer |
| Cookies/local storage | Yes during session | BrowserContext/profile |
| Routes and event logs | Yes during session | daemon/context |
| Trace/video state | Yes while active | daemon/context |
| CLI argument parser process | No | each shell invocation |
| CLI socket connection | No | one request/response |
| Snapshot refs | Only while their snapshot/DOM identity remains valid | injected selector state |

The distinction matters when optimizing. Browser startup is already amortized. Shell-process startup and one local socket handshake remain on each command.

## 18. Exact snapshot and ref pipeline

### 18.1 Command-to-snapshot flow

```text
playwright-cli snapshot --depth=4
       │
       v
CLI parser -> browser_snapshot tool
       │
       v
Response.setIncludeFullSnapshot(depth=4)
       │
       v
Tab.captureSnapshot()
       │
       v
page.ariaSnapshot({ mode: "ai", depth: 4 })
       │
       v
Playwright server/frame implementation
       │
       v
injected utility script in page's utility world
       │
       ├─ traverse DOM, slots, open shadow roots, ARIA ownership
       ├─ compute implicit/explicit role
       ├─ compute accessible name and description
       ├─ compute states: checked, disabled, expanded, selected, etc.
       ├─ determine visibility/relevance
       ├─ optionally compute bounding boxes
       └─ assign stable-within-context eN refs
       │
       v
render compact YAML-like AI snapshot
       │
       v
Response writes snapshot or returns it inline
```

The current backend calls `page.ariaSnapshot({ mode: 'ai', depth, boxes })` or the same operation on a root locator for partial snapshots. See [Tab.captureSnapshot](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/backend/tab.ts) and the [snapshot tool](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/backend/snapshot.ts).

### 18.2 Why an injected utility world is useful

Playwright needs page-local facts that browser protocols do not expose uniformly across Chromium, Firefox, and WebKit:

```text
role/name semantics
visibility checks
shadow-root traversal
selector evaluation
DOM connection state
hit-target interception
```

It therefore installs internal JavaScript in an isolated utility environment associated with each frame. Conceptually:

```text
page main world
  ├── application scripts
  ├── React/Vue
  └── application monkey patches

Playwright utility world
  ├── injected selector engines
  ├── ARIA algorithms
  ├── visibility/actionability helpers
  └── ref-to-element mapping
```

This separation makes the automation helpers less vulnerable to application code overwriting globals such as `querySelector`, although the helpers still inspect the same underlying DOM and layout.

### 18.3 Ref creation

The conceptual data structures are:

```text
snapshot text                       injected in-frame map

- button "Checkout" [ref=e17]      e17 ──> HTMLButtonElement
- textbox "Coupon" [ref=e18]       e18 ──> HTMLInputElement
```

Playwright's ARIA snapshot generator associates a generated ref with a concrete element and includes that ref in rendered snapshot text. The special `aria-ref` selector engine later resolves the ref against the most recent snapshot information. See [ariaSnapshot.ts](https://github.com/microsoft/playwright/blob/main/packages/injected/src/ariaSnapshot.ts) and [injectedScript.ts](https://github.com/microsoft/playwright/blob/main/packages/injected/src/injectedScript.ts).

### 18.4 Ref resolution in the CLI backend

The CLI backend distinguishes refs using a pattern equivalent to:

```text
e17       element in main frame
f2e17     element ref associated with another frame
```

Then:

```text
target matches ref pattern?
│
├── yes
│   ├─ construct page.locator("aria-ref=e17")
│   ├─ optionally attach human description
│   ├─ normalize locator
│   └─ fail with "capture new snapshot" if ref is invalid
│
└── no
    ├─ parse CSS or Playwright locator expression
    ├─ preflight with page.$(selector)
    ├─ fail early if no element exists
    └─ create live page.locator(selector)
```

That exact ref-versus-selector branch lives in [Tab.targetLocators](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/backend/tab.ts).

### 18.5 Snapshot cost model

Snapshot cost is roughly:

```text
T_snapshot =
    T_cross_process_call
  + T_DOM_traversal
  + T_accessible_name_computation
  + T_visibility_and_state_computation
  + T_optional_layout_boxes
  + T_string_rendering
  + T_file_or_socket_output
```

The expensive terms grow with the number and complexity of rendered DOM nodes—not the amount of application data that exists outside the DOM.

Common cost multipliers:

- thousands of rendered rows instead of virtualization;
- deeply nested wrapper DOM;
- many elements with complex accessible-name relationships;
- open shadow trees;
- iframes;
- requesting `--boxes`, which adds layout reads;
- full snapshots when only one region matters;
- immediately repeating snapshots when no useful state changed.

## 19. Exact click flow: shell command to browser event

This is the complete layered flow for a normal click:

```text
playwright-cli click e17
│
├─ [CLI client]
│    parse args
│    connect to session socket
│    send run request
│
├─ [CLI daemon]
│    parse command -> browser_click
│    validate target and options
│
├─ [backend click tool]
│    response.setIncludeSnapshot()
│    tab.targetLocator(e17)
│    tab.waitForCompletion(...)
│
├─ [Playwright Locator API]
│    locator.click(options)
│
├─ [Playwright server action pipeline]
│    resolve selector strictly
│    retry through transient failures
│    wait visible/enabled/stable
│    scroll into view
│    calculate clickable point
│    install hit-target interceptor
│
├─ [browser-specific input backend]
│    mouse move
│    mouse down
│    mouse up
│
├─ [browser renderer]
│    coordinate hit test
│    pointer/mouse/focus/click events
│    event capture + target + bubble
│    default action
│
├─ [application]
│    handler -> state update -> request -> rerender
│
├─ [CLI completion wrapper]
│    settle window
│    navigation/network completion heuristic
│
├─ [response builder]
│    capture post-action AI snapshot
│    collect page/tab/console/event metadata
│    write snapshot file
│
└─ [CLI client]
     receive response
     print link/status
     exit
```

### 19.1 Locator strictness and live resolution

`Locator` is a query recipe, not a cached DOM node:

```text
locator = getByRole("button", { name: "Pay" })

time A: action starts
        locator resolves current DOM

time B: React replaces button

time C: retry
        locator resolves new current DOM
```

Caching an `ElementHandle` would be faster in a synthetic microbenchmark but less reliable in real applications. Playwright intentionally re-resolves locators because DOM churn is normal.

### 19.2 Actionability state machine

Simplified:

```text
resolve selector
      │
      ├── 0 elements -> wait/retry until timeout
      ├── >1 elements under strict mode -> fail as ambiguous
      └── exactly 1
              │
              v
        attached to DOM?
              │ no -> retry resolution
              v
        visible?
              │ no -> wait/retry
              v
        stable across animation frames?
              │ no -> wait/retry
              v
        enabled?
              │ no -> wait/retry
              v
        scroll into view
              │
              v
        calculate point from visible content quad
              │
              v
        hit target reaches intended element/subtree?
              │ no -> retry with alternate scroll alignment
              v
        dispatch input
```

The detailed pointer-action loop is in [Playwright's server-side DOM implementation](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/dom.ts). The public guarantees are summarized in [Playwright actionability](https://playwright.dev/docs/actionability).

### 19.3 Why hit-target interception matters

Calculating a rectangle is not enough:

```text
target rectangle: x=100..220, y=300..340
chosen point:     x=160,      y=320

visual stack at that point:

z=100  transparent loading overlay  ← actual browser hit target
z=10   intended Pay button
z=0    page background
```

Playwright checks the hit target near the moment of input. If another element receives the event, it reports the interceptor and retries rather than silently claiming it clicked the button.

### 19.4 Browser-specific final mile

After all Playwright-level checks, the final input layer differs by browser:

```text
Playwright mouse.click(x, y)
       │
       ├─ Chromium -> CDP Input.dispatchMouseEvent
       ├─ Firefox  -> Playwright Firefox Page.dispatchMouseEvent
       └─ WebKit   -> Playwright WebKit protocol messages
```

That final layer is small. Most reliability logic has already run above it.

### 19.5 What Playwright CLI waits for after the click

The CLI adds a completion heuristic around the normal Locator action. Current source behavior is approximately:

```text
start listening for requests
       │
       v
run locator.click()
       │
       v
wait settle window (default internally: 500 ms)
       │
       v
did action trigger a navigation request?
       │
       ├── yes
       │     └─ wait for main-frame load, capped at 10 seconds
       │
       └── no
             ├─ wait for captured document/stylesheet/script/xhr/fetch
             │  responses to finish, capped at 5 seconds
             └─ if any request occurred, wait another settle window
```

See the current [waitForCompletion implementation](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/backend/utils.ts).

This wrapper explains two things simultaneously:

1. why Playwright CLI often returns a more settled page than a minimal CDP click implementation;
2. why a successful action can take noticeably longer than the physical mouse dispatch.

The mouse dispatch may take milliseconds. Waiting for the application and observing its result can take hundreds or thousands of milliseconds.

## 20. Where the time actually goes

Use this latency equation before optimizing:

```text
T_total
 = T_shell_process
 + T_registry_and_socket
 + T_command_parse_and_validation
 + T_target_resolution
 + T_actionability
 + T_input_dispatch
 + T_application_work
 + T_completion_settle
 + T_post_action_snapshot
 + T_response_serialization
 + T_agent_reasoning
```

An expanded flow:

```text
┌────────────┐  ┌───────┐  ┌─────────┐  ┌──────────┐  ┌────────────┐
│Node startup│->│Socket │->│Resolve  │->│Click     │->│App/network │
└────────────┘  └───────┘  └─────────┘  └──────────┘  └──────┬─────┘
                                                               │
┌────────────┐  ┌──────────┐  ┌─────────┐  ┌────────────┐      │
│LLM decides │<-│Serialize │<-│Snapshot │<-│Settle/wait │<─────┘
└────────────┘  └──────────┘  └─────────┘  └────────────┘
```

Likely dominant terms by scenario:

| Scenario | Likely dominant term |
|---|---|
| Static local page, repeated `eval` | CLI process + IPC |
| Huge DOM snapshot | ARIA traversal + serialization |
| Animated button | actionability/stability retry |
| SPA click issuing API request | app/network + completion settle |
| Navigation | server/load/network |
| LLM browser agent | model reasoning + snapshot token processing |
| Screenshot-heavy loop | compositor capture + image processing/model vision |

### 20.1 Minimal measurement ladder

Measure the layers separately on a stable local or test page:

```bash
# Mostly client + IPC + trivial JS runtime round trip
/usr/bin/time -p playwright-cli --raw eval "1"

# Snapshot traversal and output at different depths
/usr/bin/time -p playwright-cli --raw snapshot --depth=2
/usr/bin/time -p playwright-cli --raw snapshot --depth=6
/usr/bin/time -p playwright-cli --raw snapshot

# End-to-end action, completion wait, and resulting snapshot
/usr/bin/time -p playwright-cli click e17
```

Run each case repeatedly and compare median and p95, not one warm or cold observation.

Use tracing when actionability or navigation dominates:

```bash
playwright-cli tracing-start
playwright-cli click e17
playwright-cli tracing-stop
```

Use the browser's Performance API around application code when the click succeeds quickly but the UI updates slowly.

### 20.2 Benchmark table template

```text
Case                         median    p95      notes
---------------------------  --------  -------  -------------------------
eval "1"                     ___ ms    ___ ms   client/IPC floor
snapshot depth=2             ___ ms    ___ ms   shallow semantic tree
snapshot full                ___ ms    ___ ms   full DOM/ARIA cost
click with no requests       ___ ms    ___ ms   includes settle window
click with one API request   ___ ms    ___ ms   includes request finish
click causing navigation     ___ ms    ___ ms   includes load heuristic
```

Without these numbers, “optimize Playwright” is too broad to produce a reliable patch.

## 21. Optimizing Playwright CLI without modifying its source

Start here. These improvements preserve Playwright's reliability mechanisms.

### 21.1 Reuse sessions

Do:

```bash
playwright-cli -s=shop open https://shop.example
playwright-cli -s=shop snapshot
playwright-cli -s=shop click e17
playwright-cli -s=shop fill e22 "hello"
```

Avoid repeatedly opening and closing the browser. The persistent daemon exists specifically to amortize browser startup and keep page state alive.

### 21.2 Reduce observation size before reducing correctness

For a large page:

```bash
# Broad orientation, bounded depth
playwright-cli snapshot --depth=4

# Search the snapshot without returning the entire tree
playwright-cli find "Add to cart"

# Snapshot only a relevant subtree after finding its container
playwright-cli snapshot e34

# Add boxes only when coordinates/layout matter
playwright-cli snapshot e34 --boxes
```

Use this flow:

```text
large page
   │
   v
shallow snapshot or find
   │
   v
identify relevant section ref
   │
   v
partial subtree snapshot
   │
   v
act
```

This reduces DOM traversal, file size, and agent tokens while retaining semantic targeting.

### 21.3 Use direct durable locators after discovery

Once you know the stable target, you do not need a full discovery snapshot before every action:

```bash
playwright-cli click "getByRole('button', { name: 'Checkout' })"
playwright-cli fill "getByLabel('Email')" "me@example.com"
playwright-cli click "getByTestId('confirm-order')"
```

Use refs for short observation/action loops and semantic locators for known workflows.

### 21.4 Combine operations only when no observation checkpoint is needed

Built-in combination:

```bash
playwright-cli fill e5 "search text" --submit
```

For a deterministic block:

```bash
playwright-cli run-code "async page => {
  await page.getByLabel('Email').fill('me@example.com');
  await page.getByLabel('Password').fill('secret');
  await page.getByRole('button', { name: 'Sign in' }).click();
}"
```

The tradeoff is explicit:

```text
separate commands
  + observe after each step
  + easier recovery
  - process/socket/snapshot overhead per step

one run-code block
  + one CLI round trip
  + one final observation
  - less visibility between steps
  - larger failure unit
```

Batch only sequences whose intermediate result does not require a decision.

### 21.5 Keep model-facing output small

`--raw` removes status and generated-code sections from printed output, retaining the result/error/snapshot portions:

```bash
playwright-cli --raw eval "document.title"
playwright-cli --raw snapshot --depth=3
```

It reduces serialization sent to the caller; it does not automatically eliminate underlying snapshot computation for commands that request a snapshot.

A conservative `.playwright/cli.config.json` for agent use can be:

```json
{
  "outputMode": "file",
  "codegen": "none",
  "console": {
    "level": "warning"
  },
  "timeouts": {
    "action": 5000,
    "navigation": 30000
  }
}
```

This uses documented configuration fields. `codegen: "none"` removes the “Ran Playwright code” section when you do not need generated test snippets. `outputMode: "file"` keeps large artifacts out of standard output. Only reduce timeouts to values compatible with the application's measured service level; a smaller timeout does not make an action faster when it succeeds, it merely fails sooner.

### 21.6 Reuse authentication state

Do not repeat login UI in every workflow:

```bash
playwright-cli state-save auth.json

# later, in an appropriate clean session
playwright-cli state-load auth.json
```

This can save far more time than micro-optimizing IPC. Protect the state file because it may contain authentication material.

### 21.7 Use headless unless you need human observation

Headless avoids window-server and live-display overhead. Use `--headed` for debugging, visual judgment, or manual takeover—not as an automatic default.

### 21.8 Do not record expensive artifacts continuously

Tracing, video, screenshots, and `--boxes` are diagnostic tools. Turn them on around a failure or an intentionally reviewed flow rather than every low-risk action.

```text
normal loop: snapshot -> act -> semantic verification

debug loop: trace start -> reproduce -> screenshot/console/network -> trace stop
```

### 21.9 Block only provably irrelevant requests

Request routing can remove analytics, ads, or known irrelevant large assets:

```bash
playwright-cli route "https://analytics.example/**" --status=204
```

Do not globally block stylesheets, fonts, or images when testing layout or clickability. Those resources can change element dimensions, overlays, responsive breakpoints, and hit testing.

### 21.10 Use application readiness signals

The fastest reliable wait is an observable condition:

```text
bad:  sleep 2000 ms

good: wait until
      - spinner disappears
      - button becomes enabled
      - expected response completes
      - route changes
      - result heading becomes visible
```

Arbitrary sleeps always pay their full duration and still fail when the application is slower than expected.

## 22. Optimizing Playwright CLI's source

Clone the repositories only if you intend to modify and benchmark the implementation. Most real users should stop at the previous section.

The proposals below are **benchmark hypotheses, not claims that Microsoft overlooked obvious optimizations**. Several are variants of mechanisms the maintainers already implemented; others preserve a deliberate speed-versus-reliability tradeoff. If building a fork or proposing upstream changes, test them in this order and discard them when the measurements do not justify the added behavior or complexity.

### 22.1 Add measurement spans first

Instrument:

```text
client process startup
registry load
socket connect
daemon command parse
target resolution
actionability
input dispatch
completion wait
snapshot capture
response serialize/write
```

Return them only under a debug flag:

```yaml
timings:
  socketConnectMs: 2
  targetResolveMs: 8
  actionMs: 41
  settleMs: 501
  snapshotMs: 93
  serializeMs: 4
```

Without spans, source changes risk optimizing a 4 ms stage while the fixed settle window consumes 500 ms.

### 22.2 Support a batch RPC with observation policy

Current warm commands still pay for:

```text
Node client start + socket connect + response + process exit
```

per shell command.

A minimal source-level batch API could be:

```text
runBatch([
  fill(email),
  fill(password),
  click(signIn)
], observe="final", stopOnError=true)
```

Flow:

```text
one CLI client
    │
    v
one socket request
    │
    v
daemon executes action 1
    │
    ├─ error? stop and return indexed failure
    v
daemon executes action 2
    │
    v
daemon executes action 3
    │
    v
one settle + one final snapshot
```

Required safety properties:

- stop on first error by default;
- report which action failed;
- allow explicit snapshot checkpoints;
- preserve modal/dialog handling;
- never parallelize state-changing actions in one page;
- abort the remaining batch if the page/context closes.

This likely offers more benefit than changing socket serialization.

### 22.3 Make completion settling adaptive and opt-in configurable

The current completion wrapper always pays an initial settle interval, then may wait for captured requests, then may pay another settle interval.

A more adaptive algorithm could be:

```text
action begins
   │
   ├─ record navigation and relevant network events
   v
action completes
   │
   v
wait for a short quiet window
   │
   ├─ new relevant request/event arrives
   │      └─ reset quiet-window timer
   │
   └─ quiet window expires
          └─ return

hard maximum prevents endless live-page waiting
```

Expose policies rather than one magic duration:

```text
completion: "auto"       current safe behavior
completion: "action"     return after Locator action
completion: "network"    wait for tracked request quiescence
completion: "navigation" wait only for requested navigation
```

Why this must be opt-in:

- analytics and long polling can prevent network idle;
- requests can begin after timers longer than the quiet window;
- DOM updates can happen without network;
- WebSockets do not have a simple “finished” state;
- returning too early increases stale or intermediate snapshots.

The current source already has an internal `timeouts.settle` value, but it is not part of the documented CLI configuration schema shown in the README. Treat it as an implementation detail unless the installed version exposes it publicly.

### 22.4 Add post-action snapshot policies

Input tools currently request a resulting snapshot. That is useful for agents but wasteful for a deterministic batch whose caller already knows the next action.

A source-level policy could be:

```text
snapshot: "full"       current strong observation
snapshot: "changed"    semantic diff since previous snapshot
snapshot: "target"     target plus affected semantic neighborhood
snapshot: "none"       caller promises to observe later
```

The lowest-risk addition is `none` as an explicit per-command or batch option. `changed` is much harder.

An incremental diff must handle:

- nodes moving between parents;
- accessible names changing due to distant labels;
- visibility changes caused by ancestor styles;
- iframe navigation;
- shadow-tree replacement;
- duplicate nodes with similar roles/names;
- ref identity across DOM replacement.

Do not ship a mutation-observer diff that assumes each DOM mutation affects only its immediate subtree. Accessible-name and visibility dependencies can cross those boundaries.

### 22.5 Avoid duplicate non-ref selector preflight only if measurements justify it

Current non-ref target flow first calls `page.$(selector)` to produce an immediate “does not match” error, disposes the handle, then creates a live locator which resolves again during the action.

```text
selector
  ├─ page.$ preflight resolution
  └─ locator.click live resolution
```

A fork could trust Locator's own strict resolution and improve its error formatting, removing the first query. This is a valid micro-optimization, but it is probably insignificant next to actionability, settling, and snapshot capture. Measure before touching it.

### 22.6 Parallelize independent response metadata carefully

The response builder captures the current tab snapshot and tab headers before formatting output. Independent read-only work could sometimes overlap:

```text
Promise.all([
  captureSnapshot(),
  captureTabHeaders(),
  collectStableMetadata()
])
```

Risks:

- a tab can navigate or close between reads;
- metadata and snapshot can describe slightly different instants;
- console/event drains must not happen twice or out of order.

Only parallelize operations whose consistency contract permits it.

### 22.7 Add a long-lived stdin/REPL client only after batch RPC

A persistent client could remove Node startup and socket handshake entirely:

```text
agent stdin -> one CLI process -> one socket -> daemon
```

But it adds lifecycle, backpressure, cancellation, multiplexing, and recovery complexity. A batch request captures most of the value for less complexity. Build the REPL only if measurements show many single actions cannot be batched and client startup remains material.

### 22.8 Snapshot caching is high risk

It is tempting to cache a full semantic snapshot until a mutation observer reports a change. Problems include:

- scroll changes boxes without DOM mutation;
- CSS animation changes hit testing without attribute mutation;
- stylesheets load asynchronously;
- accessible names can depend on remote nodes;
- focus and selection alter semantic state;
- iframe documents change independently;
- browser state can change without obvious DOM writes.

A cache key needs more than `MutationObserver`. Start with explicit caller-controlled snapshot suppression, not automatic semantic caching.

## 23. What not to optimize away

These “optimizations” usually make browser automation worse:

### Do not cache DOM elements across arbitrary actions

```text
faster synthetic benchmark
        │
        v
stale ElementHandle after React commit
        │
        v
more retries and flaky failures in production
```

Keep live locators.

### Do not default to forced clicks

`force` suppresses evidence that an overlay, animation, or disabled state makes the interface unusable. It can make a test green while a user still cannot click.

### Do not replace semantic snapshots with raw HTML

Raw HTML is frequently larger and less informative to an agent. It also loses computed accessible names, implicit roles, visibility filtering, and user-centered meaning.

### Do not switch Playwright to Chrome's native AX tree merely for speed

That would weaken cross-browser consistency and couple snapshots to browser-specific accessibility behavior. Benchmark first and preserve semantic equivalence if experimenting.

### Do not globally disable rendering resources

CSS, fonts, images, and animations influence layout and hit testing. Disable animations for deterministic visual capture when appropriate; do not assume a resource-stripped page is behaviorally equivalent.

### Do not make timeouts tiny to claim lower latency

```text
lower timeout ≠ faster successful operation
lower timeout = earlier failure when the condition is slow
```

Optimize the condition or wait policy, not the number alone.

## 24. Recommended optimization roadmap

### Phase 1 — No source changes

- [ ] Keep one named session open for the workflow.
- [ ] Measure trivial `eval`, shallow snapshot, full snapshot, and representative click.
- [ ] Record median and p95 over repeated runs.
- [ ] Use `find`, `--depth`, and subtree snapshots on large pages.
- [ ] Switch known workflows from discovery refs to durable semantic locators.
- [ ] Combine only deterministic intermediate steps using `fill --submit` or `run-code`.
- [ ] Set `codegen: "none"` when generated snippets are unused.
- [ ] Keep large output in files and use `--raw` for machine consumption.
- [ ] Save and restore authentication state instead of logging in repeatedly.
- [ ] Enable trace/video/screenshots only around diagnostic workflows.

Acceptance criteria:

```text
no reduction in pass rate
no forced clicks
no arbitrary sleeps
smaller snapshot/token volume
lower measured median and p95 workflow duration
```

### Phase 2 — App/testability improvements

- [ ] Replace clickable `div` elements with semantic controls.
- [ ] Give controls unique accessible names.
- [ ] Add stable test IDs only where user-facing semantics are insufficient.
- [ ] Expose explicit loading and ready states.
- [ ] Ensure disabled controls use real disabled semantics.
- [ ] Keep unnecessary DOM size under control or virtualize large lists.
- [ ] Add accessible DOM controls for important canvas/WebGL operations.

These changes often improve both users and automation more than a CLI fork.

### Phase 3 — Source prototype

- [ ] Add opt-in timing spans.
- [ ] Prove which stages dominate.
- [ ] Prototype batch RPC with `observe=final` and stop-on-error.
- [ ] Prototype explicit `snapshot=none` for safe deterministic sequences.
- [ ] Compare completion policies on real SPAs, navigation, and failure cases.
- [ ] Measure correctness and latency together.
- [ ] Submit the smallest independently useful upstream change.

### Phase 4 — Only if earlier data demands it

- [ ] Prototype semantic snapshot diffs.
- [ ] Test accessible-name dependency invalidation.
- [ ] Test iframe and shadow-root invalidation.
- [ ] Add a persistent client/REPL only if batch RPC is insufficient.

The optimization priority should be:

```text
1. stop reopening browsers
2. stop observing more page than needed
3. stop creating unnecessary command checkpoints
4. tune completion policy with evidence
5. only then optimize client/IPC micro-latency
6. incremental semantic caching last
```

## 25. Adversarial review: surely Microsoft and Vercel already considered this

Yes. Assume competent maintainers before assuming an overlooked optimization.

The adversarial verdict on the preceding sections is:

```text
most user-level advice       = using features they already designed
most source-level proposals  = known tradeoffs, not novel discoveries
a few possible improvements  = hypotheses requiring workload-specific evidence
```

### 25.1 Evidence that the maintainers are already optimizing these exact layers

Microsoft has already implemented:

- persistent CLI sessions and a detached daemon, amortizing browser startup;
- workspace/session registry and local socket transport;
- snapshot files instead of forcing full trees into command output;
- subtree and depth-limited snapshots;
- a `find` command that returns matching semantic nodes and nearby context instead of the whole snapshot;
- AI-specific snapshot distillation that merges text, removes semantic noise, unwraps generic wrappers, and preserves ref resolution;
- output modes, output budgets, raw output, code-generation suppression, and configurable timeouts;
- a completion heuristic that intentionally trades some latency for a more settled post-action state.

Microsoft's [AI snapshot distillation change](https://github.com/microsoft/playwright/pull/41604) explicitly discusses token reduction, ref preservation, algorithmic complexity, and performance concerns. The same release introduced semantic snapshot search because returning a whole snapshot is expensive when the caller needs only one matching region.

Vercel has already implemented or investigated:

- a persistent daemon;
- replacement of the Node/Playwright daemon with native Rust;
- direct CDP;
- command and full-agent-loop benchmarks;
- batching CDP operations that previously performed sequential round trips per interactive element;
- a fast path for identical snapshot diffs;
- network-idle fixes requiring a consistent 500 ms idle period;
- cross-origin iframe sessions;
- stale daemon/socket recovery;
- browser process-tree cleanup and idle daemon shutdown;
- filtering semantic noise and supplementing cursor-interactive elements.

Most importantly, Vercel's own [daemon benchmark documentation](https://github.com/vercel-labs/agent-browser/blob/main/benchmarks/README.md) says per-command latency is dominated by Chrome/CDP round trips and that native-daemon command speedups are usually small. It says Rust's major wins are cold start, daemon memory, and distribution size. The [agent-browser changelog](https://github.com/vercel-labs/agent-browser/blob/main/CHANGELOG.md) documents the batching, network-idle, snapshot, iframe, and process-lifecycle work.

That directly rejects a simplistic hypothesis:

```text
Rust daemon
    therefore
every browser command is dramatically faster
```

The more accurate model is:

```text
T_command = small control-plane cost
          + much larger browser/application-dependent cost

Rust shrinks the first term.
It does not erase the second.
```

### 25.2 Reclassifying every proposed optimization

| Proposal from this guide | Adversarial classification | Verdict |
|---|---|---|
| Persistent daemon/session reuse | Already implemented by both | Usage guidance, not a new optimization |
| Smaller snapshots | Already implemented repeatedly | Use depth, subtree, find, filtering, and distillation first |
| Output snapshots to files | Already implemented | Model-context optimization, not new engine work |
| Rust/native daemon | Already implemented by Vercel and benchmarked | Large memory/install win; typically small warm-command win |
| Batch CDP calls | Already implemented where Vercel found pathological sequential calls | Valid only where tracing shows repeated serial round trips |
| Batch several user actions | Existing escape hatch through Playwright `run-code` | A first-class RPC could improve ergonomics, but loses observation checkpoints |
| Adaptive completion settling | Known hard problem | Must outperform the current heuristic without returning intermediate state |
| Remove the 500 ms quiet period | Previously caused false idle in agent-browser | Likely a reliability regression unless replaced by a better signal |
| Incremental snapshot diff | Partially explored; agent-browser already has diff optimizations | Full semantic invalidation remains complex and high-risk |
| Eliminate selector preflight | Plausible micro-optimization | Ignore unless profiling shows it matters |
| Persistent stdin/REPL client | Heavy browser state is already persistent in daemon | Probably unnecessary unless client startup is measured as material |
| Cache element handles | Conflicts with DOM-rerender reliability | Reject |
| Disable actionability checks | Converts product bugs into false test success | Reject |
| Replace Playwright ARIA computation with Chrome AX | Sacrifices cross-browser semantics | Reject without equivalence proof |
| Add timing spans | Maintainers have internal tracing; CLI-specific stage reporting could still help | Credible observability proposal, not necessarily a speed optimization |
| Explicit per-command observation policy | Product API tradeoff | Credible only if real workflows need it beyond `run-code` |

### 25.3 Why agent-browser can still feel worse even though Vercel thought about it

Thinking about a problem is not the same as choosing the same product objective or having the same maturity envelope.

```text
Microsoft Playwright objective
  maximize reliable web automation across browser engines
  even when that requires injected logic, retries, and waits

Vercel agent-browser objective
  provide a compact, fast-starting, Chrome-first agent CLI
  without Node or Playwright as runtime dependencies
```

Removing Playwright removes a dependency, but it also means reimplementing whichever Playwright behavior the product still wants:

```text
Playwright capability removed with dependency
        │
        ├─ selector semantics
        ├─ actionability state machine
        ├─ detach/retry behavior
        ├─ frame coordinate handling
        ├─ browser-specific quirks
        ├─ input sequencing
        ├─ navigation waiting
        └─ diagnostics
                │
                v
agent-browser chooses which portions to rebuild
```

Vercel may rationally accept a smaller or differently shaped reliability envelope in exchange for a tiny native daemon, lower memory, smaller installation, and direct Chrome control. Your worse experience can be a real consequence of that tradeoff rather than evidence that the team never considered reliability.

There is also a maturity effect. Playwright's action pipeline has accumulated years of cross-browser edge cases. A native rewrite can reach broad command parity faster than it reaches behavioral parity on overlays, animation, cross-origin frames, dialogs, downloads, unusual controls, and lifecycle races.

### 25.4 A stricter standard for claiming an optimization

Do not call a proposed change an optimization until it passes all four gates:

```text
1. Measured bottleneck
   The target stage is material in median or tail latency.

2. Equal semantics
   The new path performs the same observable action.

3. Equal or better success rate
   It does not trade flakiness for a prettier benchmark.

4. Worth the complexity
   The gain exceeds implementation, maintenance, and API cost.
```

Formally:

```text
accept change only if

  latency_new < latency_old
  AND success_rate_new >= success_rate_old
  AND semantic_coverage_new >= semantic_coverage_old
  AND maintenance_cost is justified
```

Benchmark at least these classes separately:

- static DOM;
- React rerender replacing the clicked node;
- CSS animation;
- overlay interception;
- request followed by delayed rerender;
- same-document SPA navigation;
- full document navigation;
- same-origin and cross-origin frames;
- open shadow DOM;
- long polling/WebSocket page;
- large semantic snapshot;
- remote high-latency browser connection.

An improvement on a static local button can be a regression on the workflow that matters.

### 25.5 The source proposals that survive adversarial review

Only three ideas remain credible without pretending the maintainers missed something obvious.

#### 1. Better user-visible latency attribution

Question:

```text
Why did this command take 1.4 seconds?
```

Useful answer:

```yaml
clientStart: 31ms
ipc: 2ms
targetResolution: 11ms
actionabilityAndInput: 43ms
applicationAndNetwork: 501ms
postActionSettle: 500ms
snapshot: 287ms
serialization: 9ms
```

Playwright tracing has deep diagnostic information, but a concise CLI stage breakdown could prevent users and contributors from optimizing the wrong layer.

#### 2. Explicit observation policy for expert workflows

Not “remove snapshots because snapshots are slow,” but:

```text
default: preserve current safe observe-after-action behavior

expert batch:
  execute deterministic steps
  stop on first failure
  capture one final observation
```

This already exists in rough form through `run-code`. A dedicated batch surface is justified only if it materially improves error attribution, safety, or agent ergonomics.

#### 3. Workload-specific completion signals

The generic completion heuristic cannot know the application's real terminal state. An explicit app signal may be both faster and more reliable:

```text
generic tool guesses:
  wait for network/load/quiet period

application knows:
  order status is now "confirmed"
  spinner is removed
  result revision changed
```

The opportunity may therefore belong in application testability or the agent workflow—not Playwright Core.

### 25.6 Revised conclusion

The maintainers did think about these problems. The useful task is not to brainstorm more generic optimizations; it is to find where **your specific workload** sits outside their chosen tradeoff.

```text
observe your failing/slow workflow
        │
        v
trace and attribute the cost/failure
        │
        v
is it usage, application semantics, or tool behavior?
        │
        ├─ usage -> use existing feature correctly
        ├─ app    -> expose stable semantic/readiness signal
        └─ tool   -> produce minimal reproduction + benchmark
                         │
                         v
                  propose the smallest measured change
```

That is the adversarially defensible optimization process.

## 26. Evidence-first optimization for parallel exploration and RBAC workflows

Yes: all three optimization ideas must be tested. They are hypotheses, not conclusions.

Microsoft and Vercel have already considered generic automation costs such as actionability, waiting, observation, browser reuse, and context isolation. A useful local improvement therefore needs to demonstrate at least one of these:

1. this workload differs materially from their assumed workload;
2. an existing capability is present but the skill teaches it poorly;
3. application-specific information can replace a generic heuristic;
4. the CLI exposes insufficient evidence to choose the right existing capability;
5. the improvement moves a measured outcome without reducing correctness or debuggability.

The first optimization step is not a fork. It is a corpus of real sessions.

### 26.1 What to ask existing Playwright CLI sessions

Ask for evidence, including failed attempts, rather than a general opinion such as “what was slow?” A previous session's polished summary is much less useful than its command sequence, errors, state assumptions, and artifacts.

Copy this prompt into five to ten existing sessions that performed materially different browser tasks:

```text
Review only the Playwright CLI work you already performed in this session.
Do not rerun the browser task, change the application, or invent missing timings.

Return an evidence bundle with:

0. Automation surface actually used:
      Playwright CLI, Playwright Test, direct Playwright API, MCP browser,
      or a mixture. Do not describe Playwright Test as Playwright CLI.
1. Task, site/application, and final result: success, partial, or failure.
2. Roles used and the exact Playwright CLI session names, if known.
3. Exact command transcript, or the paths to logs/artifacts containing it.
   State whether every referenced artifact still exists now.
4. The flow as repeated triples:
      starting observable state -> action -> resulting observable state
5. Every retry or failure, including:
      command
      error text
      likely category:
        stale ref, ambiguous target, overlay, actionability, timeout,
        authentication, navigation, frame, application error, or unknown
      recovery attempted
      whether the recovery worked
6. Parallel work attempted and any cookie, storage, data, port, session,
   or shared-record collision.
7. For each major step, measured wall time if available.
   Write "unknown" instead of estimating.
8. Snapshot counts and approximate sizes, plus trace, video, screenshot,
   console, and network artifact paths if available.
9. For cross-role work:
      which role created or changed each shared record
      how the next role learned that the state was ready
      whether the UI and server agreed about authorization
10. The single workflow change that would have helped most, and the
    concrete failed or slow step supporting that claim.

Do not omit repeated commands or failed attempts to make the result look clean.
Separate observed facts from your inference.
```

The highest-value sessions are deliberately different:

- one successful, long SPA flow;
- one flaky flow with retries;
- one authentication or RBAC flow;
- one page producing a large semantic snapshot;
- one flow involving navigation, popups, or frames;
- one shared-record flow in which one user changes what another user sees.

The sessions do not need mobile and dark-mode artifacts. Those dimensions are irrelevant unless the product has a stated requirement or a bug in those modes.

#### What the evidence bundle should let us reconstruct

```text
                           SESSION EVIDENCE
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
          v                       v                       v
     command path             state model            artifact path
  snapshots/actions/retries   role/entity/readiness   trace/log/image
          |                       |                       |
          +-----------------------+-----------------------+
                                  |
                                  v
                     classify cost and failure
                                  |
              +-------------------+-------------------+
              |                   |                   |
              v                   v                   v
           workflow           application           CLI/tool
       unnecessary observe   missing stable signal   reproducible gap
```

Without those three evidence types, a source change is guesswork.

### 26.2 Parallelism is not one feature

“Run it in parallel” hides three different scheduling problems.

#### A. Independent scenario parallelism

Two flows have separate browser sessions, separate test data, and no causal dependency. Run them concurrently.

```text
time -------------------------------------------------------------->

rbac-admin-1:  login -> create project A -> verify A
rbac-admin-2:  login -> create project B -> verify B
rbac-viewer-1: login -> inspect fixture C -> verify no edit control
```

This is the easiest and safest parallelism. Start with three or four concurrent browser sessions and increase only after measuring CPU, memory, server throttling, and failure rate.

#### B. Parallel reads of shared state

Several roles observe the same stable entity without changing it. They may run concurrently after a setup barrier.

```text
admin creates record R-8f31
             |
             v
      [R-8f31 is committed]
             |
      +------+------+
      |             |
      v             v
 viewer reads    auditor reads
      |             |
      +------+------+
             |
             v
       compare outcomes
```

The record identifier must be unique to the run. “Use the newest row” is not a synchronization strategy.

#### C. Cross-role causal choreography

This is a distributed workflow, not a set of independent tests. Steps are sequential at dependency boundaries even if other work runs concurrently.

```text
                 shared application backend
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
  admin session       member session      auditor session
        |                   |                   |
 create request            wait                 wait
        |
        +---- publish request ID/status ------->|
                            |
                      approve request
                            |
                            +---- status ------->|
                                                |
                                          verify audit event
```

Sessions “talk” through the application and its backend. They must not exchange cookies or copy one role's storage state into another role. The orchestrator shares only correlation data such as a generated record ID and observed status.

Rules that prevent most false results:

- use one named Playwright CLI session per actor, such as `rbac-admin`, `rbac-member`, and `rbac-auditor`;
- authenticate each session independently;
- never reuse an element ref such as `e17` between sessions or after a state-changing rerender;
- generate a unique run ID and include it in created data;
- wait on an observable business condition, not a fixed sleep;
- parallelize only causally independent work;
- do not mutate the same entity concurrently unless the purpose is to test a race;
- reset or delete fixtures through an approved test-data mechanism;
- capture the role, session, entity, action, expected state, and observed state for every edge.

### 26.3 Model RBAC as both permissions and propagation

An RBAC test is incomplete if it checks only whether a button is visible. It must test two separate claims:

1. **affordance:** does the UI present the action appropriately for the role?
2. **enforcement:** does the application reject the forbidden operation even if the user navigates directly or sends the same request another way?

Start with a role/action matrix:

```text
+----------------------+---------+---------+---------+--------------------------+
| Resource action      | Admin   | Member  | Viewer  | Expected propagation     |
+----------------------+---------+---------+---------+--------------------------+
| Create request       | allow   | allow   | deny    | record becomes visible   |
| Approve request      | allow   | allow*  | deny    | status + audit update    |
| Edit policy          | allow   | deny    | deny    | new policy affects users |
| Delete request       | allow   | deny    | deny    | record disappears        |
+----------------------+---------+---------+---------+--------------------------+

* only when the member is an assigned approver
```

Then turn each material business flow into a graph:

```text
[Admin: invitation form]
          |
          | submit unique email
          v
[Backend: invitation pending]
          |
          | member observes invitation
          v
[Member: invitation detail]
          |
          | accept
          v
[Backend: membership active] ----------------+
          |                                   |
          v                                   v
[Admin: member shown active]        [Viewer: member visible,
                                      editing unavailable]
          |
          v
[Auditor: invite + acceptance events recorded]
```

Every arrow needs a machine-observable barrier. Examples, ordered from strongest to weakest:

1. a stable application revision, event ID, or record status;
2. a specific response completing with the expected entity ID/version;
3. a target locator reaching an expected state;
4. a URL transition combined with a page-state assertion;
5. a generic load or quiet heuristic;
6. a fixed sleep.

The last item should be used only when the application exposes no observable signal, and the resulting test should be classified as fragile.

### 26.4 “Click through everything” means interaction-graph coverage

Literal blind clicking is unsafe and does not produce meaningful coverage. It can purchase items, send messages, delete data, log the user out, or repeatedly traverse the same state under slightly different markup.

The useful target is a bounded interaction graph.

```text
                         seed fixture + role
                                  |
                                  v
                        snapshot current state
                                  |
                                  v
                     inventory available actions
                                  |
             +--------------------+--------------------+
             |                    |                    |
             v                    v                    v
         read-only            reversible           destructive /
       tabs, menus, nav       controlled edit       external effect
             |                    |                    |
             v                    v                    v
          execute             execute in            skip or require
                              disposable data        explicit approval
             |                    |
             +---------+----------+
                       |
                       v
         record action, URL, state, console, requests
                       |
                       v
               compute state signature
                       |
             +---------+---------+
             |                   |
             v                   v
        unseen state         known state
        enqueue node         stop branch
```

A practical state signature might be:

```text
role
+ normalized route
+ primary landmark or heading
+ open modal/drawer/tab
+ relevant entity ID
+ relevant entity status/version
```

It should not hash the entire DOM. Timestamps, generated class names, ordering noise, live counters, and advertisements would manufacture endless “new” states.

A graph edge records:

```yaml
role: member
session: rbac-member
fromState: /requests/R-8f31 + heading=Request + status=pending
action: approve button
target: accessible role/name or fresh snapshot ref
risk: reversible-test-data
expected: status=approved
observed: status=approved
requests:
  - PATCH /requests/R-8f31 -> 200
toState: /requests/R-8f31 + heading=Request + status=approved
```

Coverage must include more than buttons:

- links and navigation regions;
- menus, disclosures, tabs, drawers, dialogs, and popovers;
- form controls, validation, cancellation, and submission;
- hover- or focus-revealed controls;
- keyboard-only interactions and focus order where relevant;
- pagination, filtering, sorting, and empty states;
- file input or drag/drop only with controlled fixtures;
- history back/forward and deep links;
- popup and frame boundaries;
- authorized and unauthorized paths.

Bound the traversal from the start:

```yaml
allowedOrigins:
  - app.test
allowedRoutes:
  - /projects/**
  - /requests/**
maxDepth: 6
maxStatesPerRole: 100
safeActionClasses:
  - read-only
  - reversible-test-data
blockedActionClasses:
  - purchase
  - delete-production-data
  - send-external-message
  - change-security-settings
```

Breadth-first exploration is usually preferable: it gives broad shallow coverage before spending time down one deep branch. A human-defined workflow remains the right tool for critical transactional paths.

### 26.5 What `vcheck` should and should not do

The current `vcheck` is intentionally narrow:

```text
one active Playwright CLI session's storage state
                |
                v
     N parallel browser contexts
                |
                v
     fixed desktop viewport captures
                |
                v
  baseline/current/pixel-diff directories
```

It does **not** generate mobile or dark-mode variants. The dark/light examples elsewhere in the skill are general media-emulation examples, not a `vcheck` requirement.

Keep the default policy simple:

```text
one canonical desktop viewport
one canonical theme
only URLs and roles that matter to the change
```

Add a device or theme only when it represents an explicit requirement, a known bug class, or a changed responsive/theming path.

`vcheck` is good at stable URL-level visual regression. It is not a crawler, RBAC orchestrator, or transient workflow-state recorder. It currently clones one role's storage state for parallel screenshots, so its parallelism is parallel **capture**, not parallel **multi-role behavior**.

The smallest credible RBAC enhancement, if the evidence corpus proves it necessary, is role-scoped storage rather than a device/theme matrix:

```text
vcheck --scope admin  --session rbac-admin  base urls.admin.txt
vcheck --scope member --session rbac-member base urls.member.txt

.vcheck/
  admin/
    base/
    cur/
    diff/
  member/
    base/
    cur/
    diff/
```

This must not be implemented merely because it looks tidy. First verify that role baselines are currently colliding or requiring error-prone manual directory management. For post-action screens, dialogs, and other states that cannot be restored from a URL, use explicit workflow checkpoints or Playwright Test screenshot assertions instead of stretching `vcheck` into a state-seeding framework.

### 26.6 Test corpus for the three optimization hypotheses

Use the same small corpus for baseline and treatment:

```text
F1  static form with validation
F2  SPA request followed by component replacement
F3  full navigation or popup
F4  overlay or animation that challenges actionability
F5  large semantic snapshot
F6  cross-role shared-entity workflow
F7  long-polling or WebSocket page
F8  one known flaky real-world flow
```

Freeze these inputs per comparison:

- browser and CLI versions;
- machine and browser launch mode;
- application build;
- fixture shape and account roles;
- network profile;
- trace/video settings;
- command sequence, except for the variable under test.

Collect at least:

```text
correctness
  task success rate
  expected final application state
  authorization violations or role leakage
  false-ready count

cost
  total wall time
  median and p95 command/flow time
  number of CLI commands
  number and bytes of snapshots
  CPU/memory where browser concurrency is relevant

robustness
  retries and resnapshots
  stale-ref failures
  actionability/overlay failures
  timeout failures
  shared-record or fixture collisions

diagnosability
  time to identify a forced failure
  whether the failing step and pre-failure state are recoverable
  trace/log usefulness
```

Start with ten repetitions per variant as a screening run. Do not claim a p95 improvement from ten samples. If the effect survives screening, use at least 30–50 repetitions for representative flows; use more if tail latency is the claim.

#### Experiment 1: user-visible latency attribution

Hypothesis:

```text
A concise per-stage timing breakdown identifies the dominant cost
with negligible measurement overhead and agrees with trace evidence.
```

Test:

```text
baseline                         treatment prototype
--------                         -------------------
external wall clock             external wall clock
trace around selected flows     trace around selected flows
manual diagnosis                proposed stage breakdown
```

Initially derive the treatment outside the CLI where possible. The purpose is to validate the timing taxonomy before changing source.

Pass only if:

- the reported dominant stage agrees with trace/manual evidence;
- measurement overhead is below the noise meaningful to the workflow;
- the stages are understandable and actionable;
- “application time” is not falsely attributed to Playwright internals.

Reject or redesign if the categories overlap, routinely report negative/unaccounted time, or merely duplicate the trace viewer without shortening diagnosis.

This is an observability optimization. It is not a speedup by itself.

#### Experiment 2: expert batch/observation policy

Hypothesis:

```text
Batching deterministic steps and taking one final observation reduces
round trips and snapshot cost without hiding important failures.
```

A/B the same flow:

```text
A: safe default

snapshot -> fill -> observe -> fill -> observe -> click -> observe

B: expert deterministic batch

snapshot -> run-code(fill, fill, click, final assertion) -> observe
```

Measure total time, command count, bytes observed, success rate, failure localization, and recovery time. Inject a failure into each intermediate step. A batch that is fast only when everything works but says merely “batch failed” is not an improvement.

Adoption rule:

```text
decision needed from new state?       observe
target may have been replaced?        observe
navigation/frame/popup boundary?      observe
deterministic stable input sequence?  batching may be tested
```

Keep observe-after-action as the safe default. Even if batching wins, expose it only as an expert policy or keep using `run-code`; do not invent a second API unless the existing surface is measurably inadequate.

#### Experiment 3: workload-specific readiness signals

Hypothesis:

```text
A business-state predicate is both faster and more reliable than a
generic completion heuristic for this application.
```

A/B the same action:

```text
A: generic completion                 B: explicit readiness
---------------------                 ---------------------
action returns / generic settle       action returns
next step proceeds                    wait for one of:
                                        entity status/version
                                        response carrying record ID
                                        exact locator state
                                        route + content assertion
```

Measure false-ready rate, time-to-ready, timeout rate, and final correctness. Include long-polling/WebSocket pages because they expose why generic network idleness is a poor definition of application readiness.

Prefer a stable product-level signal over a longer timeout. If adding one small `data-*` hook, status field, or test endpoint makes the flow deterministic, that application change may be better than modifying Playwright CLI.

### 26.7 Adversarial decision gates

An optimization is accepted only if it clears every applicable gate:

```text
                    measured improvement?
                         /       \
                       no         yes
                       |           |
                    reject    correctness equal/better?
                                    /       \
                                  no         yes
                                  |           |
                               reject    failures diagnosable?
                                              /       \
                                            no         yes
                                            |           |
                                         reject    existing feature sufficient?
                                                        /       \
                                                      yes        no
                                                      |           |
                                               improve skill    minimal source
                                               or workflow      change + repro
```

The source patch is the last branch, not the first.

Concrete rejection criteria:

- any RBAC state or credential leakage;
- a success-rate regression outside measured noise;
- lower mean time but materially worse p95 without a justified tradeoff;
- a “ready” result before the business state is committed;
- hidden intermediate failures that increase recovery time;
- gains that disappear when tracing is disabled or the application is warmed equally;
- benefits achievable by named sessions, `run-code`, locators, or explicit assertions already available today.

### 26.8 Documentation issues already worth resolving

The current local skill contains two conceptual contradictions that should be settled with one rule each:

1. one reference says never to use `networkidle`, while another example recommends it;
2. one spec-generation section says scenarios sharing a seed must never run in parallel, while another says uniquely named generated sessions can run in parallel.

The likely resolutions are:

```text
readiness:
  prefer explicit application state;
  use load states only when they actually represent the application's contract;
  do not use networkidle as a universal "ready" signal.

parallel generation:
  setup that mutates one seed session is sequential;
  generated scenarios may run concurrently only after cloning/isolation,
  with unique session names and non-colliding test data.
```

These are documentation/workflow corrections unless the corpus reveals tool behavior that contradicts them.

### 26.9 Minimal execution plan

```text
TODO 1  Send the retrospective prompt to 5-10 existing sessions.
TODO 2  Select 6-8 flows; include one failure and one cross-role workflow.
TODO 3  Build the role/action matrix and unique fixture naming convention.
TODO 4  Run an unchanged Playwright CLI baseline and retain raw artifacts.
TODO 5  Screen the three treatments with 10 repetitions each.
TODO 6  Reject weak ideas; repeat credible effects with 30-50+ runs.
TODO 7  Update the skill's readiness and parallelism guidance.
TODO 8  Add role-scoped vcheck storage only if real baselines collide.
TODO 9  Patch/fork Playwright CLI only for a reproduced tool-level gap.
```

The immediate request to existing sessions is the only prerequisite. Their evidence determines whether the next move is a better recipe, a small `vcheck` scope option, an application readiness hook, or a Playwright CLI change.

## 27. Evidence review P8: useful negative control, not CLI evidence

P8 is the first returned evidence bundle. It is valuable, but it must be classified correctly.

```text
automation actually used
  +-- npx playwright test
  +-- direct @playwright/test Node script
  +-- no playwright-cli
  +-- no named CLI sessions
  +-- no MCP browser

coverage actually obtained
  +-- two single-role client-side palette tests
  +-- public dark-theme route capture
  +-- no cross-role handoff
  +-- no server authorization exercise
  +-- no vcheck

evidence condition now
  +-- command output reconstructed from session context
  +-- logs deleted
  +-- screenshots deleted
  +-- video deleted
  +-- trace never created
```

Therefore:

```text
P8 can inform experimental hygiene and Playwright Test practice.
P8 cannot establish Playwright CLI latency, snapshot, session,
batch-observation, or multi-role behavior.
```

### 27.1 Facts worth retaining

| Observation | What it establishes | What it does not establish |
|---|---|---|
| Cold run A: 2 failures, 10 passes, 2.1 minutes | The failure existed in one observed run | Why it failed |
| Warm run C: 12 passes, 27.3 seconds | Warm application state correlated with success and speed | That warming is the causal fix |
| Cold run D with `test.slow()`: 12 passes, 1.3 minutes | The changed run passed | That `test.slow()` fixed it |
| Cold control E without `test.slow()`: 12 passes, 2.2 minutes | The claimed fix was unnecessary in that control | A deterministic root cause |
| `test.slow()` did not change the 5-second `toHaveURL` budget | The proposed mechanism did not address the blamed assertion | Whether a larger assertion timeout would be desirable |
| `PLAYWRIGHT_WORKERS=2` was used | Tests were worker-parallel | That worker parallelism caused the failure |
| Another verification process overlapped run A | Machine/application contention is a plausible variable | Causation; it was never isolated |
| UI option was absent for the roles | Client-side affordance filtering was exercised | Backend authorization correctness |
| All material artifacts disappeared from `/private/tmp` | The evidence lifecycle failed | That the original visual judgment was wrong |

The most important adversarial conclusion is that the successful and failing arms were not matched. Application build/cache state, concurrent workload, and possibly server warmup differed. The result cannot support a source or timeout change.

### 27.2 Hypothesis impact

#### Hypothesis 1: better latency attribution

**Strengthened, but only at the workflow boundary.**

Observed total time varied from 27.3 seconds warm to 1.3–2.2 minutes in cold-style runs. Yet server boot time, `.next` rebuild time, route compilation time, and application readiness were not measured separately.

```text
reported total
     |
     +-- server startup             unknown
     +-- Next.js compilation/cache  unknown
     +-- browser/test startup       unknown
     +-- login and route readiness  partially observed
     +-- palette interaction        partially observed
     +-- failed navigation wait     observed near timeout
```

This is exactly the kind of case in which a stage breakdown could stop people from “fixing Playwright” when the dominant variable is the application server or build cache. It does not yet show that the timing must be implemented inside Playwright CLI; an external harness may be sufficient.

#### Hypothesis 2: batch/observation policy

**Unchanged.**

P8 used Playwright Test locators and assertions, not the Playwright CLI snapshot/action loop. There is no command-round-trip or snapshot-volume measurement to compare with `run-code` batching.

#### Hypothesis 3: application-specific readiness

**Weakly supported, with an important distinction.**

The palette test already used a business-relevant outcome: the destination URL. The observed failure was not merely “the test checked too early”; the palette closed and the URL stayed on the landing route. Increasing a generic timeout would not prove the click caused a valid navigation.

The missing observations sit earlier:

```text
option selected
      |
      v
click dispatched?
      |
      v
handler executed?
      |
      v
router navigation requested?
      |
      v
destination response/route committed?
      |
      v
destination application state ready?
```

The next reproduction should instrument those boundaries. The correct readiness improvement may be a route-specific condition, but the original evidence is equally compatible with a click/handler/router failure before readiness begins.

#### New prerequisite: durable evidence

**Strongly supported.**

This is not a fourth performance optimization. It is a prerequisite for evaluating any optimization.

```text
experiment without retained evidence
             = anecdote

experiment with commands + environment + trace + final artifacts
             = reviewable result
```

Do not use ephemeral `/private/tmp` paths as the sole evidence referenced by a review. Place outputs in the provided session scratchpad or another intentionally retained, run-specific directory. Store the evidence manifest beside them.

Minimum manifest:

```yaml
runId: p8-repro-cold-w2-001
automationSurface: playwright-test
gitRevision: exact-revision
applicationMode: mock
serverState: cold
workers: 2
concurrentWorkloads: []
commands: commands.txt
stdout: test.log
serverLog: server.log
artifacts:
  - test-results/
result: pass-or-fail
notes: facts-only.md
```

For Playwright Test, remember that `trace: "on-first-retry"` produces no trace when retries are zero. A diagnostic experiment must choose trace settings consistent with its retry configuration. For Playwright CLI, wrap the representative or failing flow with explicit trace start/stop and retain the output in the same run directory.

### 27.3 P8 RBAC coverage boundary

P8 exercised two independent client-side role cases:

```text
admin     -> palette option filtering -> permitted destination
feed_ops  -> palette option filtering -> permitted destination
```

That is useful UI permission coverage, but it is not this:

```text
admin creates shared record
             |
             v
feed_ops changes shared record
             |
             v
viewer observes allowed fields and cannot mutate
             |
             v
backend rejects a forbidden direct operation
```

No shared entity, cross-session barrier, state propagation, or backend enforcement was exercised. P8 must not be counted in the multi-role choreography corpus.

### 27.4 P8 parallelism boundary

Worker concurrency and cross-role orchestration are different:

```text
P8:
  2 Playwright Test workers
  x 2 projects
  x 2 independent roles
  x 3 repeats

not P8:
  role A mutates entity
  -> synchronization barrier
  -> role B consumes mutation
```

The only failure run overlapped another resource-intensive verification process, but this is correlation. It suggests a test, not a conclusion.

### 27.5 Clean reproduction matrix derived from P8

Do not rerun the old sequence ad hoc. Use a controlled factorial screen:

```text
                         workers=1       workers=2
                       +---------------+---------------+
cold application       | repeated arm  | repeated arm  |
                       +---------------+---------------+
prewarmed application  | repeated arm  | repeated arm  |
                       +---------------+---------------+
```

Hold constant:

- exact application revision;
- exact browser projects;
- test data and mock mode;
- port ownership;
- no unrelated verification workload;
- trace/video/screenshot settings;
- run-specific durable output directory;
- definition of cold and prewarmed state;
- server readiness probe.

Add a second controlled comparison only after the first matrix:

```text
machine load absent  vs  one known concurrent workload
```

Do not mix that variable into the cold/warm and worker screen initially.

Collect timestamps for:

```text
server process started
server readiness probe passed
login began/completed
landing route ready
palette opened
option became selected
click began/completed
navigation request observed
URL committed
destination assertion passed/failed
```

Trace every failed arm. Preserve console and server logs. If a failure recurs, the first question becomes “at which boundary did progress stop?” rather than “which timeout should increase?”

### 27.6 What P8 says about `vcheck`

Almost nothing about its implementation or performance: `vcheck` was not used.

It does reinforce the value of project-local, retained visual artifacts. `vcheck` already stores baselines and diffs under `.vcheck/` instead of treating `/private/tmp` as durable evidence. That is a workflow advantage, not proof that role-scoped `vcheck` is needed.

No role visual baselines collided in P8, so this bundle provides **no justification yet** for implementing `vcheck --scope`.

### 27.7 Updated evidence TODOs after P8

```text
DONE   Classify P8 by actual automation surface.
DONE   Exclude it from Playwright CLI performance conclusions.
DONE   Retain its experimental-design and artifact-lifecycle lessons.

TODO   Obtain a session that actually used playwright-cli snapshots/refs.
TODO   Obtain a real cross-role shared-entity flow.
TODO   Obtain snapshot counts/bytes and command-level timing.
TODO   Preserve all future artifacts outside ephemeral /private/tmp.
TODO   Run the latency-attribution corpus before proposing instrumentation.
TODO   Do not implement role-scoped vcheck from P8 evidence.
```

## 28. Evidence review: first genuine Playwright CLI bundle

Unlike P8, this bundle used the actual Playwright CLI and separately used `vcheck`. It is the first evidence that can update the CLI-workflow hypotheses.

### 28.1 Classification

```text
automation surface
  +-- playwright-cli commands
  +-- playwright-cli eval
  +-- vcheck, separately
  +-- no Playwright Test
  +-- no direct Playwright API
  +-- no MCP browser

session model
  +-- unnamed/default persistent CLI session
  +-- producer role observed directly
  +-- other persona details incompletely retained

execution model
  +-- sequential shell chains
  +-- no parallel browser flows
  +-- no trace, video, or network artifact
  +-- artifacts stored inside a disposable worktree
```

The portal payment result itself was coherent:

```text
producer portal page
       |
       +-- UI intentionally gates online payment
       |
       +-- direct in-page POST /pay-intent
                         |
                         v
                expected HTTP 501 + gate message
```

The direct `fetch` validates endpoint parity for the observed session. It does not prove that a user-visible payment control dispatched that request, because it intentionally bypassed the UI.

### 28.2 What this bundle proves

| Evidence | Supported conclusion |
|---|---|
| CLI `snapshot`, `eval`, storage, resize, reload, and screenshot commands were recorded | This was genuine CLI usage |
| No `-s=<session>` appeared | The default session was used |
| Theme and viewport commands were long sequential chains | This is a candidate for reduced matrix size or deterministic batching |
| CLI-wrapper wall times were recorded | There is enough signal to design a timing experiment |
| `vcheck` reported portal/sync as `SAME` | Stable URL capture found no visual difference in that comparison |
| 47 PNGs, at least 9 snapshots, and a console log disappeared with the worktree | Artifact durability is a repeated, verified workflow failure |
| No stale-ref, actionability, ambiguity, timeout, auth, navigation, or frame failure survived in the transcript | This bundle does not establish those CLI failure modes |
| No shared record ID or cross-role handoff was retained | It is not multi-role choreography evidence |

### 28.3 What it does not prove

Do not infer any of the following:

- `playwright-cli --help` internally requires 5.8 seconds;
- `snapshot` computation itself requires 4.0 seconds;
- the daemon, browser, shell, tool wrapper, and orchestration overhead are separable from the reported times;
- `run-code` batching will preserve the same diagnostics;
- named sessions would have prevented a failure in this run;
- role-scoped `vcheck` is necessary;
- the missing screenshots were visually correct;
- client-side role behavior matched server authorization.

The reported times are outer command or wrapper measurements. A source optimization needs process-level and stage-level measurements under a controlled environment.

### 28.4 Updated optimization hypotheses

#### 1. Latency attribution: materially strengthened

Reported measurements:

```text
reload + direct 501 eval                     11.0s
snapshot                                      4.0s
screenshot --help                             4.6s
--help                                        5.8s
theme-state eval                              7.5s
390px dark/light sequence                     8.6s
640px + desktop dark/light sequence          18.7s
```

The oddity is important: an information-only help command appears comparable to a browser observation, while a multi-command chain is not the sum of repeated four-to-six-second costs. That pattern is compatible with measurement overhead outside the CLI process. It is not evidence of a specific slow function.

The next benchmark must record both:

```text
outer orchestration wall time
              |
              +-- shell/process launch
              +-- CLI client startup
              +-- daemon connection
              +-- browser action
              +-- automatic observation
              +-- serialization/output
```

Run `--help` and `--version` without a browser as controls. Then compare `eval`, `snapshot --depth`, and `--raw` under a warm named session. Until those measurements exist, the likely optimization surface is agent/tool round trips rather than Playwright action execution.

#### 2. Batch/observation: strengthened as a test candidate

The original workflow repeatedly changed storage, reloaded, resized, and captured. Those steps were deterministic; the agent did not need to inspect the page between every substep.

```text
separate commands
  resize -> snapshot output
  storage set -> snapshot output
  reload -> snapshot output
  screenshot -> snapshot output

candidate batch
  run-code(
    resize,
    set theme,
    reload,
    assert expected theme/route,
    screenshot
  )
  -> one structured result
```

But the user does not want routine mobile × theme matrices, so the first optimization is deletion: do not capture variants with no requirement. Batching is second, and only for the remaining deterministic checkpoints.

A fair test compares:

```text
A  N separate CLI commands, normal automatic observations
B  one run-code batch with named step errors and a final assertion
```

Force the storage change, reload, readiness assertion, and screenshot to fail independently. Reject batching if it cannot identify which step failed or if its artifact path is ambiguous.

#### 3. Application-specific readiness: slightly strengthened

The payment gate had an exact terminal condition:

```text
HTTP status = 501
and response.title = expected gate message
and user-visible payment affordance = intentionally unavailable
```

That is better than waiting for generic network quiet. However, the direct fetch was an assertion mechanism, not an end-to-end UI action. Future flows should distinguish:

```text
UI affordance state
UI-triggered request
server response
committed shared business state
other role's observed state
```

Each is a separate edge in an RBAC flow.

### 28.5 New high-confidence workflow changes

#### Delete unrequested visual dimensions

The portal alone produced captures at 390×844, 640×900, and 1440×960 in both themes. That may be appropriate for a responsive/theme bug, but it must not be the default verification policy.

```text
default visual check
  one canonical desktop viewport
  one canonical theme
  affected URLs only

add a variant only for
  changed responsive behavior
  changed theming behavior
  explicit acceptance criterion
  known regression
```

This is the cheapest optimization because it avoids commands, screenshots, review time, and false-positive surface.

#### Name sessions by role

The default session obscured which authentication and storage state belonged to each persona. Even without a recorded collision, the audit trail is insufficient for the requested RBAC work.

```text
-s=rbac-producer
-s=rbac-office
-s=rbac-leadership
-s=rbac-proxy-staff
-s=rbac-sync-admin
```

The exact names are less important than stable one-role-per-session isolation.

#### Retain evidence beyond worktree deletion

P8 lost all Playwright Test evidence in `/private/tmp`. This bundle lost all Playwright CLI evidence inside a deleted worktree. Two independent sessions now demonstrate the same root problem.

```text
disposable worktree/.playwright-cli
              |
              | copy immediately after capture
              v
stable run-specific evidence directory
  manifest
  commands
  snapshots
  screenshots
  trace
  console
  requests
```

This justifies a skill rule now. It does not justify a new artifact-management program.

### 28.6 Why this still does not justify patching CLI source

The current skill workspace contains documentation and helper scripts, not the Playwright CLI implementation. In the present environment, `playwright-cli` is not on `PATH`, and the global npm root reported by `npm` does not exist at that location. Consequently, the reported timings cannot be reproduced here yet.

```text
genuine historical CLI evidence
             |
             v
workflow guidance can improve now
             |
             v
restore/install exact CLI version
             |
             v
run controlled benchmark
             |
     +-------+-------+
     |               |
     v               v
workflow wins    source bottleneck reproduced
use skill        clone/patch minimal CLI code
```

Installing or cloning “latest” before recovering the historical version would contaminate the comparison. Record the exact version in the next genuine session.

### 28.7 Next evidence request

The next returned CLI bundle should preserve these fields in particular:

```text
playwright-cli --version
command process time and outer tool-call time
named session and application role
snapshot path and byte size
whether automatic snapshot output was enabled/raw/depth-limited
trace spanning one representative flow
durable artifact root that still exists
one shared entity ID crossing two named role sessions
```

This is enough to run the three A/B tests without cloning the CLI repository first.

## The mental model worth keeping

```text
An LLM does not click a React component.

It reads a compressed representation of browser state,
chooses a target,
and invokes a deterministic automation tool.

The tool resolves that target to a browser/DOM object,
checks layout and interaction constraints,
and injects browser-level input.

The browser hit-tests the coordinates,
dispatches DOM events,
the framework updates application state,
the DOM changes,
and the browser paints new pixels.

Then the agent observes again.
```

That model explains almost everything: stale refs, overlays, hydration, portals, frames, accessibility, canvas limitations, event handlers, and why WebGL is rendering—not automation.
