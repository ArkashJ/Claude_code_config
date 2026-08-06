#!/usr/bin/env python3
"""PreToolUse gate (CR-13, synthesis 2026-08-06 §5.2, item 1 of 'if only three things
get built'): a mutating call to an external system is denied until the target identity
has been asserted this session. Keys to ACTION CLASS, never to an authorisation phrase.

Origin: cbfc486c — SES production access requested and a support case opened on another
company's AWS account; no mechanism fired. The standing aws grant in settings.json is
scoped to account <AWS_ACCOUNT_ID> — this gate makes the model look at the account before
mutating.
"""
import json
import pathlib
import re
import sys

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cmd = (d.get("tool_input") or {}).get("command") or ""
sid = re.sub(r"[^A-Za-z0-9-]", "", d.get("session_id") or "nosession")[:40]


def marker(key):
    return pathlib.Path(f"/tmp/claude-idgate-{sid}-{key}")


# Seeing the assertion command marks identity as checked for this session.
# ponytail: marked at request time, not on command success — a failed assert
# still clears the gate once; acceptable, the output lands in context either way.
ASSERTS = {
    "sts get-caller-identity": "aws",
    "benmore apps": "benmore",
}
for needle, key in ASSERTS.items():
    if needle in cmd:
        marker(key).touch()

GATED = [
    (
        "aws",
        r"\baws\s+(?!sts\b|configure\s+list|help\b)[a-z0-9-]+\s+[a-z0-9-]*"
        r"(create|put|delete|update|attach|detach|request|verify|set|enable|disable"
        r"|modify|terminate|run-instances|invoke|start|stop|subscribe|publish)",
        "run `aws sts get-caller-identity` and confirm the account is the intended "
        "tenant (standing grant covers <AWS_ACCOUNT_ID> ONLY)",
    ),
    (
        "benmore",
        r"\bbenmore\s+(deploy|promote|delete-file)"
        r"|\bbenmore\s+sql\b.*\b(INSERT|UPDATE|DELETE|DROP|ALTER)\b",
        "run `benmore whoami && benmore apps` (whoami alone reads a cached "
        "credential and lies: e7faa32e)",
    ),
]
for key, pat, hint in GATED:
    if re.search(pat, cmd, re.I) and not marker(key).exists():
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason":
                    f"Identity gate (CR-13): no identity assertion for '{key}' this "
                    f"session — {hint}, then retry this command.",
            }
        }))
        sys.exit(0)
sys.exit(0)
