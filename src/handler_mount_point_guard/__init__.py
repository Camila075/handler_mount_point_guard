"""Public API for handler_mount_point_guard.

Exports:
    mount_once: Register a logging handler at most once per mount point.
    is_mounted: Check whether a handler is currently mounted at a mount point.
    unmount: Remove a handler from a mount point (does nothing if absent).
    clear_all: Remove all tracked mounts (test helper).
"""

from .core import mount_once, is_mounted, unmount, clear_all

__all__ = ["mount_once", "is_mounted", "unmount", "clear_all"]
