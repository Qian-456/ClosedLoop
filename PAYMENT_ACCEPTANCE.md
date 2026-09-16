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


## 前端响应与会话验收（2026-09-16 补充）

从 frontend 执行：

```powershell
npm ci
npm test -- --run src/features/itinerary/store/__tests__/useItineraryStore.payment.test.ts src/features/itinerary/ui/__tests__/PlanPanel.payment.test.tsx src/features/itinerary/ui/__tests__/PlanPanel.test.tsx
npm run build
```

14 项检查通过，其中新增 9 项；构建通过，保留原有大于 500kB 的 bundle 提示。UI 检查使用真实组件/会话 store 和模拟 API 响应，不能冒充浏览器到后端的完整链路。

人工观察标准：

- 后端成功时显示“执行已完成”。
- paid + failed 显示“执行未完成”，保留失败项，不提供整单再次支付按钮。
- unknown 显示“执行结果待核对”，提示核对已成功项；没有明细不能显示为完成。
- 密码错误且 not_started 时仍可删除并重新输入密码。
- 提交后切换会话，返回结果只更新对应 execution_id 的原会话；原会话已换新订单时，旧响应不得覆盖新订单。

测试从界面点击六位密码和确认按钮，核对响应后的实际 DOM；未完成真实 HTTP/浏览器验收。


## 真实浏览器 → HTTP → Mock 库存联调

新增本地隔离入口（只监听 127.0.0.1，不发布到生产）：

```powershell
# 先在 frontend 中 npm run build，再回到仓库根目录
python -X utf8 scripts/payment_browser_demo.py --scenario success --port 18766
# 另一个终端运行缺货场景
python -X utf8 scripts/payment_browser_demo.py --scenario partial --port 18765
```

打开各终端打印的 /review 地址，点击准备订单进入现有 /app 页面。展开支付面板。success 场景可先输入 222222，确认显示密码错误且 /review/inventory 库存仍为3；删除六位密码并输入111111，页面应显示执行已完成，库存为2。partial 场景在预览后把第二项库存设为0；输入111111后应显示执行未完成、失败1项及 review_sold_out，成功项库存2、失败项0，不再显示整单确认支付按钮。刷新后仍保留结果。

2026-09-16 已在 Codex 内置浏览器实际操作上述两场景；使用现有 main.py 的支付路由，无模拟 HTTP 响应。再次请求同一命令，成功仍 success、部分失败仍 failed，库存不再扣减。原始 fixture、preview-events、http-replay、browser-observation 保存在各自 payment-runs/browser-* 下。最初两次运行先于 metadata 功能，后补观察记录明确标记来源与 harness 未提交，不伪造当时自动生成的版本记录。后续运行自动生成 metadata.json（源码与构建哈希）。

此入口只复用支付路由，未暴露模型聊天接口；计划由固定夹具提供，不代表自然语言规划或模型驱动补齐的全链路。Ctrl+C 停止；每次重启新建独立库存，旧结果保留。开发隔离端口上的会话存储会被测试夹具替换，不要用于正式会话。
