# Backend：技术栈与落地方式（Stack）

## Purpose

这份文档回答：用什么技术栈把后端流程落地，并建议一个最小可跑的模块边界。

## Recommended Stack（v1）

- Language: Python
- UI: Streamlit（单进程，把 UI 与后端逻辑先跑通）
- LLM Orchestration: LangChain
- State Machine: LangGraph
- LLM Provider Strategy: DeepSeek（Primary）→ Qwen（Fallback）
- Map: 前端嵌入地图组件（高德 JS 或替代方案），后端只产出点位与顺序

## Why This Stack

- Demo 优先：减少服务拆分与部署成本
- 闭环优先：Plan/Validate/Execute/Fallback 都能在同一进程内可控地模拟
- 可演进：后续想拆 API 服务时，只需要把“后端核心流程”封装成独立模块

## Provider Strategy（DeepSeek → Qwen）

- Primary：DeepSeek（默认）
- Fallback：Qwen（当 Primary 超时、限流或返回不可用错误时切换）
- 建议把“切换原因”写入执行日志与 metrics（便于答辩展示稳定性）

## Minimal Architecture（推荐模块边界）

- domain：数据结构（PlanState / Constraints / Action / Result）
- tools：search / validate / feasibility / execute（纯函数或可 mock 的适配层）
- agent：planner agent（两种形态：planner/adjust；adjust 是“更多记忆/上下文”的强化版，用于局部修正）
- workflow：状态机与编排（INIT→PLAN→VALIDATE→...）
- ui：Streamlit 页面（只做展示与事件触发）

## Mock Preference Source（可选，但很适合 Demo）

- 用一个本地的轻量偏好数据源模拟“用户以前爱点的吃的/价位偏好”
- 用于影响 search_restaurants 与套餐排序（bundles ranking）

## Config（建议）

- 用环境变量控制：Primary/Fallback provider、模型名、超时、重试、是否注入执行失败等
- 为了便于答辩与复现：提供一组默认 demo constraints（家庭/朋友）

## Observability（先小后大）

- 指标只要能算出来：plan_success / exec_success / fallback_rate / latency
- 先把指标写到内存与 UI 展示，后续再接日志或埋点系统

## Checklist

- 不依赖外部服务也能跑完整闭环（search/execute 可 mock）
- LLM 调用可开关（没有 key 时用规则/模板降级）
- 架构分层清晰：UI 不直接做业务决策
