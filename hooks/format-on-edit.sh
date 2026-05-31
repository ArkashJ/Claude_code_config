#!/usr/bin/env bash
# PostToolUse(Write|Edit) formatter — repo-aware so it never imposes a style a
# repo did not ask for. Reads the hook JSON on stdin, formats the edited file
# with the formatter the repo actually configures.
#
# Decision order for JS/TS/CSS/JSON/MD/MDX:
#   1. Prettier, if the repo configures it (a .prettierrc*/prettier.config.* file,
#      or a "prettier" key/dependency in package.json). This is the common case
#      and the reason this script exists: Biome run with default config was
#      reformatting Prettier repos (tabs/semicolons/double-quotes).
#   2. Biome, if a biome.json/biome.jsonc is present and Prettier is not.
#   3. Otherwise: do nothing — an unconfigured repo has no "correct" style to
#      enforce, so we leave the file alone rather than guess.
# Python/Go always use ruff/gofmt. All formatters run from the repo root so they
# pick up the repo's own config and ignore files.
set -u

f=$(jq -r '.tool_response.filePath // .tool_input.file_path // empty' 2>/dev/null)
[ -z "$f" ] && exit 0
[ -f "$f" ] || exit 0

case "$f" in
  *.py) ruff format "$f" 2>/dev/null || true; exit 0 ;;
  *.go) gofmt -w "$f" 2>/dev/null || true; exit 0 ;;
  *.ts | *.tsx | *.js | *.jsx | *.mjs | *.cjs | *.css | *.json | *.jsonc | *.md | *.mdx) ;;
  *) exit 0 ;;
esac

# Walk up from the file to the repo root (first dir with package.json or .git).
root=$(dirname "$f")
d="$root"
while [ "$d" != "/" ] && [ -n "$d" ]; do
  if [ -e "$d/package.json" ] || [ -d "$d/.git" ]; then root="$d"; break; fi
  d=$(dirname "$d")
done

prettier=0
for c in .prettierrc .prettierrc.json .prettierrc.jsonc .prettierrc.yaml .prettierrc.yml \
  .prettierrc.json5 .prettierrc.js .prettierrc.cjs .prettierrc.mjs .prettierrc.toml \
  prettier.config.js prettier.config.cjs prettier.config.mjs; do
  [ -e "$root/$c" ] && prettier=1
done
# A "prettier" config key OR a prettier dependency in package.json also counts.
grep -q '"prettier"' "$root/package.json" 2>/dev/null && prettier=1

if [ "$prettier" -eq 1 ]; then
  (cd "$root" && bunx --no-install prettier --write "$f" 2>/dev/null) ||
    bunx prettier --write "$f" 2>/dev/null || true
  exit 0
fi

if [ -e "$root/biome.json" ] || [ -e "$root/biome.jsonc" ]; then
  (cd "$root" && bunx --no-install @biomejs/biome check --write "$f" 2>/dev/null) ||
    bunx @biomejs/biome check --write "$f" 2>/dev/null || true
  exit 0
fi

# No JS/TS formatter configured — leave the file untouched.
exit 0
