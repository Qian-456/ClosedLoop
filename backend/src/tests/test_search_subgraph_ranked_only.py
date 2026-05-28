import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.search_subgraph.builder import build_subgraph_search


class TestSearchSubgraphRankedOnly(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = build_subgraph_search()

    def test_keyword_score_caps_at_60(self):
        state = {
            "session_id": "thread-1",
            "category": "restaurant",
            "user_request": "牛肉 火锅 烧烤",
            "subcatory": None,
            "top_k": 5,
            "candidates": [
                {
                    "combo_id": "c1",
                    "id": "c1",
                    "name": "牛肉火锅烧烤三合一",
                    "merchant_name": "牛肉火锅烧烤店",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 0,
                    "distance_km": 1.0,
                    "price": 100,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                }
            ],
        }

        out = self.graph.invoke(state)
        results = out.get("results", [])
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["keyword_score"], 60.0)

    def test_field_score_cap_and_hit(self):
        state = {
            "session_id": "thread-1",
            "category": "restaurant",
            "user_request": "想找亲子 安静 室内的地方",
            "subcatory": None,
            "top_k": 5,
            "candidates": [
                {
                    "combo_id": "c2",
                    "id": "c2",
                    "name": "亲子室内乐园套餐",
                    "merchant_name": "亲子餐厅",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": ["安静", "低噪"],
                    "child_facility_tags": ["儿童乐园"],
                    "kid_menu_status": "available",
                    "stroller_friendly_status": "good",
                    "noise_level_estimated": {"level": "low"},
                    "indoor": True,
                    "score": 0,
                    "distance_km": 1.0,
                    "price": 100,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                }
            ],
        }

        out = self.graph.invoke(state)
        results = out.get("results", [])
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["field_score"], 30.0)
        self.assertTrue(any("亲子" in r for r in results[0]["hit_reasons"]))
        self.assertTrue(any("安静" in r for r in results[0]["hit_reasons"]))
        self.assertTrue(any("室内" in r for r in results[0]["hit_reasons"]))

    def test_negative_keyword_filters_out(self):
        state = {
            "session_id": "thread-1",
            "category": "restaurant",
            "user_request": "不要辣",
            "subcatory": None,
            "top_k": 5,
            "candidates": [
                {
                    "combo_id": "c3",
                    "id": "c3",
                    "name": "川味火锅",
                    "merchant_name": "辣辣火锅店",
                    "tags": ["辣"],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 0,
                    "distance_km": 1.0,
                    "price": 100,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                }
            ],
        }

        out = self.graph.invoke(state)
        self.assertEqual(out.get("results", []), [])

    def test_subcatory_bonus_applies(self):
        state = {
            "session_id": "thread-1",
            "category": "restaurant",
            "user_request": "火锅",
            "subcatory": "dinner",
            "top_k": 5,
            "candidates": [
                {
                    "combo_id": "c4",
                    "id": "c4",
                    "name": "火锅套餐",
                    "merchant_name": "火锅店",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 0,
                    "distance_km": 1.0,
                    "price": 100,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                }
            ],
        }

        out = self.graph.invoke(state)
        results = out.get("results", [])
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["subcatory_bonus"], 10.0)

    def test_tie_break_order(self):
        state = {
            "session_id": "thread-1",
            "category": "restaurant",
            "user_request": "火锅",
            "subcatory": None,
            "top_k": 5,
            "candidates": [
                {
                    "combo_id": "c10",
                    "id": "c10",
                    "name": "火锅套餐",
                    "merchant_name": "A店",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 50,
                    "distance_km": 2.0,
                    "price": 100,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                },
                {
                    "combo_id": "c11",
                    "id": "c11",
                    "name": "火锅套餐",
                    "merchant_name": "B店",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 40,
                    "distance_km": 1.0,
                    "price": 10,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                },
            ],
        }

        out = self.graph.invoke(state)
        results = out.get("results", [])
        self.assertEqual([r["id"] for r in results[:2]], ["c10", "c11"])

    def test_keyword_delimiters_are_supported(self):
        state = {
            "session_id": "thread-1",
            "category": "restaurant",
            "user_request": "儿童友好,安静|室内",
            "subcatory": None,
            "top_k": 5,
            "candidates": [
                {
                    "combo_id": "c20",
                    "id": "c20",
                    "name": "儿童友好安静室内套餐",
                    "merchant_name": "家庭餐厅",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 0,
                    "distance_km": 1.0,
                    "price": 100,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                }
            ],
        }

        out = self.graph.invoke(state)
        results = out.get("results", [])
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["keyword_score"], 60.0)

    def test_stopwords_do_not_dominate_ranking(self):
        state = {
            "session_id": "thread-1",
            "category": "restaurant",
            "user_request": "餐厅 儿童友好",
            "subcatory": None,
            "top_k": 5,
            "candidates": [
                {
                    "combo_id": "rest",
                    "id": "rest",
                    "name": "普通套餐",
                    "merchant_name": "餐厅",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 100,
                    "distance_km": 0.5,
                    "price": 10,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                },
                {
                    "combo_id": "kid",
                    "id": "kid",
                    "name": "儿童友好套餐",
                    "merchant_name": "家庭乐园",
                    "tags": [],
                    "features": "",
                    "description": "",
                    "review_keywords": [],
                    "score": 10,
                    "distance_km": 5.0,
                    "price": 100,
                    "subcatory": "dinner",
                    "source": "ranked_only",
                },
            ],
        }

        out = self.graph.invoke(state)
        results = out.get("results", [])
        self.assertTrue(results)
        self.assertEqual(results[0]["id"], "kid")


if __name__ == "__main__":
    unittest.main()
