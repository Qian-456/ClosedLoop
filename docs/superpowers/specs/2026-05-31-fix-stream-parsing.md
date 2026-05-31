# Plan: Fix Stream Parsing for Proper Markdown Rendering

## 1. Goal
The user pointed out that while the previous version did output constraints before calling the tool, the text was squashed together (e.g., `-群体: 一家三口 -预算: 600元`) instead of rendering as a proper vertical Markdown list. This happened because the backend stream parser or frontend renderer swallowed or failed to handle newlines properly. We need to fix the stream parsing so the frontend receives and renders proper Markdown with line breaks.

## 2. Implementation Steps

### Step 1: Fix Backend Stream Parser (`main.py`)
- Inspect `_extract_message_text_from_chunk` and related functions in `backend/src/main.py`.
- Ensure that when extracting text from `AIMessageChunk`, we are not calling `.strip()` on intermediate chunks in a way that destroys newlines. (Streaming tokens often arrive as `\n` or `\n-`, and stripping them breaks formatting).
- We already removed `.strip()` from one place in the previous attempt, but we need to ensure the block extraction itself (`_get_block_text`) and the chunk combination are completely raw and preserve all whitespace.

### Step 2: Refine Agent Prompt (`agent.py`)
- Update `PLAN_AGENT_SYSTEM_PROMPT` to enforce strict, clean Markdown list formatting for the pre-tool constraint output.
- Explicitly tell the agent to use proper spacing and line breaks.
- Example format:
  ```
  好的，我先为您整理一下需求：
  - **群体**：一家三口
  - **预算**：600元
  - **时间**：13:00-19:00
  - **偏好**：亲子友好、少走路
  现在为您调用工具生成方案！
  ```

### Step 3: Verify Frontend Rendering (`ChatView.tsx` / `MarkdownText.tsx`)
- Ensure the frontend `ChatView` uses `whitespace-pre-wrap` or that `MarkdownText` handles line breaks correctly (standard Markdown lists usually handle this natively if the raw string contains newlines).

## 3. Verification
- Run tests.
- Verify that the stream correctly transmits newlines and the UI renders a vertical bulleted list.