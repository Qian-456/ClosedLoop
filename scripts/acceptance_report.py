"""将执行状态回归转换为可读证据；仅运行固定单元测试，不调用模型或启动服务。"""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import html
from importlib import metadata
import inspect
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
from uuid import uuid4


ROOT = Path(os.path.abspath(os.path.dirname(__file__))).parent
SOURCE = ROOT / "backend" / "src"
MODULES = {
    "tests.test_execute_tool_consistency_payment_gate": "待支付门控、超额费用拦截、失败进入补齐",
    "tests.test_execute_tool_hitl_timeout": "需用户选择时及时返回补齐状态",
    "tests.test_adjust_and_execute_update": "补齐成功/仍失败的状态回写",
    "tests.test_execute_cost_consistency": "礼物配送费与方案费用口径",
}
LIMITATION = (
    "固定模拟事件的单元回归：验证状态与费用规则。"
    "未验证真实模型、浏览器、商家预约、支付扣款或端到端恢复；"
    "通过比例不是业务成功率，耗时不是接口延迟。"
)
TITLES = {
    "test_execute_itinerary_should_fail_inconsistency_when_overpay": "实际预订费用超额时拦截成功状态",
    "test_execute_itinerary_should_turn_to_needs_fixup_when_has_failures": "条目预订失败时进入补齐流程",
    "test_pending_confirmation_should_return_needs_fixup_immediately": "需要用户选择时及时返回补齐状态",
    "test_non_gift_cost_should_use_plan_item_cost": "普通项目按已确认方案费用计算",
}


class EvidenceResult(unittest.TextTestResult):
    """保留逐项结果；跳过、预期失败均不算完整验收通过。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []

    def startTest(self, test):
        self.started = time.perf_counter()
        super().startTest(test)

    def record(self, test, status):
        method = getattr(test, getattr(test, "_testMethodName", ""), None)
        source = inspect.getsourcefile(method) if method else None
        try:
            relative = Path(source).resolve().relative_to(ROOT).as_posix() if source else ""
            line = inspect.getsourcelines(method)[1] if source else None
        except (ValueError, OSError, TypeError):
            relative, line = "", None
        self.rows.append({
            "test_id": test.id(), "status": status,
            "description": TITLES.get(test.id().split(".")[-1]) or test.shortDescription() or test.id().split(".")[-1],
            "seconds": round(time.perf_counter() - self.started, 6),
            "source": relative, "line": line,
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.record(subtest, "failed")


def git_value(*args):
    """仅读取版本状态；没有 Git 时不伪造提交信息。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True,
            text=True, encoding="utf-8", timeout=5, check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def source_fingerprint():
    """包含未提交源码的哈希，避免将工作树测试误认成纯提交验证。"""
    files = {}
    for path in sorted(SOURCE.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    files["scripts/acceptance_report.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return files


def summarize(result):
    passed = sum(row["status"] == "passed" for row in result.rows)
    # 零测试、跳过、导入错误及不完整记录都不能生成绿色报告。
    complete = (
        result.testsRun > 0 and result.wasSuccessful()
        and passed == result.testsRun and len(result.rows) == result.testsRun
        and not result.skipped and not result.expectedFailures
    )
    return {"passed": passed, "tests_run": result.testsRun, "complete": complete}


def render_report(report):
    """静态 HTML 无外部资源；测试描述与路径全部转义。"""
    escape = html.escape
    rows = []
    for row in report["tests"]:
        label = escape(row["source"] or "测试载入失败，查看 unittest.txt")
        if row["source"]:
            label += f":{row['line']}"
        rows.append(
            f"<tr><td>{escape(row['status'])}</td><td>{escape(row['description'])}"
            f"<details><summary>测试标识与实现位置</summary><code>{escape(row['test_id'])}"
            f"</code><p>{label}</p></details></td></tr>"
        )
    summary = report["summary"]
    status = "全部通过" if summary["complete"] else "未完整通过"
    color = "#167047" if summary["complete"] else "#a13226"
    groups = "".join(f"<li>{escape(value)}</li>" for value in MODULES.values())
    return f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>ClosedLoop 回归验收报告</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 20px;
line-height:1.7;color:#192b36;background:#f6f8fa}}section{{background:white;padding:20px;margin:20px 0;
border:1px solid #dbe3e9;border-radius:12px}}table{{width:100%;border-collapse:collapse}}
td,th{{text-align:left;padding:12px;border-bottom:1px solid #ddd}}code{{overflow-wrap:anywhere}}
h1{{font-size:28px}}.status{{color:{color};font-weight:bold}}summary{{cursor:pointer}}</style>
<h1>ClosedLoop · 执行状态回归验收</h1>
<section><strong class="status">{status} · {summary['passed']} / {summary['tests_run']} 项</strong>
<p>{escape(LIMITATION)}</p><p>生成时间：{escape(report['generated_at'])}</p>
<p>提交：<code>{escape(report['revision'] or '未知')}</code> · 工作树有改动：{report['dirty']}</p>
<p>Python {escape(report['python'])} · {escape(report['platform'])}</p></section>
<section><h2>检查什么</h2><ul>{groups}</ul>
<p>每项“通过”表示对应测试断言通过，不表示实际订单已付款。</p></section>
<section><h2>逐项证据</h2><table><tr><th>结果</th><th>验证内容</th></tr>{''.join(rows)}</table>
<p><a href="report.json">结构化结果与源码哈希</a> · <a href="unittest.txt">测试原始输出</a></p></section>
<section><h2>如何用于面试</h2><p>先讲需求 → 约束规划 → 确认 → Mock 执行 → 失败补齐，
再选择一项检查，展示输入、状态断言和对应代码。真实浏览器流程仍需单独演示。</p></section></html>"""


def main():
    """每次生成独立产物目录，保留历史失败结果，不复用旧的成功报告。"""
    sys.path.insert(0, str(SOURCE))
    stamp = datetime.now(timezone.utc)
    target = ROOT / "acceptance-runs" / f"{stamp:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    target.mkdir(parents=True, exist_ok=False)
    output = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        suite = unittest.TestLoader().loadTestsFromNames(list(MODULES))
        result = unittest.TextTestRunner(stream=output, verbosity=2, resultclass=EvidenceResult).run(suite)
    status = git_value("status", "--porcelain")
    versions = {}
    for name in ("langchain", "langgraph", "pydantic", "fastapi"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    report = {
        "schema_version": "1.0", "generated_at": stamp.isoformat(),
        "revision": git_value("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None,
        "python": platform.python_version(), "platform": platform.system(), "dependencies": versions,
        "scope": LIMITATION, "modules": MODULES, "summary": summarize(result),
        "seconds": round(time.perf_counter() - started, 6), "tests": result.rows,
        "source_sha256": source_fingerprint(),
    }
    (target / "unittest.txt").write_text(output.getvalue(), encoding="utf-8")
    (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "index.html").write_text(render_report(report), encoding="utf-8")
    # CLI 结果路径属于命令输出，不输出配置、密钥或业务对话。
    sys.stdout.write(f"{target / 'index.html'}\n")
    return 0 if report["summary"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
