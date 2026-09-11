# ADR 0010 — Fail-closed local IO boundaries

- **Status**: Accepted (2026-09-10; marketplace security review follow-up)

## Context

The marketplace security review at `db39cb2` found that every predictable
path the plugin touches was trusted by default: the API-key config and the
imported OpenCode credential file were opened directly (no `O_NOFOLLOW`, no
descriptor type/owner/mode checks, no size cap — a FIFO at the path would
even hang the collector); the usage and notification state reads were
likewise unbounded; `write_json` renamed into a predictable parent without
validating it; and `notify-send` was resolved through the inherited
`PATH`.

## Decision

**`bin/zhipu_secure.py`** owns the boundaries; every other module goes
through it:

- `read_json_bounded()` — `O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC`
  open (`O_NONBLOCK` is a no-op on regular files but makes a FIFO/device
  open instantly instead of hanging for a writer), then fstat checks:
  regular file, owned by the current user, no group/world write, size and
  streamed read capped at 1 MiB. Any refusal parses as `{}` — fail-closed,
  never an exception path callers can forget to handle.
- `write_json_atomic()` — the parent directory is opened (`O_DIRECTORY |
  O_NOFOLLOW`) and held as a `dir_fd`, verified (directory, current user,
  no group/world write); the 0600 temp file is created with `O_EXCL`
  inside that descriptor and `os.replace`d with `src_dir_fd`/`dst_dir_fd`,
  so a swapped parent path cannot redirect the destination. Violations
  raise `SecureIOError` (an `OSError`) — the usage write fails loudly
  rather than writing somewhere untrusted.
- `notify_send_executable()` — candidates limited to
  `/usr/bin/notify-send` and `/usr/local/bin/notify-send`, `lstat`-checked
  (regular, root-owned, not group/world-writable, executable). The
  inherited `PATH` is never consulted; a missing or untrusted binary
  returns `None` and notifications are silently disabled (the panel is
  unaffected — consistent with notify-send being optional).

The SQLite history database is created by the sqlite3 library itself and
holds only chart aggregates; it keeps plain `sqlite3.connect` (documented
residual, corruptible-but-not-security-critical).

## Consequences

- Symlink planting, FIFO hangs, foreign-owned or world-writable state,
  oversized payloads, parent-directory swaps, and PATH hijacking at the
  reviewed boundaries are all refused.
- Legitimate deployments are unaffected: user-owned 0600/0644 files in
  user-owned 0700/0755 directories pass every check.
- Nine tests lock the refusals (symlink, world-writable file/dir, oversize,
  FIFO, foreign owner) and the happy paths.
