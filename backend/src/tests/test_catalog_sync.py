import json
import os
import tempfile
import unittest

import closedloop.core.config as config_module
from closedloop.mock_data_generator import generate_mock_db_from_catalog, generate_reservations_from_mock_db
from closedloop.utils.mock_db import load_mock_data


class TestCatalogSync(unittest.TestCase):
    def test_catalog_edit_syncs_to_mock_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog_dir = os.path.join(tmp, "catalog")
            repo_dir = os.path.join(tmp, "repo")
            os.makedirs(catalog_dir, exist_ok=True)
            os.makedirs(repo_dir, exist_ok=True)

            keys = ["MOCK_DB_CATALOG_DIR", "MOCK_DB_REPO_DIR"]
            old_env = {k: os.environ.get(k) for k in keys}
            try:
                os.environ["MOCK_DB_CATALOG_DIR"] = catalog_dir
                os.environ["MOCK_DB_REPO_DIR"] = repo_dir
                config_module.get_config.cache_clear()

                restaurants_catalog = [
                    {
                        "id": "restaurant_1001",
                        "name": "我自定义的餐厅名",
                        "category": "restaurant",
                        "sub_category": "粤菜",
                        "district": "CBD核心商圈",
                        "address": "CBD核心商圈附近某商场4F",
                        "latitude": 1.234,
                        "longitude": 2.345,
                        "business_hours": "10:00-22:00",
                        "indoor": True,
                        "review_keywords": ["适合约会", "环境安静", "可做不辣"],
                        "suitable_groups": ["couple", "solo"],
                        "experience_tag": ["安静", "轻松", "仪式感"],
                        "romantic_score_derived": {
                            "score": 4.2,
                            "confidence": 0.9,
                            "source": {
                                "sub_category": "粤菜",
                                "matched_review_keywords": ["适合约会"],
                                "rule": "romantic_from_sub_category_and_keywords",
                            },
                        },
                        "photo_score_derived": {
                            "score": 2.8,
                            "confidence": 0.7,
                            "source": {
                                "sub_category": "粤菜",
                                "matched_review_keywords": ["环境安静"],
                                "rule": "photo_from_sub_category_and_keywords",
                            },
                        },
                        "onsite_walking_level_estimated": {
                            "score": 1.2,
                            "confidence": 0.8,
                            "source": {
                                "sub_category": "粤菜",
                                "matched_review_keywords": [],
                                "rule": "walking_from_sub_category_and_keywords",
                            },
                        },
                        "noise_level_estimated": {
                            "score": 1.8,
                            "confidence": 0.8,
                            "source": {
                                "sub_category": "粤菜",
                                "matched_review_keywords": ["环境安静"],
                                "rule": "noise_from_sub_category_and_keywords",
                            },
                        },
                        "kid_menu_status": "possible",
                        "stroller_friendly_status": "likely",
                        "child_facility_tags": ["儿童座椅", "室内"],
                        "child_friendly_score_derived": {
                            "score": 3.5,
                            "confidence": 0.8,
                            "source": {
                                "sub_category": "粤菜",
                                "matched_review_keywords": ["环境安静"],
                                "rule": "child_friendly_from_facilities_and_keywords",
                            },
                        },
                        "rating": 4.9,
                        "tags": ["测试"],
                        "combos": [
                            {
                                "combo_id": "c_1001_1",
                                "name": "自定义套餐",
                                "price": 99.0,
                                "description": "desc",
                                "features": "features",
                                "duration_mins": 60,
                                "duration_std_dev": 10.0,
                                "suitable_time_slots": ["lunch"],
                                "requires_booking": True,
                            }
                        ],
                    }
                ]

                activities_catalog = [
                    {
                        "id": "activity_1001",
                        "name": "我自定义的活动名",
                        "category": "activity",
                        "sub_category": "电影院",
                        "district": "大学城商圈",
                        "address": "大学城商圈某影院L3",
                        "latitude": 3.21,
                        "longitude": 1.11,
                        "business_hours": "09:00-22:00",
                        "indoor": True,
                        "review_keywords": ["适合亲子", "周末人多", "建议预约"],
                        "suitable_groups": ["family", "adult"],
                        "age_range": ["7-10", "adult"],
                        "experience_tag": ["亲子友好", "互动感强", "室内兜底"],
                        "romantic_score_derived": {
                            "score": 0.8,
                            "confidence": 0.8,
                            "source": {
                                "sub_category": "电影院",
                                "matched_review_keywords": [],
                                "rule": "romantic_from_sub_category_and_keywords",
                            },
                        },
                        "photo_score_derived": {
                            "score": 1.2,
                            "confidence": 0.7,
                            "source": {
                                "sub_category": "电影院",
                                "matched_review_keywords": [],
                                "rule": "photo_from_sub_category_and_keywords",
                            },
                        },
                        "onsite_walking_level_estimated": {
                            "score": 1.0,
                            "confidence": 0.8,
                            "source": {
                                "sub_category": "电影院",
                                "matched_review_keywords": [],
                                "rule": "walking_from_sub_category_and_keywords",
                            },
                        },
                        "noise_level_estimated": {
                            "score": 2.0,
                            "confidence": 0.7,
                            "source": {
                                "sub_category": "电影院",
                                "matched_review_keywords": ["周末人多"],
                                "rule": "noise_from_sub_category_and_keywords",
                            },
                        },
                        "is_free": False,
                        "rating": 4.8,
                        "tags": ["测试"],
                        "packages": [
                            {
                                "package_id": "pkg_1001_1",
                                "name": "自定义场次",
                                "price": 45.0,
                                "description": "desc",
                                "features": "features",
                                "requires_booking": True,
                                "duration_mins": 120,
                                "duration_std_dev": 2.0,
                                "start_time": "10:00",
                                "available_stock": 123,
                            }
                        ],
                    }
                ]

                with open(os.path.join(catalog_dir, "restaurants_catalog.json"), "w", encoding="utf-8") as f:
                    json.dump(restaurants_catalog, f, ensure_ascii=False, indent=2)
                with open(os.path.join(catalog_dir, "activities_catalog.json"), "w", encoding="utf-8") as f:
                    json.dump(activities_catalog, f, ensure_ascii=False, indent=2)
                with open(os.path.join(catalog_dir, "add_ons_catalog.json"), "w", encoding="utf-8") as f:
                    json.dump(
                        [
                            {
                                "id": "gift_shop_1001",
                                "name": "我自定义的礼品店",
                                "category": "gift_shop",
                                "sub_category": "鲜花",
                                "district": "滨江风景区",
                                "address": "滨江风景区花店A座",
                                "latitude": 0.12,
                                "longitude": 4.56,
                                "business_hours": "10:00-21:00",
                                "indoor": True,
                                "review_keywords": ["氛围感", "适合约会", "可同城配送"],
                                "suitable_groups": ["couple"],
                                "experience_tag": ["惊喜感", "仪式感", "浪漫"],
                                "romantic_score_derived": {
                                    "score": 4.8,
                                    "confidence": 0.95,
                                    "source": {
                                        "sub_category": "鲜花",
                                        "matched_review_keywords": ["氛围感", "适合约会"],
                                        "rule": "romantic_from_sub_category_and_keywords",
                                    },
                                },
                                "photo_score_derived": {
                                    "score": 3.5,
                                    "confidence": 0.8,
                                    "source": {
                                        "sub_category": "鲜花",
                                        "matched_review_keywords": [],
                                        "rule": "photo_from_sub_category_and_keywords",
                                    },
                                },
                                "onsite_walking_level_estimated": {
                                    "score": 0.6,
                                    "confidence": 0.8,
                                    "source": {
                                        "sub_category": "鲜花",
                                        "matched_review_keywords": [],
                                        "rule": "walking_from_sub_category_and_keywords",
                                    },
                                },
                                "noise_level_estimated": {
                                    "score": 1.0,
                                    "confidence": 0.7,
                                    "source": {
                                        "sub_category": "鲜花",
                                        "matched_review_keywords": [],
                                        "rule": "noise_from_sub_category_and_keywords",
                                    },
                                },
                                "gift_type": "flower",
                                "delivery_to_restaurant": True,
                                "surprise_score_derived": {
                                    "score": 4.8,
                                    "confidence": 0.9,
                                    "source": {
                                        "sub_category": "鲜花",
                                        "matched_review_keywords": ["氛围感", "适合约会"],
                                        "rule": "surprise_from_gift_type_and_delivery",
                                    },
                                },
                                "rating": 4.9,
                                "tags": ["测试"],
                                "delivery_time_mins": 30,
                                "delivery_time_std_dev": 5.0,
                                "gifts": [
                                    {
                                        "gift_id": "g_1001_1",
                                        "name": "自定义礼物",
                                        "price": 19.9,
                                        "description": "desc",
                                        "features": "features",
                                        "stock": 10,
                                    }
                                ],
                            }
                        ],
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )

                generated = generate_mock_db_from_catalog(
                    restaurants_catalog=restaurants_catalog,
                    activities_catalog=activities_catalog,
                    add_ons_catalog=[
                        {
                            "id": "gift_shop_1001",
                            "name": "我自定义的礼品店",
                            "category": "gift_shop",
                            "sub_category": "鲜花",
                            "district": "滨江风景区",
                            "address": "滨江风景区花店A座",
                            "latitude": 0.12,
                            "longitude": 4.56,
                            "business_hours": "10:00-21:00",
                            "indoor": True,
                            "review_keywords": ["氛围感", "适合约会", "可同城配送"],
                            "suitable_groups": ["couple"],
                            "experience_tag": ["惊喜感", "仪式感", "浪漫"],
                            "romantic_score_derived": {
                                "score": 4.8,
                                "confidence": 0.95,
                                "source": {
                                    "sub_category": "鲜花",
                                    "matched_review_keywords": ["氛围感", "适合约会"],
                                    "rule": "romantic_from_sub_category_and_keywords",
                                },
                            },
                            "photo_score_derived": {
                                "score": 3.5,
                                "confidence": 0.8,
                                "source": {
                                    "sub_category": "鲜花",
                                    "matched_review_keywords": [],
                                    "rule": "photo_from_sub_category_and_keywords",
                                },
                            },
                            "onsite_walking_level_estimated": {
                                "score": 0.6,
                                "confidence": 0.8,
                                "source": {
                                    "sub_category": "鲜花",
                                    "matched_review_keywords": [],
                                    "rule": "walking_from_sub_category_and_keywords",
                                },
                            },
                            "noise_level_estimated": {
                                "score": 1.0,
                                "confidence": 0.7,
                                "source": {
                                    "sub_category": "鲜花",
                                    "matched_review_keywords": [],
                                    "rule": "noise_from_sub_category_and_keywords",
                                },
                            },
                            "gift_type": "flower",
                            "delivery_to_restaurant": True,
                            "surprise_score_derived": {
                                "score": 4.8,
                                "confidence": 0.9,
                                "source": {
                                    "sub_category": "鲜花",
                                    "matched_review_keywords": ["氛围感", "适合约会"],
                                    "rule": "surprise_from_gift_type_and_delivery",
                                },
                            },
                            "rating": 4.9,
                            "tags": ["测试"],
                            "delivery_time_mins": 30,
                            "delivery_time_std_dev": 5.0,
                            "gifts": [
                                {
                                    "gift_id": "g_1001_1",
                                    "name": "自定义礼物",
                                    "price": 19.9,
                                    "description": "desc",
                                    "features": "features",
                                    "stock": 10,
                                }
                            ],
                        }
                    ],
                )
                reservations = generate_reservations_from_mock_db(generated)

                with open(os.path.join(repo_dir, "restaurants.json"), "w", encoding="utf-8") as f:
                    json.dump(generated["restaurants"], f, ensure_ascii=False, indent=2)
                with open(os.path.join(repo_dir, "activities.json"), "w", encoding="utf-8") as f:
                    json.dump(generated["activity_venues"], f, ensure_ascii=False, indent=2)
                with open(os.path.join(repo_dir, "add_ons.json"), "w", encoding="utf-8") as f:
                    json.dump(generated["gift_shops"], f, ensure_ascii=False, indent=2)
                with open(os.path.join(repo_dir, "reservations.json"), "w", encoding="utf-8") as f:
                    json.dump(reservations, f, ensure_ascii=False, indent=2)

                restaurants = load_mock_data("restaurants.json")
                activities = load_mock_data("activities.json")
                add_ons = load_mock_data("add_ons.json")

                self.assertEqual(restaurants[0]["name"], "我自定义的餐厅名")
                self.assertEqual(activities[0]["name"], "我自定义的活动名")
                self.assertEqual(add_ons[0]["name"], "我自定义的礼品店")
                self.assertEqual(restaurants[0]["id"], "restaurant_1001")
                self.assertEqual(activities[0]["id"], "activity_1001")
                self.assertEqual(add_ons[0]["id"], "gift_shop_1001")
                self.assertEqual(activities[0]["sub_category"], "电影院")
                self.assertEqual(activities[0]["business_hours"], "09:00-22:00")
                self.assertEqual(restaurants[0]["suitable_groups"], ["couple", "solo"])
                self.assertEqual(activities[0]["age_range"], ["7-10", "adult"])
                self.assertEqual(add_ons[0]["experience_tag"], ["惊喜感", "仪式感", "浪漫"])
                self.assertEqual(restaurants[0]["romantic_score_derived"]["source"]["rule"], "romantic_from_sub_category_and_keywords")
                self.assertEqual(restaurants[0]["kid_menu_status"], "possible")
                self.assertEqual(add_ons[0]["delivery_radius_km"], 5.0)
                self.assertEqual(add_ons[0]["gift_type"], "flower")
                self.assertTrue(add_ons[0]["delivery_to_restaurant"])
            finally:
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
                config_module.get_config.cache_clear()


if __name__ == "__main__":
    unittest.main()
