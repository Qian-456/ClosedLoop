# [OPEN] demo-404

## 症状

- 访问前端页面时出现 `Access Error: 404 - Not Found`
- 页面提示 `Cannot open document for: /demo`

## 初始假设

1. 前端路由表中已不存在 `/demo`。
2. Docker 前端容器仍在提供旧的静态资源或旧配置。
3. 静态服务器未对 SPA 路由做 `index.html` 回退。
4. 当前有效入口已经改成 `/app`，但访问习惯或文档仍指向 `/demo`。

## 下一步

- 检查前端路由定义
- 检查 Docker 前端容器当前提供的资源
- 检查前端静态服务器配置

## 运行时证据

- 前端源码中存在 `/demo` 与 `/app` 路由：
  - `frontend/src/app/router.tsx`
- Docker 前端镜像内静态资源存在，`index.html` 已部署到 `/usr/share/nginx/html`。
- 前端容器内部访问成功：
  - `http://127.0.0.1/` → `200`
  - `http://127.0.0.1/demo` → `200`
- Nginx 配置存在 SPA 回退：
  - `try_files $uri /index.html;`
- 但宿主机访问失败：
  - `http://127.0.0.1:8080/` → `404`
  - `http://127.0.0.1:8080/demo` → `404`
- 宿主机 `8080` 端口存在额外本地监听进程：
  - `PID 10044` → `ApplicationWebServer.exe`
- 同时 Docker 也在监听 `8080`：
  - `PID 34536` → `com.docker.backend.exe`

## 当前判定

1. 前端 React 路由没有丢，`/demo` 仍然存在。
2. 前端 Docker 容器内的 Nginx 配置和静态资源也是正常的。
3. 真正的问题是宿主机 `8080` 被额外的 `ApplicationWebServer.exe` 抢占/并存监听，浏览器命中了错误的本地服务。
4. 因此你看到的 `404 /demo` 不是 ClosedLoop 前端返回的，而是另一个本地 Web 服务返回的。

## 本次修复

- 将 `docker-compose.yml` 中的前端端口从 `8080:80` 调整为 `8088:80`。
- 将 `README.md` 中的前端访问地址同步为 `http://localhost:8088`。
- 将 `docs/deployment_docker.md` 中的 Docker 部署访问地址与端口占用说明同步为 `8088`。

## 后续操作

- 重新启动前端容器使新端口生效：
  - `docker compose up -d --build frontend`
- 之后使用：
  - `http://127.0.0.1:8088/demo`
