"""语义网关硬锚点：工具层必须强制覆盖检索 query 与 jurisdiction。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from mcp.legal_search_router import resolve_legal_systems, search_article
from services.query_detection import QueryDetection, SemanticGatewayResult
from services.semantic_gateway_context import (
    reset_current_semantic_gateway,
    set_current_semantic_gateway,
)


def _gateway(
    *,
    jurisdiction: str = "TH",
    aligned_query: str = "การถือหุ้นของคนต่างชาติในบริษัทไทย",
    aligned: bool = True,
) -> SemanticGatewayResult:
    return SemanticGatewayResult(
        original_query="中国企业能否100%持有泰国公司？",
        detection=QueryDetection("zh", jurisdiction, (jurisdiction,), "polylm"),
        aligned_query=aligned_query,
        alignment_language="th",
        aligned=aligned,
        english_pivot="Can a Chinese company wholly own a Thai company?",
        legal_concepts=("foreign ownership",),
    )


class LegalSearchHardAnchorTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Ensure no leftover bind leaks into other tests.
        token = set_current_semantic_gateway(None)
        reset_current_semantic_gateway(token)

    def test_resolve_legal_systems_forces_bound_country_and_aligned_query(self):
        token = set_current_semantic_gateway(_gateway())
        try:
            plan = json.loads(
                resolve_legal_systems("随便写点中国公司法问题绕开泰国")
            )
        finally:
            reset_current_semantic_gateway(token)

        self.assertTrue(plan["gateway_hard_anchor"])
        self.assertEqual(plan["countries"][0]["country"], "TH")
        self.assertEqual(len(plan["systems"]), 1)
        self.assertEqual(plan["systems"][0]["jurisdiction"], "大陆法系")
        self.assertEqual(
            plan["systems"][0]["suggested_query"],
            "การถือหุ้นของคนต่างชาติในบริษัทไทย",
        )
        self.assertIn("硬锚点", plan["systems"][0]["reason"])

    def test_search_article_rewrites_text_and_jurisdiction(self):
        token = set_current_semantic_gateway(_gateway())
        captured: dict[str, str] = {}

        def fake_fuzzy(system: str, text: str) -> str:
            captured["system"] = system
            captured["text"] = text
            return json.dumps({"success": True, "results": []}, ensure_ascii=False)

        try:
            with patch("mcp.legal_search_router._fuzzy", side_effect=fake_fuzzy):
                search_article(
                    text="请按中国公司法检索外商持股",
                    jurisdiction="中国",
                )
        finally:
            reset_current_semantic_gateway(token)

        self.assertEqual(captured["system"], "civil")
        self.assertEqual(captured["text"], "การถือหุ้นของคนต่างชาติในบริษัทไทย")

    def test_without_gateway_keeps_caller_args(self):
        captured: dict[str, str] = {}

        def fake_china(text: str) -> str:
            captured["text"] = text
            return json.dumps({"success": True, "results": []}, ensure_ascii=False)

        with patch(
            "mcp.legal_search_router.china_search_article",
            side_effect=fake_china,
        ):
            search_article(text="劳动合同解除", jurisdiction="")

        self.assertEqual(captured["text"], "劳动合同解除")


if __name__ == "__main__":
    unittest.main()
