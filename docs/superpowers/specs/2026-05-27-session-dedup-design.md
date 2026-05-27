# 会话删除与误创建拦截设计

## Summary

- 目标：解决侧边栏会话列表里“新对话/重复会话过多”的问题，同时不给真实历史对话带来误伤。
- 方案：采用“删除键常驻 + 只拦误创建”的策略，不做按内容的激进去重。

## Current State

- 侧边栏中的删除键当前只在 hover 时显示，移动端与演示壳里不够直观。
- 新会话在首发时通过 `startSession(sessionId, text)` 直接追加进 `sessions`。
- 历史会话通过 Zustand `persist` 长期保存在本地，旧的空会话或默认标题会一直留在列表里。
- 当前没有任何“误创建拦截”逻辑，也没有“空会话复用”逻辑。

## Decisions

- 删除键对每条会话都始终显示，不再依赖 hover。
- 不做“按标题/内容强制去重”，避免误伤用户真实重复提问的场景。
- 只拦截明显的误创建：
  - 当前已经存在待发送的空会话时，不重复创建新的空会话。
  - 点击“新对话”后进入空白态，再发送首条消息时，优先复用已有的空会话上下文，而不是继续追加。
- 不批量清洗历史数据；只修未来新增逻辑，避免继续制造重复项。

## Proposed Changes

### 1. Store

- 文件：`frontend/src/features/itinerary/store/useItineraryStore.ts`
- 增加一个“会话创建前规整”逻辑：
  - 在 `startSession` 内先检查是否已存在相同 `sessionId`。
  - 若存在，则只切换当前会话并更新标题，不重复 append。
  - 对明显的空会话保留单实例语义，避免反复追加。

### 2. Sidebar

- 文件：`frontend/src/features/itinerary/ui/Sidebar.tsx`
- 删除键始终展示，样式弱化但可点击。
- 保持每条会话都可直接删除。

### 3. Tests

- 文件：`frontend/src/features/itinerary/store/__tests__/useItineraryStore.session.test.ts`
- 覆盖：
  - 同一个 sessionId 不会重复插入。
  - 空会话状态下再次新建不会产生重复项。
  - 正常不同 sessionId 的真实新会话仍可新增。

## Non-Goals

- 不做按标题相同去重。
- 不做按首条消息文本相同去重。
- 不在本次改动里批量清理用户已有历史记录。

## Acceptance Criteria

- 每条会话都看得到删除入口。
- 重复点击“新对话”或在空白态反复进入首发流程，不再制造新的默认会话。
- 用户主动开启新的真实会话时，历史仍正常保留。
