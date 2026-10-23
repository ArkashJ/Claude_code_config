"""Offline reporter checks: absent evidence stays invalid; optional extractor fields are optional.

Run: python3 skills/harvest/test_signals.py. No extractor, key, or network needed.
"""
import contextlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import Mock, patch

# Isolate both external boundaries before loading the reporter. The extractor's
# current turns carry n/human/reply/failed/emphatic/at, but no `kind` field.
hunt = types.ModuleType("hunt")
hunt.api_key = Mock(return_value="offline-test")
hunt.ask = Mock(return_value={
    "answers": {
        "corrects": {"noul": 0.9},
        "reask": {"noul": 0.1},
        "doubts_claim": {"noul": 0.1},
        "wants_depth": {"noul": 0.1},
        "area": {"choice": "incomplete", "confidence": 0.9},
        "request": {"choice": "code_change", "confidence": 0.9},
    },
    "model": "offline-mock",
})
signals = types.ModuleType("signals")
source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("signals.py")
with patch.dict(sys.modules, {"hunt": hunt}):
    exec(compile(source.read_text(), str(source), "exec"), signals.__dict__)

with tempfile.TemporaryDirectory() as directory:
    transcript = Path(directory) / ".codex/sessions/rollout.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"type":"summary"}\n')

    def run(turns):
        red = {"meta": {"session": "offline-signals"}, "turns": turns}
        extracted = types.SimpleNamespace(returncode=0, stdout=json.dumps([red]))
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", [str(source), str(transcript)]), \
                patch.object(signals.subprocess, "run", return_value=extracted), \
                patch.object(signals.tempfile, "gettempdir", return_value=directory), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                signals.main()
            except SystemExit as result:
                return result.code, stdout.getvalue(), stderr.getvalue()
        raise AssertionError("reporter did not preserve its exit-code contract")

    code, stdout, stderr = run([])
    assert code == 2 and "unable to measure" in stderr, (code, stdout, stderr)
    hunt.api_key.assert_not_called()
    hunt.ask.assert_not_called()
    print("ok — zero extracted human turns exits 2 before Jev")

    code, stdout, stderr = run([{
        "n": 1, "at": "2026-10-07T00:00:00Z", "human": "You missed the tests?? Fix them.",
        "reply": "", "failed": [], "emphatic": True,
    }])
    assert code == 0 and not stderr, (code, stdout, stderr)
    assert "SIGNALS: 1 of 1" in stdout and "ASKS: 1 requests" in stdout, stdout
    report = json.loads((Path(directory) / "harvest-signals-offline-signals.json").read_text())
    assert report["signals"][0]["turn"] == 1 and report["asks"][0]["kind"] == "code_change", report
    hunt.ask.assert_called_once()
    print("ok — a current extractor turn without optional kind is judged and reported")
