"""Local-only real UI -> existing HTTP payment route -> isolated Mock inventory demo."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import sys
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend/src'))


def create_app(scenario, target):
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from closedloop.core.config import get_config
    from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
    from closedloop.execution import mock_executor as executor

    seed, runtime = target / 'seed', target / 'runtime'
    seed.mkdir(parents=True)
    ids = ['review_available'] + (['review_sold_out'] if scenario == 'partial' else [])
    packages = [{'package_id': key, 'available_stock': 3, 'requires_booking': False} for key in ids]
    for name, value in {'restaurants.json': [], 'reservations.json': [], 'add_ons.json': [],
                        'activities.json': [{'id': 'review_activity', 'packages': packages}]}.items():
        (seed / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    config = get_config()
    config.data.MOCK_DB_REPO_DIR = str(seed)
    config.data.MOCK_DB_RW_DIR = str(runtime)
    config.data.FORCE_OUT_OF_STOCK_IDS = ''
    config.logging.LOG_DIR = str(target / 'logs')
    config.EXECUTION_SIM_DELAY_MAX_SECS = 0
    import main as application

    app = FastAPI(title='Local payment review')
    # Reuse the production route itself; the model/chat endpoints are not exposed.
    route = next(r for r in application.app.routes if getattr(r, 'path', '') == '/execution/{execution_id}/commit')
    app.router.routes.append(route)
    fixture = None
    fixture_lock = asyncio.Lock()

    @app.post('/review/fixture')
    async def prepare_fixture():
        nonlocal fixture
        async with fixture_lock:
            if fixture is not None:
                return fixture
            steps = [ExecuteStep(item_id=key, item_type='activity', start_time=f'{12+i}:00',
                                 end_time=f'{13+i}:00', user_touched=True) for i, key in enumerate(ids)]
            key = await executor.start_execution(ExecuteRequest(plan_id='plan_review', mode='preview', steps=steps))
            events = [event async for event in executor.iter_events(key)]
            (target / 'preview-events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')
            # Deterministic stock change after preview, before the real browser payment request.
            if scenario == 'partial':
                path = runtime / 'activities.json'
                data = json.loads(path.read_text(encoding='utf-8'))
                data[0]['packages'][1]['available_stock'] = 0
                path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            plan = {'plan_id': 'plan_review', 'title': '隔离库存支付验收', 'selected_item_ids': ids,
                    'total_cost': len(ids) * 10, 'total_duration_minutes': len(ids) * 60,
                    'steps': [{'order_id': str(i+1), 'duration_minutes': 60, 'note': '固定验收输入',
                               'start_time': step.start_time, 'end_time': step.end_time,
                               'item': {'id': step.item_id, 'type': 'activity', 'name': step.item_id,
                                        'location': '隔离测试', 'distance_km': 0, 'cost': 10}}
                              for i, step in enumerate(steps)]}
            fixture = {'id': 'payment-review-' + scenario, 'title': '支付联调验收：' + scenario,
                       'messages': [{'type': 'ai', 'content': '这是固定计划输入的支付联调，未调用规划模型。'}],
                       'updatedAt': 1, 'itinerary': {'status': 'ok', 'plans': [plan]},
                       'confirmation': {'status': 'pending_payment', 'execution_id': key,
                          'payment_status': 'pending', 'commit_status': 'not_started',
                          'execution_command': {'execution_id': key, 'plan_id': 'plan_review',
                                                'pricing_summary': {'original_amount': len(ids)*10}}}}
            (target / 'fixture.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding='utf-8')
            return fixture

    @app.get('/review/inventory')
    async def inventory():
        path = runtime / 'activities.json'
        return {'scenario': scenario, 'inventory': json.loads(path.read_text()) if path.exists() else None}

    @app.get('/review', response_class=HTMLResponse)
    async def landing():
        return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>支付浏览器联调</title>
<h1>隔离库存支付联调</h1><p>固定计划输入；真实页面、现有 HTTP 支付路由与 Mock 文件库存。无规划模型、无真实支付。</p>
<p>点击进入后，在支付面板输入 Mock 密码 111111，再核对页面结果和库存。</p>
<button id="start">准备固定订单并进入现有页面</button> <a href="/review/inventory">查看实际库存</a><p id="status"></p>
<script>document.getElementById('start').onclick=async()=>{
try {const r=await fetch('/review/fixture',{method:'POST'});if(!r.ok)throw Error('准备失败');const s=await r.json();
localStorage.setItem('closedloop-sessions',JSON.stringify({state:{sessions:[s],currentSessionId:s.id},version:0}));
location.href='/app';}catch(e){document.getElementById('status').textContent=String(e)}};</script></html>'''

    @app.get('/app')
    async def frontend():
        return FileResponse(ROOT / 'frontend/dist/index.html')

    app.mount('/assets', StaticFiles(directory=ROOT / 'frontend/dist/assets'), name='assets')
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', choices=['success', 'partial'], default='success')
    parser.add_argument('--port', type=int, default=18765)
    args = parser.parse_args()
    if not (ROOT / 'frontend/dist/index.html').exists():
        parser.error('Build frontend first: cd frontend; npm run build')
    target = ROOT / 'payment-runs' / ('browser-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:6])
    app = create_app(args.scenario, target)
    sources = [Path(__file__), ROOT / 'backend/src/closedloop/execution/mock_executor.py',
               ROOT / 'backend/src/main.py', ROOT / 'frontend/src/features/itinerary/ui/PlanPanel.tsx',
               ROOT / 'frontend/src/features/itinerary/store/useItineraryStore.ts']
    metadata = {'scenario': args.scenario,
        'revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'dirty': bool(subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip()),
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'build_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (ROOT / 'frontend/dist').rglob('*') if p.is_file()}}
    (target / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print('Evidence:', target, flush=True)
    print(f'Open http://127.0.0.1:{args.port}/review', flush=True)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
