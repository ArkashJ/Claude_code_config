#!/usr/bin/env python3
"""Exit 1 if one skill/command name resolves to more than one source Claude can load.

2026-09-22: `wrap` resolved to the Codex-adapted ~/.agents/skills/wrap (linked into ~/.claude/skills)
instead of ~/.claude/commands/wrap.md, and was model-invoked 9 times without the Claude-specific
steps. `start` had four copies. Nothing warned. Fix: keep ONE source per name (unlink the others
from ~/.claude/skills; account-synced copies are removed at claude.ai → Skills).
"""
import collections, re, sys
from pathlib import Path

H = Path.home() / ".claude"
seen = collections.defaultdict(list)
for f in H.glob("skills/*/SKILL.md"):
    m = re.search(r"^name:\s*\"?([\w:-]+)", f.read_text(errors="replace"), re.M)
    seen[(m.group(1) if m else f.parent.name).split(":")[-1]].append(str(f.parent))
for f in H.glob("skills/synced/*/*/SKILL.md"):
    seen[f.parent.name].append(f"account sync: {f.parent.name}")
for f in H.glob("commands/*.md"):
    seen[f.stem].append(str(f))
dupes = {k: v for k, v in seen.items() if len(v) > 1}
for k, v in sorted(dupes.items()):
    print(f"{k}: {len(v)} sources\n  " + "\n  ".join(v))
print(f"{len(seen)} names checked, {len(dupes)} with more than one source")
sys.exit(1 if dupes else 0)
