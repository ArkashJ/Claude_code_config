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

# --- 2026-09-29 (session 3d5863e4): the instrument was blind to mid-turn messages and question answers.
# It printed "human turns: 7" and never judged "you've added unnecessary guard rails which has nerfed
# the tool", the session's most important correction. Runs on the real transcript; no Jev, no network.
sys.path.insert(0, str(Path(__file__).parent))
import signals  # noqa: E402

REAL = Path.home() / ".claude/projects/-Users-arkashjain-Developer-todo-Chantanl-175/3d5863e4-feaf-4569-a533-2caa1e5717bc.jsonl"
if not REAL.exists():
    print(f"SKIPPED (NOT PASSED): real-transcript check needs {REAL}; the blind-spot guard did not run")
    sys.exit(0)
_, turns = signals.load_turns(REAL)
kinds = [t.get("kind", "typed") for t in turns]
nerf = [t for t in turns if "nerfed" in t["human"]]
buyers = [t for t in turns if t.get("kind") == "answer" and "buyers or sellers" in t["human"]]
assert len(turns) > 7, f"only {len(turns)} human turns: mid-turn messages / answers are being dropped again"
assert nerf and nerf[0].get("kind") == "mid-turn", "the 'nerfed' mid-turn correction is not among the human turns"
assert buyers, "no AskUserQuestion answer containing 'buyers or sellers' among the human turns"
# subagent hand-backs and task-notifications are also queued_commands: they must NOT count as human
assert not [t for t in turns if t["human"].startswith(("<task-notification>", "<agent-message"))], "harness notices counted as human turns"
print(f"ok — {len(turns)} human turns ({kinds.count('typed')} typed, {kinds.count('mid-turn')} mid-turn, {kinds.count('answer')} answers); 'nerfed' + 'buyers or sellers' present")
