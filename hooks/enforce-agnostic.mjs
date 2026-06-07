#!/usr/bin/env node
// PostToolUse(Write|Edit) — enforces that any file declaring itself AGNOSTIC in
// a header comment stays portable: no app design tokens, no app-aliased imports.
// Keys off an explicit marker so there are zero false positives — a file is only
// checked once *I* claim it's reusable. Works in any repo (path-independent).
//
// Exit 2 + stderr surfaces the violations back to Claude as actionable feedback.
import { readFileSync } from "node:fs";

let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  const tool = input.tool_name ?? "";
  if (tool !== "Write" && tool !== "Edit" && tool !== "MultiEdit") process.exit(0);

  const file = input.tool_input?.file_path ?? "";
  if (!/\.(tsx?|jsx?|css)$/.test(file)) process.exit(0);

  let src;
  try {
    src = readFileSync(file, "utf8");
  } catch {
    process.exit(0);
  }

  // Only enforce when the file opts in via an AGNOSTIC marker in a comment.
  if (!/\bAGNOSTIC\b/.test(src)) process.exit(0);

  const violations = [];
  // App design tokens — the exact coupling that makes a component non-portable.
  const tokenHits = [...src.matchAll(/var\(--[a-z0-9-]+\)/gi)].map((m) => m[0]);
  if (tokenHits.length) {
    violations.push(
      `app CSS tokens (not portable): ${[...new Set(tokenHits)].slice(0, 6).join(", ")} — accept colors via a prop with hardcoded-hex defaults instead.`,
    );
  }
  // App-aliased imports tie the file to one project's module graph.
  const aliasHits = [...src.matchAll(/from\s+["']@\/[^"']+["']/g)].map((m) => m[0]);
  if (aliasHits.length) {
    violations.push(
      `app-aliased imports (not portable): ${[...new Set(aliasHits)].slice(0, 6).join(", ")} — depend only on npm packages + relative paths.`,
    );
  }

  if (violations.length) {
    process.stderr.write(
      `AGNOSTIC contract violated in ${file}:\n- ${violations.join("\n- ")}\n` +
        `Either make it truly portable, or remove the AGNOSTIC marker if it's meant to be app-specific.`,
    );
    process.exit(2);
  }
  process.exit(0);
});
