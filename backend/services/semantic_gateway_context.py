"""本轮语义网关（PolyLM）结果的上下文绑定。

供检索工具在执行时强制采纳 aligned_query / jurisdiction，
避免仅依赖 LLM 自觉遵守 prompt。
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from services.query_detection import SemanticGatewayResult

_CURRENT_SEMANTIC_GATEWAY: ContextVar[SemanticGatewayResult | None] = ContextVar(
    "current_semantic_gateway",
    default=None,
)


def set_current_semantic_gateway(gateway: SemanticGatewayResult | None) -> Token:
    return _CURRENT_SEMANTIC_GATEWAY.set(gateway)


def get_current_semantic_gateway() -> SemanticGatewayResult | None:
    return _CURRENT_SEMANTIC_GATEWAY.get()


def reset_current_semantic_gateway(token: Token) -> None:
    _CURRENT_SEMANTIC_GATEWAY.reset(token)


# ISO → 工具 jurisdiction 参数（与 legal_search_router 别名一致）
GATEWAY_COUNTRY_TO_TOOL_JURISDICTION: dict[str, str] = {
    "CN": "",
    "TH": "大陆法系",
    "VN": "大陆法系",
    "ID": "大陆法系",
    "MY": "伊斯兰法系",
    "SG": "普通法系",
    "MM": "普通法系",
    "KH": "大陆法系",
    "LA": "大陆法系",
    "PH": "普通法系",
    "BN": "伊斯兰法系",
}

GATEWAY_COUNTRY_LABEL_EN: dict[str, str] = {
    "CN": "China",
    "TH": "Thailand",
    "VN": "Vietnam",
    "ID": "Indonesia",
    "MY": "Malaysia",
    "SG": "Singapore",
    "MM": "Myanmar",
    "KH": "Cambodia",
    "LA": "Laos",
    "PH": "Philippines",
    "BN": "Brunei",
}


def tool_jurisdiction_for_gateway_country(code: str | None) -> str | None:
    """Return tool jurisdiction arg for a gateway country code, or None if unbound."""
    if not code:
        return None
    if code not in GATEWAY_COUNTRY_TO_TOOL_JURISDICTION:
        return None
    return GATEWAY_COUNTRY_TO_TOOL_JURISDICTION[code]


__all__ = [
    "GATEWAY_COUNTRY_LABEL_EN",
    "GATEWAY_COUNTRY_TO_TOOL_JURISDICTION",
    "get_current_semantic_gateway",
    "reset_current_semantic_gateway",
    "set_current_semantic_gateway",
    "tool_jurisdiction_for_gateway_country",
]
