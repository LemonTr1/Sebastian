import unittest

from src.tools.toolkits.cron_schedule import CRON_SCHEDULE  # noqa: F401
from src.tools.tools_registry import get_tools_registry


class TestCronHitl(unittest.TestCase):
    def test_schedule_cron_requires_hitl(self):
        registry = get_tools_registry()
        self.assertTrue(registry.is_hitl_tool("schedule_cron"))
        self.assertFalse(registry.is_hitl_tool("list_crons"))
        self.assertFalse(registry.is_hitl_tool("cancel_cron"))


if __name__ == "__main__":
    unittest.main()
