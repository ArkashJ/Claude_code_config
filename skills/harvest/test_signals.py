"""signals.py must never report a clean harvest it did not measure.

Found 2026-09-27: harness-extractor 1.0.0 reads a Codex rollout as 0 turns and exits 0, and
signals.py printed "0 signals" on a session whose human had asked "did you merge and deploy??"
twice. Zero turns read means unable to measure: exit 2. No network or key needed; it exits
before any Jev call.  Run: python3 ~/.claude/skills/harvest/test_signals.py
"""
import subprocess, sys, tempfile
from pathlib import Path

with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
    f.write('{"type":"summary"}\n')
r = subprocess.run([sys.executable, str(Path(__file__).with_name("signals.py")), f.name], capture_output=True, text=True)
assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
assert "unable to measure" in r.stderr, r.stderr
print("ok — a transcript with no readable turns exits 2, not 0 signals")
