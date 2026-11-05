"""Prevent duplicate logging handler registration across re-imports and plugins.

The problem: a module that calls ``logging.getLogger(name).addHandler(handler)``
at import time will add another handler every time it is imported again, e.g.
after ``importlib.reload`` or when several plugins each import the same helper.
The usual fix is a module-level boolean, but that breaks when the logger or the
handler is created later, and it gives no way to undo the mount.

This module keeps a registry keyed by ``(logger_name, mount_point)``.  A mount
point is any hashable identifier chosen by the caller -- a string, an enum, a
class, a tuple.  The handler instance is stored with the mount point, so
``mount_once`` is idempotent: calling it again with the same logger and mount
point is a no-op and returns the already-mounted handler.

Design decision: the registry lives in this module, not on the logger or the
handler.  Attaching state to ``logging.Logger`` or ``logging.Handler`` objects
is fragile because both are frequently copied, pickled, or wrapped.  A private
module-level dict is easy to reason about and easy to clear in tests.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Hashable, Optional, Tuple

# Key: (logger_name, mount_point).  Value: the handler currently mounted there.
# A plain dict is used deliberately: the guard is process-local and the number
# of mount points is tiny, so a lock would add complexity without benefit.
_mounts: Dict[Tuple[str, Hashable], logging.Handler] = {}


def _key(logger: logging.Logger, mount_point: Hashable) -> Tuple[str, Hashable]:
    """Build the registry key for a logger and mount point.

    ``logger.name`` is used rather than the logger object so that two calls
    with the same name but different ``Logger`` instances (which can happen
    after ``logging.getLogger`` is monkey-patched or after a reload) still
    collide, which is the whole point of the guard.
    """
    return (logger.name, mount_point)


def mount_once(
    logger: logging.Logger,
    handler: logging.Handler,
    mount_point: Hashable,
) -> logging.Handler:
    """Attach ``handler`` to ``logger`` unless one is already mounted.

    Returns the handler that is mounted at ``mount_point`` after the call.
    If a handler is already registered there, it is returned unchanged and
    ``handler`` is left untouched (not added, not closed).  This makes the
    function safe to call from import-time code and from plugin init hooks.

    ``mount_point`` must be hashable; a string such as ``"audit"`` or a class
    object works well.  The same mount point on two different loggers is two
    independent slots.
    """
    if not isinstance(logger, logging.Logger):
        raise TypeError("logger must be a logging.Logger instance")
    if not isinstance(handler, logging.Handler):
        raise TypeError("handler must be a logging.Handler instance")
    if not isinstance(mount_point, Hashable):
        raise TypeError("mount_point must be hashable")

    key = _key(logger, mount_point)
    existing = _mounts.get(key)
    if existing is not None:
        return existing

    logger.addHandler(handler)
    _mounts[key] = handler
    return handler


def is_mounted(logger: logging.Logger, mount_point: Hashable) -> bool:
    """Return True if a handler is registered at ``mount_point`` on ``logger``.

    This checks the guard's registry, not the logger's handler list.  The two
    can diverge if someone calls ``logger.addHandler`` directly; the guard does
    not try to police that, it only prevents its own callers from duplicating.
    """
    return _key(logger, mount_point) in _mounts


def unmount(logger: logging.Logger, mount_point: Hashable) -> Optional[logging.Handler]:
    """Remove and return the handler mounted at ``mount_point``, if any.

    Returns ``None`` when nothing was mounted.  The handler is removed from
    the logger as well as from the registry, so a later ``mount_once`` call
    with a fresh handler will succeed.
    """
    key = _key(logger, mount_point)
    handler = _mounts.pop(key, None)
    if handler is None:
        return None
    logger.removeHandler(handler)
    return handler


def clear_all() -> None:
    """Forget every mount point without touching the loggers.

    Intended for tests and for process teardown.  Loggers keep their handlers;
    only the guard's bookkeeping is cleared.
    """
    _mounts.clear()
