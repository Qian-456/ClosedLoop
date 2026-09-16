"""Real Mock executor + isolated JSON inventory; no fabricated execution events."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
from closedloop.execution import mock_executor as executor


class PaymentIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed = self.root / 'seed'
        self.runtime = self.root / 'runtime'
        self.seed.mkdir()
        self.fixtures = {'restaurants.json': [], 'reservations.json': [], 'add_ons.json': [],
                         'activities.json': [{'id': 'activity', 'packages': [
                             {'package_id': 'available', 'available_stock': 3, 'requires_booking': False},
                             {'package_id': 'sold_out', 'available_stock': 0, 'requires_booking': False}]}]}
        for name, data in self.fixtures.items():
            (self.seed / name).write_text(json.dumps(data), encoding='utf-8')
        config = SimpleNamespace(EXECUTION_SIM_DELAY_MAX_SECS=0,
            data=SimpleNamespace(MOCK_DB_REPO_DIR=str(self.seed), MOCK_DB_RW_DIR=str(self.runtime),
                                 FORCE_OUT_OF_STOCK_IDS=''))
        self.config_patch = patch.object(executor, 'get_config', return_value=config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def stock(self):
        return json.loads((self.runtime / 'activities.json').read_text(encoding='utf-8'))[0]['packages'][0]['available_stock']

    async def preview(self, *ids):
        request = ExecuteRequest(plan_id='isolated-payment-test', mode='preview', steps=[
            ExecuteStep(item_id=i, item_type='activity', start_time='12:00', end_time='13:00',
                        user_touched=True) for i in ids])
        key = await executor.start_execution(request)
        self.events = [e async for e in executor.iter_events(key)]
        self.assertEqual(self.stock(), 3, 'preview must not deduct inventory')
        return key

    async def test_repeated_success_replays_result_and_deducts_once(self):
        key = await self.preview('available')
        first = await executor.commit_execution_payment(key, '111111')
        second = await executor.commit_execution_payment(key, '111111')
        self.assertEqual(first['commit_status'], 'success')
        self.assertEqual(first, second)
        self.assertEqual(self.stock(), 2)
        first['items'].clear()
        self.assertTrue((await executor.commit_execution_payment(key, '111111'))['items'])
        self.assertEqual(json.loads((self.seed / 'activities.json').read_text()), self.fixtures['activities.json'])

    async def test_concurrent_submissions_share_one_result(self):
        key = await self.preview('available')
        results = await asyncio.wait_for(asyncio.gather(*[
            executor.commit_execution_payment(key, '111111') for _ in range(8)]), timeout=2)
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(results[0]['commit_status'], 'success')
        self.assertEqual(self.stock(), 2)

    async def test_partial_failure_retry_does_not_rededuct_success(self):
        key = await self.preview('available', 'sold_out')
        first = await executor.commit_execution_payment(key, '111111')
        second = await executor.commit_execution_payment(key, '111111')
        self.assertEqual(first['commit_status'], 'failed')
        self.assertEqual(first, second)
        self.assertEqual(self.stock(), 2)
        self.assertEqual([i['item_id'] for i in first['failures']], ['sold_out'])

    async def test_wrong_password_and_unknown_command_are_not_paid(self):
        key = await self.preview('available')
        wrong = await executor.commit_execution_payment(key, 'wrong')
        unknown = await executor.commit_execution_payment('missing-command', '111111')
        self.assertEqual(wrong['payment_status'], 'failed')
        self.assertEqual(unknown['payment_status'], 'failed')
        self.assertEqual(self.stock(), 3)
        self.assertEqual((await executor.commit_execution_payment(key, '111111'))['commit_status'], 'success')

    async def test_cancelled_waiter_does_not_cancel_commit(self):
        key = await self.preview('available')
        request = asyncio.create_task(executor.commit_execution_payment(key, '111111'))
        await asyncio.sleep(0)
        request.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await request
        result = await asyncio.wait_for(executor.commit_execution_payment(key, '111111'), timeout=2)
        self.assertEqual(result['commit_status'], 'success')
        self.assertEqual(self.stock(), 2)

    async def test_distinct_commands_with_same_steps_do_not_share_event_queue(self):
        first = await self.preview('available')
        second = await self.preview('available')
        results = await asyncio.wait_for(asyncio.gather(
            executor.commit_execution_payment(first, '111111'),
            executor.commit_execution_payment(second, '111111')), timeout=2)
        self.assertTrue(all(r['commit_status'] == 'success' for r in results))
        self.assertNotEqual(results[0]['commit_execution_id'], results[1]['commit_execution_id'])
        self.assertEqual(self.stock(), 1)

    async def test_incomplete_stream_is_not_success(self):
        key = await self.preview('available')
        async def incomplete(_key):
            yield {'type': 'done', 'data': {'status': 'not_found'}}
        with patch.object(executor, 'iter_events', new=incomplete), \
             patch.object(executor, 'start_execution', return_value='missing-execution'):
            result = await executor.commit_execution_payment(key, '111111')
        self.assertEqual(result['commit_status'], 'failed')
        self.assertEqual(self.stock(), 3)

    async def test_internal_error_is_cached_as_uncertain(self):
        key = await self.preview('available')
        with patch.object(executor, 'start_execution', side_effect=RuntimeError('test failure')) as start:
            first = await executor.commit_execution_payment(key, '111111')
            second = await executor.commit_execution_payment(key, '111111')
        self.assertEqual(first['commit_status'], 'unknown')
        self.assertEqual(first, second)
        self.assertEqual(start.call_count, 1)
        self.assertEqual(self.stock(), 3)


if __name__ == '__main__':
    unittest.main()
