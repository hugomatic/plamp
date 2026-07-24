"""Descriptor-relative atomic filesystem ownership helpers."""

from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import secrets
import stat
import sys


class AtomicExchangeUnsupported(OSError):
    pass


def exchange_paths(first: Path, second: Path) -> None:
    if not sys.platform.startswith("linux"):
        raise AtomicExchangeUnsupported("atomic exchange requires Linux renameat2")
    exchange_at(-100, os.fspath(first), -100, os.fspath(second))


def exchange_at(first_fd: int, first: str, second_fd: int, second: str) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise AtomicExchangeUnsupported("renameat2 is unavailable")
    result = rename(first_fd, os.fsencode(first), second_fd, os.fsencode(second), 2)
    if result != 0:
        value = ctypes.get_errno()
        if value in {errno.ENOSYS, errno.ENOTSUP, errno.EINVAL}:
            raise AtomicExchangeUnsupported(os.strerror(value))
        raise OSError(value, os.strerror(value))


def _identity(parent_fd: int, name: str) -> tuple[int, int, int]:
    details = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    return details.st_dev, details.st_ino, details.st_mode


def _remove_claimed(parent_fd: int, name: str, mode: int) -> None:
    if stat.S_ISDIR(mode):
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        try:
            for child in tuple(os.listdir(descriptor)):
                details = os.stat(child, dir_fd=descriptor, follow_symlinks=False)
                if not remove_owned_entry_at(
                    descriptor, child, (details.st_dev, details.st_ino)
                ):
                    raise OSError(errno.ESTALE, f"owned cleanup child moved: {child}")
        finally:
            os.close(descriptor)
        os.rmdir(name, dir_fd=parent_fd)
    else:
        os.unlink(name, dir_fd=parent_fd)


def remove_owned_entry_at(
    parent_fd: int, preferred_name: str, identity: tuple[int, int]
) -> bool:
    """Atomically claim and remove one inode, finding it if concurrently moved."""

    active_claims: set[str] = set()
    for _attempt in range(4):
        candidates = (preferred_name, *(
            name for name in os.listdir(parent_fd)
            if name != preferred_name and name not in active_claims
        ))
        retry = False
        for candidate in candidates:
            try:
                device, inode, mode = _identity(parent_fd, candidate)
            except FileNotFoundError:
                continue
            if (device, inode) != identity:
                continue
            placeholder = f".plamp-owned-{secrets.token_hex(8)}"
            active_claims.add(placeholder)
            if stat.S_ISDIR(mode):
                os.mkdir(placeholder, dir_fd=parent_fd)
                remove_placeholder = lambda: os.rmdir(placeholder, dir_fd=parent_fd)
            else:
                placeholder_fd = os.open(
                    placeholder, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
                    0o600, dir_fd=parent_fd,
                )
                os.close(placeholder_fd)
                remove_placeholder = lambda: os.unlink(placeholder, dir_fd=parent_fd)
            exchanged = False
            try:
                exchange_at(parent_fd, candidate, parent_fd, placeholder)
                exchanged = True
                claimed_device, claimed_inode, claimed_mode = _identity(parent_fd, placeholder)
                if (claimed_device, claimed_inode) != identity:
                    exchange_at(parent_fd, candidate, parent_fd, placeholder)
                    exchanged = False
                    retry = True
                    break
                _remove_claimed(parent_fd, placeholder, claimed_mode)
                exchanged = False
                if stat.S_ISDIR(mode):
                    os.rmdir(candidate, dir_fd=parent_fd)
                else:
                    os.unlink(candidate, dir_fd=parent_fd)
                return True
            finally:
                if exchanged:
                    try:
                        exchange_at(parent_fd, candidate, parent_fd, placeholder)
                    except OSError:
                        pass
                try:
                    remove_placeholder()
                except FileNotFoundError:
                    pass
                active_claims.discard(placeholder)
        if not retry:
            return False
    return False
