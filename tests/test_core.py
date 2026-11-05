import logging
import unittest

from handler_mount_point_guard import (
    clear_all,
    is_mounted,
    mount_once,
    unmount,
)


class _ListHandler(logging.Handler):
    """Records records in a list so tests do not depend on stream state."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class MountOnceTests(unittest.TestCase):
    def setUp(self):
        clear_all()
        self.logger = logging.getLogger("test.guard")
        self.logger.handlers = []
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

    def tearDown(self):
        clear_all()
        self.logger.handlers = []

    def test_first_mount_adds_handler(self):
        handler = _ListHandler()
        returned = mount_once(self.logger, handler, "audit")
        self.assertIs(returned, handler)
        self.assertIn(handler, self.logger.handlers)
        self.assertTrue(is_mounted(self.logger, "audit"))

    def test_second_mount_is_noop_and_returns_existing(self):
        first = _ListHandler()
        second = _ListHandler()
        mount_once(self.logger, first, "audit")
        returned = mount_once(self.logger, second, "audit")
        self.assertIs(returned, first)
        self.assertIn(first, self.logger.handlers)
        self.assertNotIn(second, self.logger.handlers)
        self.assertEqual(self.logger.handlers.count(first), 1)

    def test_distinct_mount_points_are_independent(self):
        a = _ListHandler()
        b = _ListHandler()
        mount_once(self.logger, a, "audit")
        mount_once(self.logger, b, "metrics")
        self.assertIn(a, self.logger.handlers)
        self.assertIn(b, self.logger.handlers)
        self.assertTrue(is_mounted(self.logger, "audit"))
        self.assertTrue(is_mounted(self.logger, "metrics"))

    def test_same_mount_point_on_different_loggers(self):
        other = logging.getLogger("test.guard.other")
        other.handlers = []
        other.propagate = False
        a = _ListHandler()
        b = _ListHandler()
        mount_once(self.logger, a, "audit")
        mount_once(other, b, "audit")
        self.assertIn(a, self.logger.handlers)
        self.assertIn(b, other.handlers)
        self.assertNotIn(b, self.logger.handlers)

    def test_mount_point_may_be_a_class(self):
        class Marker:
            pass

        handler = _ListHandler()
        mount_once(self.logger, handler, Marker)
        self.assertTrue(is_mounted(self.logger, Marker))

    def test_unhashable_mount_point_raises(self):
        handler = _ListHandler()
        with self.assertRaises(TypeError):
            mount_once(self.logger, handler, ["not", "hashable"])

    def test_non_handler_raises(self):
        with self.assertRaises(TypeError):
            mount_once(self.logger, object(), "audit")

    def test_non_logger_raises(self):
        handler = _ListHandler()
        with self.assertRaises(TypeError):
            mount_once("not a logger", handler, "audit")

    def test_unmount_removes_and_returns_handler(self):
        handler = _ListHandler()
        mount_once(self.logger, handler, "audit")
        removed = unmount(self.logger, "audit")
        self.assertIs(removed, handler)
        self.assertNotIn(handler, self.logger.handlers)
        self.assertFalse(is_mounted(self.logger, "audit"))

    def test_unmount_absent_returns_none(self):
        self.assertIsNone(unmount(self.logger, "never-mounted"))

    def test_remount_after_unmount_uses_new_handler(self):
        first = _ListHandler()
        second = _ListHandler()
        mount_once(self.logger, first, "audit")
        unmount(self.logger, "audit")
        returned = mount_once(self.logger, second, "audit")
        self.assertIs(returned, second)
        self.assertIn(second, self.logger.handlers)
        self.assertNotIn(first, self.logger.handlers)

    def test_is_mounted_does_not_see_direct_add_handler(self):
        # The guard only tracks its own mounts; a direct addHandler is invisible.
        stray = _ListHandler()
        self.logger.addHandler(stray)
        self.assertFalse(is_mounted(self.logger, "audit"))

    def test_clear_all_forgets_registry_but_keeps_handlers(self):
        handler = _ListHandler()
        mount_once(self.logger, handler, "audit")
        clear_all()
        self.assertFalse(is_mounted(self.logger, "audit"))
        self.assertIn(handler, self.logger.handlers)


if __name__ == "__main__":
    unittest.main()
