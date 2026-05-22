# ClosedLoop 前端

Mobile-first 的 Web SPA「后端调用台 + 用户体验壳子」。

## 本地开发

在 `frontend` 目录下：

```bash
npm ci
npm run dev
```

默认开发地址：

- `http://localhost:5173`

前端开发时会通过 Vite proxy 转发后端接口（`/invoke`、`/health`、`/execute/*`），后端默认是 `http://127.0.0.1:8000`。

## 调试建议

- 后端开启 `LOG_ELK_ENABLED=true` 后，会输出结构化日志到 `backend/src/logs/elk.jsonl`（便于 Kibana/grep 检索）
- 当遇到“为什么只生成了 1-2 套方案”时，后端开启 `LOG_PLANNER_STATS=true`，观察 `phase=planner_*` 统计日志
