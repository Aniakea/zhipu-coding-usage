"""Fail-closed local IO boundaries (ADR-0010).

Every predictable path this plugin touches — the API-key config, the
imported OpenCode credential file, the usage and notification state — is
read through ``read_json_bounded`` (``O_NOFOLLOW``, regular-file/owner/
mode checks on the opened descriptor, hard byte cap) and written through
``write_json_atomic`` (parent directory verified via a held ``dir_fd``;
temp file created and renamed inside that directory only).
``notify_send_executable`` resolves notify-send from a root-owned
absolute-path allowlist instead of the inherited ``PATH``.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
from pathlib import Path
from typing import Any, Final

_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)
_MAX_JSON_BYTES: Final = 1_048_576
_NOTIFY_SEND_CANDIDATES: Final = ("/usr/bin/notify-send", "/usr/local/bin/notify-send")


class SecureIOError(OSError):
    """A predictable-path boundary check refused the operation."""


def _fd_is_trusted(fd: int, expect_dir: bool) -> bool:
    info = os.fstat(fd)
    if expect_dir:
        if not stat.S_ISDIR(info.st_mode):
            return False
    elif not stat.S_ISREG(info.st_mode):
        return False
    return info.st_uid == os.geteuid() and info.st_mode & 0o022 == 0


def read_json_bounded(path: Path, max_bytes: int = _MAX_JSON_BYTES) -> dict[str, Any]:
    """Parse a trusted-owned JSON object, or ``{}`` on any refusal.

    Refuses: symlinked final component, non-regular files, files not owned
    by the current user, group/world-writable files, payloads over
    ``max_bytes``, and anything that does not parse into a JSON object.
    """
    try:
        # O_NONBLOCK is a no-op on regular files but makes a FIFO or device
        # at this path open instantly instead of hanging for a writer; the
        # descriptor type check below then refuses it.
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        return {}
    try:
        if not _fd_is_trusted(fd, expect_dir=False):
            return {}
        if os.fstat(fd).st_size > max_bytes:
            return {}
        chunks: list[bytes] = []
        total = 0
        while total <= max_bytes:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total == 0 or total > max_bytes:
            return {}
        parsed = json.loads(b"".join(chunks).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    finally:
        os.close(fd)
    return parsed if isinstance(parsed, dict) else {}


def write_json_atomic(path: Path, payload: dict[str, Any], max_bytes: int = _MAX_JSON_BYTES) -> None:
    """Atomically write JSON inside a verified, user-owned directory.

    The parent is opened and checked (directory, current user, no
    group/world write) and held as a ``dir_fd``; the temp file is created
    and ``os.replace``d within that descriptor, so a swapped parent path
    cannot redirect the destination.
    """
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(data) > max_bytes:
        raise SecureIOError(f"payload exceeds {max_bytes} bytes")

    path.parent.mkdir(parents=True, exist_ok=True)
    dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | _NOFOLLOW | os.O_CLOEXEC)
    tmp_name = f".tmp-{os.getpid()}-{dt.datetime.now().strftime('%H%M%S%f')}.json"
    try:
        if not _fd_is_trusted(dir_fd, expect_dir=True):
            raise SecureIOError(f"untrusted state directory: {path.parent}")
        fd = os.open(
            tmp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=dir_fd,
        )
        try:
            os.fchmod(fd, 0o600)
            written = 0
            while written < len(data):
                written += os.write(fd, data[written:])
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_name, path.name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
    finally:
        os.close(dir_fd)


def notify_send_executable() -> str | None:
    """A root-owned, non-group/world-writable notify-send, or ``None``.

    The inherited ``PATH`` is never consulted; a missing or untrusted
    binary simply disables notifications (the panel is unaffected).
    """
    for candidate in _NOTIFY_SEND_CANDIDATES:
        try:
            info = os.lstat(candidate)
        except OSError:
            continue
        if not stat.S_ISREG(info.st_mode):
            continue
        if info.st_uid != 0 or info.st_mode & 0o022:
            continue
        if os.access(candidate, os.X_OK):
            return candidate
    return None
