"""验证报告不会把零测试、跳过或失败伪装为成功。"""

import io
import unittest

from scripts.acceptance_report import EvidenceResult, summarize, render_report


class TestAcceptanceReport(unittest.TestCase):
    def result_for(self, case):
        return unittest.TextTestRunner(stream=io.StringIO(), resultclass=EvidenceResult).run(
            unittest.TestSuite([case]) if case else unittest.TestSuite()
        )

    def test_empty_suite_is_not_complete(self):
        self.assertFalse(summarize(self.result_for(None))["complete"])

    def test_failure_and_skip_are_not_complete(self):
        class Failure(unittest.TestCase):
            def runTest(self):
                self.fail("模拟断言失败")

        class Skipped(unittest.TestCase):
            def runTest(self):
                self.skipTest("模拟缺少前置条件")

        for case in (Failure(), Skipped()):
            with self.subTest(case=type(case).__name__):
                self.assertFalse(summarize(self.result_for(case))["complete"])

    def test_failed_subtest_is_not_complete(self):
        class Failure(unittest.TestCase):
            def runTest(self):
                with self.subTest(value=1):
                    self.fail("模拟子测试失败")

        self.assertFalse(summarize(self.result_for(Failure()))["complete"])

    def test_html_escapes_test_content_and_shows_scope(self):
        report = {
            "summary": {"complete": False, "passed": 0, "tests_run": 1},
            "generated_at": "test", "revision": None, "dirty": None,
            "python": "test", "platform": "test", "tests": [{
                "status": "error", "description": "<script>alert(1)</script>",
                "test_id": "test", "source": "", "line": None,
            }],
        }
        page = render_report(report)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("未完整通过", page)
        self.assertIn("通过比例不是业务成功率", page)


if __name__ == "__main__":
    unittest.main()
