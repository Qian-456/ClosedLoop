"""Run actual Mock execution against a new isolated inventory and show the evidence."""
import asyncio
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))
from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
from closedloop.execution import mock_executor as executor


async def run(target):
    seed, runtime = target / 'seed', target / 'runtime'
    seed.mkdir()
    fixtures = {'restaurants.json': [], 'add_ons.json': [], 'reservations.json': [],
                'activities.json': [{'id': 'demo-activity', 'packages': [
                    {'package_id': 'demo-package', 'available_stock': 3, 'requires_booking': False}]}]}
    for name, value in fixtures.items():
        (seed / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    config = SimpleNamespace(EXECUTION_SIM_DELAY_MAX_SECS=0,
        data=SimpleNamespace(MOCK_DB_REPO_DIR=str(seed), MOCK_DB_RW_DIR=str(runtime), FORCE_OUT_OF_STOCK_IDS=''))
    def stock():
        return json.loads((runtime / 'activities.json').read_text(encoding='utf-8'))[0]['packages'][0]['available_stock']
    with patch.object(executor, 'get_config', return_value=config):
        request = ExecuteRequest(plan_id='isolated-demo', mode='preview', steps=[
            ExecuteStep(item_id='demo-package', item_type='activity', start_time='12:00', end_time='13:00')])
        key = await executor.start_execution(request)
        events = [e async for e in executor.iter_events(key)]
        after_preview = stock()
        wrong = await executor.commit_execution_payment(key, 'incorrect-demo-password')
        after_wrong = stock()
        results = await asyncio.wait_for(asyncio.gather(*[
            executor.commit_execution_payment(key, '111111') for _ in range(8)]), timeout=10)
        after_commit = stock()
        replay = await executor.commit_execution_payment(key, '111111')
        after_replay = stock()
    checks = {'preview_does_not_deduct': after_preview == 3,
              'wrong_password_does_not_deduct': after_wrong == 3 and wrong['payment_status'] == 'failed',
              'concurrent_commit_deducts_once': after_commit == 2,
              'all_eight_results_equal': all(r == results[0] for r in results),
              'commit_succeeded': all(r['commit_status'] == 'success' for r in results),
              'retry_replays_without_deduction': replay == results[0] and after_replay == 2,
              'seed_unchanged': json.loads((seed / 'activities.json').read_text()) == fixtures['activities.json']}
    return {'checks': checks, 'passed': all(checks.values()), 'concurrent_requests': 8,
            'inventory': {'initial': 3, 'after_preview': after_preview, 'after_wrong_password': after_wrong,
                          'after_concurrent_commit': after_commit, 'after_retry': after_replay},
            'preview_events': events, 'commit_results': results, 'retry_result': replay}


def main():
    target = ROOT / 'payment-runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:6])
    target.mkdir(parents=True)
    report = {'passed': False}
    try:
        report.update(asyncio.run(run(target)))
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
    report['revision'] = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    report['dirty'] = bool(subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip())
    report['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__), ROOT / 'backend/src/closedloop/execution/mock_executor.py')}
    data = json.dumps(report, ensure_ascii=False, indent=2)
    (target / 'report.json').write_text(data, encoding='utf-8')
    status = '通过' if report['passed'] else '未通过'
    (target / 'index.html').write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Mock 支付重复提交验收</title><style>body{{font:16px/1.7 system-ui;max-width:960px;margin:40px auto;padding:16px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style>
<h1>Mock 支付重复提交：{status}</h1><p>真实 Mock 执行器 + 隔离 JSON 库存；不是银行支付、HTTP 并发或模型端到端测试。</p>
<p>预览库存 3 → 错误密码 3 → 同一命令并发提交 8 次后 2 → 再次提交仍为 2。以下 JSON 为本次实测，失败时以错误为准。</p>
<p><a href="report.json">原始报告</a> · <a href="seed/activities.json">初始库存</a> · <a href="runtime/activities.json">执行后库存</a></p>
<pre>{html.escape(data)}</pre></html>''', encoding='utf-8')
    print(target / 'index.html')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
