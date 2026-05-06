from typing import Literal

from pydantic import BaseModel, Field


class ItineraryItem(BaseModel):
    """行程中单个地点/元素的最小信息单元。"""

    id: str = Field(..., description="候选条目的唯一 id")
    name: str = Field(..., description="候选条目的名称")
    type: Literal["restaurant", "activity", "gift_shop", "commute"] = Field(
        ..., description="候选条目的类型"
    )
    location: str = Field(..., description="候选地点的地址/位置描述")
    distance_km: float = Field(..., description="候选地点相对当前位置的距离（km）")
    cost: float = Field(default=0.0, description="该条目的价格/花费")


class ItineraryStep(BaseModel):
    """行程中的一个步骤。"""

    order_id: str = Field(..., description="步骤顺序 id，实体活动为 1, 2... 通勤为 C1, C2...")
    item: ItineraryItem = Field(..., description="该步骤选择的候选条目")
    duration_minutes: int = Field(..., description="该步骤建议停留时长（分钟）")
    note: str = Field(..., description="该步骤的简短说明/理由")


class ItineraryPlanVariant(BaseModel):
    """同一批 candidates 的一套时间组合方案。"""

    plan_id: str = Field(..., description="方案 id，例如 plan_1")
    title: str = Field(..., description="方案标题，例如 4小时轻松版")
    steps: list[ItineraryStep] = Field(..., description="方案内的步骤列表")
    selected_item_ids: list[str] = Field(
        ..., description="与 steps 顺序一致的候选 id 列表"
    )
    total_duration_minutes: int = Field(..., description="该方案预计总时长（分钟）")
    total_cost: float = Field(default=0.0, description="该方案的总花费")
    average_score: float = Field(default=0.0, description="该方案的平均得分")


class ItineraryPlan(BaseModel):
    """plan 节点输出的行程草案（可包含多套时间组合方案）。"""

    plans: list[ItineraryPlanVariant] = Field(..., description="方案列表，第一套为推荐方案")
    status: Literal["ok", "insufficient_candidates", "fallback_deterministic"] = Field(
        ..., description="生成状态"
    )
    missing_types: list[Literal["restaurant", "activity", "gift_shop"]] = Field(
        default_factory=list, description="候选不足时缺失的类型列表"
    )

