# Remove Recommendation Score (推荐指数) Design Spec

## 1. Overview
The current system calculates and displays a "Recommendation Score" (`推荐指数`) for each generated itinerary plan. This score is a leftover from a previous workflow and no longer provides significant value to the user experience. To simplify the interface and data models, we will remove this score from the user-facing frontend and the API response schema.

## 2. Changes

### 2.1 Frontend Changes
- **UI Update**: In `frontend/src/features/itinerary/ui/PlanCard.tsx`, remove the UI capsule (`bg-blue-50`) that displays `推荐指数 {score}`.
- **Type Definitions**: In `frontend/src/features/itinerary/model/types.ts`, remove the `average_score` and `experience_score` properties from the `ItineraryPlanVariant` interface.

### 2.2 Backend Changes
- **Data Model**: In `backend/src/closedloop/contracts/itinerary.py`, remove the `average_score` and `experience_score` fields from the `ItineraryPlanVariant` Pydantic model.
- **Planner Logic**: In `backend/src/closedloop/graph/plan_subgraph/planner_utils.py` and potentially `planner_node.py`:
  - Keep the calculation of the score internally (renaming to `sort_score` if necessary) to maintain the sorting logic of generated plans.
  - Do not export `average_score` and `experience_score` into the final returned plan dictionaries.

## 3. Scope and Impact
This is a straightforward cleanup task. It does not alter the core DFS combination logic or the overall structure of the application. The internal scoring mechanism remains functional for sorting `unique_candidates`, ensuring that the most logical plans still bubble up to the top, but the user is not distracted by arbitrary numerical scores.

## 4. Edge Cases
- **Sorting**: We must ensure that `planner_utils.py` still has a valid key to sort `candidate_pool` by. We will use an internal `_sort_score` key in the dictionary during generation and sorting, which won't map to the final `ItineraryPlanVariant` model.