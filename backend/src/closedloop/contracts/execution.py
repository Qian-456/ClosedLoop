from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ExecuteStep(BaseModel):
    """执行阶段的单步输入（来自前端时间轴）。"""

    item_id: str = Field(..., description="条目 id（combo_id/package_id/gift_id/commute_xxx）")
    item_type: Literal["restaurant", "activity", "gift_shop", "commute"] = Field(
        ..., description="条目类型"
    )
    start_time: str = Field(..., description="开始时间（HH:MM）")
    end_time: str = Field(..., description="结束时间（HH:MM）")
    commute_mode: Literal["walking", "taxi", "driving"] | None = Field(
        default=None, description="通勤交通方式（仅 commute）"
    )
    backup_candidates: Optional[list[dict]] = Field(
        default=None, description="系统内部备选队列"
    )
    replacement_policy: Optional[str] = Field(
        default="equivalent_only", description="自动替换策略"
    )
    user_touched: Optional[bool] = Field(
        default=False, description="用户是否主动修改过此项"
    )


class ExecuteRequest(BaseModel):
    """开始执行的请求。"""

    plan_id: str = Field(..., description="方案 id，例如 plan_1")
    steps: list[ExecuteStep] = Field(default_factory=list, description="时间轴步骤")


class ExecutionStartResponse(BaseModel):
    """开始执行后的返回。"""

    execution_id: str = Field(..., description="执行会话 id")


class ExecuteEvent(BaseModel):
    """SSE 推送的事件（统一以 JSON 作为 data）。"""

    type: Literal["item_update", "done"] = Field(..., description="事件类型")
    data: dict[str, Any] = Field(default_factory=dict, description="事件 payload")
