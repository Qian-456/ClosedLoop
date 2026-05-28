from typing import Any, NotRequired
from typing_extensions import TypedDict


class SearchSubgraphState(TypedDict):
    """Search subgraph state schema."""

    session_id: str
    category: str
    user_request: str
    subcatory: NotRequired[str | None]
    top_k: NotRequired[int]
    candidates: NotRequired[list[dict[str, Any]]]

    results: NotRequired[list[dict[str, Any]]]


class SearchSubgraphOutput(TypedDict):
    """Search subgraph output schema."""

    results: NotRequired[list[dict[str, Any]]]

