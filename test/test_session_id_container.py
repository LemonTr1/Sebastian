# 测 SessionIdContainer 的取/设/默认与会话级单例行为
import unittest

from src.utils.session_id_container import (
    SESSION_ID_CONTAINER,
    SessionIdContainer,
    get_session_id_container,
)


class TestSessionIdContainer(unittest.TestCase):
    def test_default_empty(self):
        self.assertEqual(SessionIdContainer().get_session_id(), "")

    def test_custom_default(self):
        c = SessionIdContainer("abc-123")
        self.assertEqual(c.get_session_id(), "abc-123")

    def test_set_get_roundtrip(self):
        c = SessionIdContainer()
        c.set_session_id("sess-xyz")
        self.assertEqual(c.get_session_id(), "sess-xyz")

    def test_set_overwrites(self):
        c = SessionIdContainer("first")
        c.set_session_id("second")
        self.assertEqual(c.get_session_id(), "second")

    def test_singleton_identity(self):
        # 单例具对象，修改对后续获取可见
        container = get_session_id_container()
        self.assertIs(container, SESSION_ID_CONTAINER)
        container.set_session_id("singleton-sid")
        self.assertEqual(SESSION_ID_CONTAINER.get_session_id(), "singleton-sid")


if __name__ == "__main__":
    unittest.main()