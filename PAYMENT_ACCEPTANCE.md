# Mock 支付重复提交：人工验收

## 一条命令

在独立 PR 分支根目录，使用安装好后端依赖的 Python 环境：

```powershell
python -X utf8 scripts/payment_demo.py
```

无需模型密钥、网络或商家服务。每次生成新的 `payment-runs/<时间-ID>/`，只修改该目录内的 JSON 库存。打开最后打印的 `index.html`，查看本次实测 `checks`、库存变化、八次并发调用结果、提交版本和源码哈希。

| 操作 | 预期可观察结果 |
|---|---|
| 初始库存 | 3 |
| 创建待支付命令 | 库存仍为 3 |
| 输入错误 Mock 密码 | 返回失败，库存仍为 3 |
| 同一命令同时提交 8 次 | 八份结果相同，只有一次扣减，库存为 2 |
| 再次提交同一命令 | 返回首次结果，库存仍为 2 |

点击“初始库存”和“执行后库存”，直接核对 JSON；报告 `passed=false`、命令非零退出或库存数值不符均视为未通过。报告中的文字预期不能替代实际 JSON。清理时只需删除该次 `payment-runs` 子目录，原始 `backend/src/mock_db` 不受影响。

这运行真实 Mock 执行器和文件落盘，仅配置路径被替换到隔离目录；不是伪造成功事件。但没有浏览器、HTTP、Agent 模型或真实支付服务，不能称为产品全链路验收。

## 回归测试

```powershell
$env:PYTHONPATH='backend/src'
python -X utf8 -m unittest tests.test_payment_idempotency tests.test_forced_out_of_stock tests.test_mock_executor_event_detail tests.test_execute_tool_consistency_payment_gate -v
```

2026-09-16，Python 3.12.3：18 项通过，其中新增 8 项。新增测试包含真实库存部分失败、并发、结果重放、取消等待、不同命令隔离，以及注入异常/缺失事件流的防误报检查。后两项属于故障注入，不作为真实外部故障证据。

## HR / 技术面试官可核验

- HR：同一命令连续或并发提交不会重复扣库存，有可运行报告和前后 JSON。
- 技术面试官：从 `main.py` 的支付路由进入 `commit_execution_payment`，查看命令 ID 下共享任务、取消保护、独立事件消费、部分失败保留与未知状态处理。用测试重现修改前错误和修改后行为。
- 个人贡献：用户要求可验收的项目改造；Agent 定位、实现和运行实验。用户本人尚未填写复盘，不能将本次调试过程直接写成个人经历。

## 适用边界

幂等键是同一个进程中的 execution_id。缓存保留至进程结束，重启后结果丢失；没有跨进程锁、数据库事务、缓存淘汰或支付账本。新 execution_id 是新命令，不保证跨 ID 去重。不能宣称生产支付 exactly-once。

部分成功后的同命令重试只返回原失败结果，不能自动重做整单；后续应核对成功项并为未完成项创建独立补齐命令。本 PR 不实现完整 UI 补齐流程。出现 unknown 应核查隔离库存，不能擅自新建整单重试。

`payment-review/DECISIONS.md` 和 `FEEDBACK_AND_FIXES.md` 保留本次取舍与真实失败记录；与 PR #1 的状态回归报告独立，未合并或部署。
