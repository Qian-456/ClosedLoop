# Brainstorming Design: Fixup Agent Adjust and Execute

## Context
When the system is in the `fixup_agent` phase (because an item failed to reserve), the LLM was previously instructed to call two tools sequentially in one response: `adjust_plan_item` and `execute_itinerary`. 
However, LangGraph executes multiple tool calls from a single LLM response concurrently. This concurrency causes a race condition where `execute_itinerary` reads the old plan state before `adjust_plan_item` has updated it, resulting in the tool not executing correctly.

## Solution
We will combine the "adjust" and "execute" steps into a single atomic tool for the `fixup_agent` called `adjust_and_execute_plan_item`.

1. **New Tool**: `adjust_and_execute_plan_item`
   - Inputs: `plan_id`, `target_item_id`, `new_item_id`, `book_commutes_policy` (optional).
   - Logic:
     1. Runs the same validation checks as `adjust_plan_item` (checking if `target_item_id` is already executed, fetching `new_item_data` from candidates or plan_sub API).
     2. Calls `repair_plan` to replace the item and resolve constraints.
     3. If repair fails, returns the error.
     4. If repair succeeds, updates the state with the `new_plan` (in `latest_plan_result` and `itinerary`).
     5. Immediately calls the internal execution logic (equivalent to `start_execution` used in `execute_itinerary`) on the `new_plan`.
     6. Returns a single `Command` containing both the adjustment updates and the execution event updates.

2. **Refactoring**:
   - `adjust_plan_item` remains intact for `plan_agent` to use. Its existing validations (like reading `success`, `replacement` from `execution_summary`) will not be deleted.
   - We will extract the core logic of `adjust_plan_item` into a shared helper function (e.g., `_do_adjust_plan_item`) to avoid code duplication between `adjust_plan_item` and `adjust_and_execute_plan_item`.
   - We will also extract the core logic of `execute_itinerary` into a shared helper (e.g., `_do_execute_itinerary`).

3. **Agent Prompts & Config**:
   - In `backend/src/closedloop/graph/agent.py`, the `fixup_agent`'s tools will be updated to: `[search_candidates, adjust_and_execute_plan_item]`.
   - `FIXUP_AGENT_SYSTEM_PROMPT` will be updated. When a user selects a candidate or searches for one, the agent will be instructed to call `adjust_and_execute_plan_item` instead of two separate tools.

## Error Handling & Consistency Checks
- **Execution Locks**: `plan_option` is the single source of truth during execution. Items in `execution_report` that are successfully executed (or successfully executed after replacement) CANNOT be modified. If the user/agent attempts to modify them, the tool will return a `ToolMessage` stating "该项目已成功预订/执行，禁止替换".
- **Post-Execution Consistency**: After the new adjustment and execution run, if all items are reported as executed, the system will perform a consistency check to ensure the items in `execution_report` exactly match those in `plan_option`. If there is a mismatch, a retry/sync mechanism is triggered.
- If the item cannot be found or the replacement conflicts with constraints, it returns an error ToolMessage.
- If execution fails (e.g., still out of stock), the `fixup_agent` receives the updated state and can re-prompt the user.

## Success Criteria
- The LLM only makes one tool call during fixup selection.
- The `execute` phase reads the correctly updated plan.
- Existing features (search, adjust validations) remain fully functional.
