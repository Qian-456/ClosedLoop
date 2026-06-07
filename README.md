# ClosedLoop: 执行型本地生活 Agent

ClosedLoop 是一个面向未来的执行型本地生活 Agent。只需用户一句话需求，系统即可完成“意图理解 → 结构化约束 → 候选过滤与打分 → 智能行程规划 → 方案调整 → 模拟支付与执行”的全流程闭环。

本项目针对本地生活服务场景进行了深度的工程化与架构设计，强调：
- **Execution（执行闭环）**：不仅仅停留在闲聊，而是将意图转化为可执行的实体订单。
- **Engineering（工程规范）**：拆分微服务、严格的配置与日志管理、高拟真的本地 Mock DB 支撑。
- **Workflow（工作流可控）**：引入 Handoff 架构与多 Agent 协同（规划、修改、执行），保证流程的确定性与可控性。

## 🏆 比赛提交物

比赛的演示文档、核心设计说明以及工具列表均已提取到根目录下的 `competition_submission/` 文件夹中：
- `competition_submission/01_demo.md` - 演示剧本与复现指南
- `competition_submission/02_tools.html` - 工具与 API 契约列表
- `competition_submission/03_design.html` - 核心架构与设计思路

## 🌟 核心能力与亮点

**1. 创新性（突破性技术架构与交互体验）**
- **Workflow 与 Agent 的完美融合**：打破纯 Agent 规划容易产生的思维盲区与幻觉，创新性地引入工作流（Workflow），将极度复杂的多约束本地生活规划变得稳定且预期可控。在保留 Agent 灵活调度的前提下，做到“硬约束交给代码，推荐交给算法（现阶段以规则代替）”，为未来接入美团成熟的推荐系统以大幅提升个性化留出了无缝扩展的可能。
- **顺滑的闭环交互**：从自然语言对话到生成直观的可视化方案卡片，支持方案链接共享给好友。确认方案后顺滑拉起 Mock 执行，将前沿技术与真实业务链路进行了创造性结合。

**2. 完整性（高成熟度的规划与执行质量）**
- **严谨的规划质量**：通过深度模块化代码承接时间、地理等硬约束，准确理解并满足人群、忌口、出行偏好等复杂条件，确保时间分配自然且不出错。
- **杜绝幻觉的执行质量**：通过全局状态共享（State Sharing），将确定的方案内容直接透传给执行 Agent，从根本上避免大模型的“胡编乱造”。智能接管异常并提供细粒度的执行模式选择（如：一次性预约所有打车，或仅预约从家出发的首趟车），端到端跑通成功率（Pass@1）极高。

**3. 应用效果（极致性能与精准匹配）**
- **流式输出与透明状态**：前端提供丝滑的流式响应，工具调用响应极快（≤ 3秒），实时向用户展示“正在规划方案…”等中间气泡状态，消除等待焦虑。
- **多维偏好的精准兼容**：高度准确地解析并兼容用户的各类复杂需求，包括活动偏好、时间排布习惯、交通工具偏好以及严格的餐饮忌口，做到“所想即所得”。

**4. 商业价值（极高 ROI 与数据飞轮潜力）**
- **重塑用户决策漏斗**：让用户从过去痛苦的“先想去哪、再算时间、最后算钱”转变为极其轻松的“看方案做判断、局部替换”。单次规划的 Token 成本不到 1 毛钱，却能成倍降低用户的决策时间成本，大幅提升最终成交概率。
- **商业变现与生态协同**：高转化率直接赋能平台，提升广告收益与交易佣金。同时，本系统天然契合美团的海量真实数据，一旦接入即可快速启动“数据飞轮”，持续增强推荐准度，进而极大提升用户粘性与对 Agent 的信任度。

## 🚀 快速启动

### 1. 环境变量配置
复制后端环境变量模板并填写必要的 API Key：
```bash
cp backend/.env.example backend/.env
```
（注：必须配置 `DEEPSEEK_API_KEY` 以及 `DASHSCOPE_API_KEY`，后者用于在 DeepSeek 不可用时作为 Fallback 备用，否则服务将无法正常启动）

### 2. 启动服务 (推荐 Docker 一键部署)
强烈建议使用 Docker 一键拉起全套服务（包含前端页面、主 Agent 服务以及检索/规划子服务）：

```bash
docker compose up -d --build
```
启动完成后，直接在浏览器访问：**`http://localhost:8088`** 即可体验完整产品。

> **提示**：如果需要进行本地代码开发调试，可参考以下命令（不推荐用于常规演示）：
> ```bash
> # 启动前端开发服务器
> cd frontend && npm ci && npm run dev
> # 启动后端提供 HTTP 接口的主服务
> cd backend/src && python main.py
> # (可选) 纯命令行交互测试
> cd backend/src && python cli_main.py
> ```

### 3. 可选：通过 Docker 查看 ELK 结构化日志

如果你想排查“为什么候选太少 / 为什么剪枝过多 / 为什么某次规划超时”，可以额外启动 ELK 来查看结构化日志。

> **说明**：这不是本项目的重点能力，也不是最终形态。当前引入 ELK，主要是为了在开发与演示阶段快速追溯链路，检查统计数据和规划过程是否异常；真实业务里更核心的还是推荐系统与业务指标体系。

1. 先确认 `backend/.env` 中已经打开结构化日志输出：

```bash
LOG_ELK_ENABLED=true
LOG_PLANNER_STATS=true
```

2. 先按上面的方式启动主业务服务：

```bash
docker compose up -d --build
```

3. 再单独启动 ELK：

```bash
docker compose -f docker/elk/docker-compose.elk.yml --project-directory . up -d
```

4. 打开 Kibana：

- `http://localhost:5601`

5. 在 Kibana 中创建 Data View：

- Index pattern 填 `closedloop-*`
- 进入 `Discover` 后即可按时间线查看结构化日志

6. 常见观察方式：

- **硬过滤阶段（推荐先看）**：在 Kibana 里筛选 `event=filter_drop`；先看 `category.keyword` 和 `reason_code.keyword`，可以知道是哪个大类（如餐厅/活动/礼品）被过滤，以及各类过滤原因的分布。
- **看过滤细节**：继续展开 `reason_detail.*` 字段，可以看到每种硬过滤原因的具体细节；例如价格过滤时可看 `reason_detail.actual` 与 `reason_detail.threshold`，年龄过滤可看 `reason_detail.age_range.keyword`、`reason_detail.child_age` 等。
- **Plan 阶段减枝**：DFS 减枝的可能性太多，不适合在 ELK 中逐条细粒度分析；这一部分更适合直接看后端日志中的 `phase=planner_candidate_pool_stats`、`phase=planner_pattern_skipped` 等统计信息，判断是 pattern 缺失、候选池不足还是组合阶段被大量剪枝。
- **链路追溯**：结合 `session_id / tool / error / phase` 等字段，可以追溯某次请求从主服务到子服务的处理链路。
- **离线查看**：如果只想快速看原始文件，也可以直接查看 `backend/src/logs/elk/` 下生成的 `jsonl` 日志。

## 📚 目录结构导览

- `competition_submission/`：比赛核心文档与提交物。
- `backend/`：Python 后端服务（含主 Agent 服务与规划子服务）。
- `frontend/`：React + Vite 移动端响应式前端。
- `mock_db/`：本地生活高保真数据库配置。

## 🧪 测试

后端测试：
```bash
python -m unittest discover -s tests -p "test_*.py"
```

前端测试：
```bash
npm test -- --run
```
