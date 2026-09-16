---
name: update-config
description: Safely modify Claude Code settings, hooks, permissions, or global instructions. Use when editing ~/.claude/settings.json, hook commands, plugin or permission configuration, or ~/.claude/CLAUDE.md behavior.
---

# Update Config

Make the smallest change that satisfies the request while preserving unrelated configuration.

1. Read each target file completely and verify the current Claude Code schema against official documentation when the format may have changed.
2. Confirm the exact global or project scope. Require explicit approval before writing outside the active project.
3. Keep an untouched rollback copy and a separate temporary working copy. Patch and validate only the working copy, then replace the target while preserving its mode.
4. Put non-trivial hook logic in a dedicated executable script instead of embedding shell in JSON.
5. For blocking hooks, test positive and negative command cases before registering the hook. Assert both the exit code and the user-facing message.
6. Validate structured files with their native parser, read every changed target back, and report the rollback source.

Never print secrets, access tokens, cookies, or unrelated configuration values. Never widen permissions, delete existing hooks, or rewrite unrelated prose unless the request explicitly requires it.
