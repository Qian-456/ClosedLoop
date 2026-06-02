from typing import Literal, Optional

from pydantic import BaseModel, Field


class CommuteOption(BaseModel):
    """通勤选项（用于前端切换交通方式）。"""

    mode: Literal["walking", "taxi", "driving"] = Field(..., description="交通方式")
    time_minutes: int = Field(..., description="预计通勤时间（分钟）")
    cost: float = Field(default=0.0, description="预计通勤费用（元）")


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
    gift_price: Optional[float] = Field(default=None, description="礼物价格（仅 gift_shop）")
    delivery_fee: Optional[float] = Field(default=None, description="配送费（仅 gift_shop）")
    delivery_distance_km: Optional[float] = Field(default=None, description="配送距离（仅 gift_shop）")
    price_breakdown: Optional[dict[str, float]] = Field(
        default=None, description="费用明细：基础价、礼品、配送、通勤与合计"
    )
    duration_breakdown: Optional[dict[str, int]] = Field(
        default=None, description="时间明细：基础时长、等待、转场缓冲与合计"
    )
    expected_wait_minutes: Optional[int] = Field(default=None, description="预计等待/排队时长")
    queue_required: Optional[bool] = Field(default=None, description="是否预计需要排队")
    seating_risk_prob: Optional[float] = Field(default=None, description="无座风险概率（0.0-1.0），与排队和热度相关")
    requires_booking: Optional[bool] = Field(default=None, description="是否需要预约")
    booking_target_type: Optional[Literal["restaurant", "package"]] = Field(
        default=None, description="预约扣减目标类型"
    )
    booking_target_id: Optional[str] = Field(default=None, description="预约扣减目标 id")
    parent_name: Optional[str] = Field(default=None, description="父级地点名，如餐厅名或活动场地名")
    display_name: Optional[str] = Field(default=None, description="前端主展示名，优先显示地点名")
    sub_name: Optional[str] = Field(default=None, description="前端副展示名，优先显示套餐名或票种名")

    intro: Optional[str] = Field(default=None, description="条目介绍（来自 Mock DB）")
    features: Optional[str] = Field(default=None, description="条目特色/亮点（来自 Mock DB）")

    commute_from: Optional[str] = Field(default=None, description="通勤：出发点名称")
    commute_to: Optional[str] = Field(default=None, description="通勤：目的地名称")
    commute_mode: Optional[Literal["walking", "taxi", "driving"]] = Field(
        default=None, description="通勤：当前交通方式"
    )
    commute_options: Optional[list[CommuteOption]] = Field(
        default=None, description="通勤：可选交通方式列表"
    )

    backup_candidates: Optional[list[dict]] = Field(
        default=None, description="系统内部备选队列，用于执行失败时自动替换"
    )
    replacement_policy: Optional[Literal["strict", "equivalent_only", "completion_first"]] = Field(
        default="equivalent_only", description="自动替换策略"
    )
    user_touched: Optional[bool] = Field(
        default=False, description="用户是否主动修改过此项"
    )


class ItineraryStep(BaseModel):
    """行程中的一个步骤。"""

    order_id: str = Field(..., description="步骤顺序 id，实体活动为 1, 2... 通勤为 C1, C2...")
    item: ItineraryItem = Field(..., description="该步骤选择的候选条目")
    duration_minutes: int = Field(..., description="该步骤建议停留时长（分钟）")
    start_time: Optional[str] = Field(default=None, description="步骤预计开始时间（HH:MM）")
    end_time: Optional[str] = Field(default=None, description="步骤预计结束时间（HH:MM）")


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
    experience_score: float = Field(default=0.0, description="该方案的体验分（用于前端展示，0-100）")


class ItineraryPlan(BaseModel):
    """plan 节点输出的行程草案（可包含多套时间组合方案）。"""

    plans: list[ItineraryPlanVariant] = Field(..., description="方案列表，第一套为推荐方案")
    status: Literal["ok", "insufficient_candidates", "fallback_deterministic"] = Field(
        ..., description="生成状态"
    )
    missing_types: list[Literal["restaurant", "activity", "gift_shop"]] = Field(
        default_factory=list, description="候选不足时缺失的类型列表"
    )
