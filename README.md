# handler_mount_point_guard

Registers a `logging.Handler` at most once per mount point, even across re-imports or repeated plugin initialization.

## Usage

```python
import logging
from handler_mount_point_guard import mount_once, is_mounted, unmount

logger = logging.getLogger("myapp.audit")
handler = logging.StreamHandler()

# Safe to call from import-time code or a plugin init hook.
mount_once(logger, handler, "audit")
assert is_mounted(logger, "audit")

# Calling again with a different handler does nothing and returns the first one.
other = logging.StreamHandler()
assert mount_once(logger, other, "audit") is handler

# Remove it when you are done.
unmount(logger, "audit")
assert not is_mounted(logger, "audit")
```

## Why this exists

A module that calls `logger.addHandler(h)` at import time adds a second handler every time it is imported again: `importlib.reload`, several plugins importing the same helper, or a test suite that re-imports the module. The symptom is duplicated log lines, and it is easy to miss until a production log is three times as long as it should be.

The usual fix is a module-level `_configured = False` flag. That works until the logger or handler is created later, or until you want to undo the mount. This library keeps a small registry keyed by `(logger.name, mount_point)`, where the mount point is any hashable value the caller chooses. The handler instance is stored with the key, so `mount_once` is idempotent: a second call with the same logger and mount point returns the already-mounted handler instead of adding another.

The trade-off: the guard is process-local and only tracks mounts made through its own API. If code calls `logger.addHandler` directly, the guard will not notice, and `is_mounted` will still report `False`. Policing every direct call would mean wrapping `logging.Logger`, which is invasive and breaks pickling; keeping the guard opt-in is the deliberate choice here.

## The awkward edge

Mount points are hashable keys, not handler identities. If two different parts of your program both use the mount point `"audit"` on the same logger, the second one silently gets the first one's handler. Choose mount points that are unique to the component doing the mounting -- a module name, a class, or an enum member -- rather than a generic string.

## API

- `mount_once(logger, handler, mount_point) -> logging.Handler`
- `is_mounted(logger, mount_point) -> bool`
- `unmount(logger, mount_point) -> logging.Handler | None`
- `clear_all() -> None`

`clear_all` is intended for tests and process teardown: it forgets the registry but leaves handlers attached to their loggers.
