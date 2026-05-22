# Docker 一键部署

本项目支持在仓库根目录使用 docker compose 一键启动前后端（前端由 Nginx 提供静态资源，并同源代理后端 API）。

## 1. 前置条件

- Windows 已安装 Docker Desktop，并开启 WSL2 后端
- 仓库内准备好后端运行所需的 `backend/.env`

## 2. 配置环境变量

复制并填写：

- `backend/.env.example` → `backend/.env`

至少需要：

- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`

## 3. 一键启动

在仓库根目录执行：

```bash
docker compose up --build
```

启动后访问：

- 前端：`http://localhost:8080`
- 后端健康检查：`http://localhost:8080/health`（由前端 Nginx 代理到后端）
- （可选直连后端）`http://localhost:8000/health`

## 4. 说明

- 前端会以同源方式请求 `/invoke`、`/execute/*`，无需额外 CORS 配置。
- Mock 数据从仓库 `mock_db/` 目录以只读方式挂载到后端容器 `/app/mock_db`。
- 日志默认写入 `backend/src/logs/`（通过 volume 映射到宿主机，便于查看）。

## 5. 常见问题

### 5.1 端口被占用

- 修改 `docker-compose.yml` 中的端口映射，例如把 `8080:80` 改成 `8081:80`。

### 5.2 后端启动报缺少 API Key

- 检查 `backend/.env` 是否存在、是否填入了 `DEEPSEEK_API_KEY` 与 `DASHSCOPE_API_KEY`。
