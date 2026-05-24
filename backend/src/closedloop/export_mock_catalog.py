import json
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.core.config import REPO_ROOT_DIR, get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.utils.mock_db import load_mock_data


def _resolve_dir(v: str) -> str:
    if not v:
        return ""
    if os.path.isabs(v):
        return os.path.abspath(v)
    return os.path.abspath(os.path.join(REPO_ROOT_DIR, v))


def export_catalog() -> None:
    """Export editable fields into catalog JSON files."""
    config = get_config()
    LoggerManager.setup(config)
    catalog_dir = _resolve_dir(config.data.MOCK_DB_CATALOG_DIR)
    os.makedirs(catalog_dir, exist_ok=True)

    restaurants = load_mock_data("restaurants.json")
    activities = load_mock_data("activities.json")
    add_ons = load_mock_data("add_ons.json")

    restaurants_catalog: list[dict] = []
    for r in restaurants:
        combos = []
        for c in r.get("combos", []) or []:
            combos.append(
                {
                    "combo_id": c.get("combo_id"),
                    "name": c.get("name"),
                    "price": c.get("price"),
                    "description": c.get("description"),
                    "features": c.get("features"),
                    "duration_mins": c.get("duration_mins"),
                    "duration_std_dev": c.get("duration_std_dev"),
                    "suitable_time_slots": c.get("suitable_time_slots"),
                    "requires_booking": c.get("requires_booking"),
                }
            )

        restaurants_catalog.append(
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "category": r.get("category"),
                "sub_category": r.get("sub_category"),
                "district": r.get("district"),
                "address": r.get("address"),
                "latitude": r.get("latitude"),
                "longitude": r.get("longitude"),
                "business_hours": r.get("business_hours"),
                "indoor": r.get("indoor"),
                "review_keywords": r.get("review_keywords"),
                "suitable_groups": r.get("suitable_groups"),
                "experience_tag": r.get("experience_tag"),
                "photo_score_derived": r.get("photo_score_derived"),
                "onsite_walking_level_estimated": r.get("onsite_walking_level_estimated"),
                "noise_level_estimated": r.get("noise_level_estimated"),
                "kid_menu_status": r.get("kid_menu_status"),
                "stroller_friendly_status": r.get("stroller_friendly_status"),
                "child_facility_tags": r.get("child_facility_tags"),
                "child_friendly_score_derived": r.get("child_friendly_score_derived"),
                "rating": r.get("rating"),
                "tags": r.get("tags"),
                "combos": combos,
            }
        )

    activities_catalog: list[dict] = []
    for v in activities:
        packages = []
        for p in v.get("packages", []) or []:
            packages.append(
                {
                    "package_id": p.get("package_id"),
                    "name": p.get("name"),
                    "price": p.get("price"),
                    "description": p.get("description"),
                    "features": p.get("features"),
                    "requires_booking": p.get("requires_booking"),
                    "duration_mins": p.get("duration_mins"),
                    "duration_std_dev": p.get("duration_std_dev"),
                    "start_time": p.get("start_time"),
                }
            )

        activities_catalog.append(
            {
                "id": v.get("id"),
                "name": v.get("name"),
                "category": v.get("category"),
                "sub_category": v.get("sub_category"),
                "district": v.get("district"),
                "address": v.get("address"),
                "latitude": v.get("latitude"),
                "longitude": v.get("longitude"),
                "business_hours": v.get("business_hours"),
                "indoor": v.get("indoor"),
                "review_keywords": v.get("review_keywords"),
                "suitable_groups": v.get("suitable_groups"),
                "age_range": v.get("age_range"),
                "experience_tag": v.get("experience_tag"),
                "photo_score_derived": v.get("photo_score_derived"),
                "onsite_walking_level_estimated": v.get("onsite_walking_level_estimated"),
                "noise_level_estimated": v.get("noise_level_estimated"),
                "is_free": v.get("is_free"),
                "rating": v.get("rating"),
                "tags": v.get("tags"),
                "packages": packages,
            }
        )

    with open(os.path.join(catalog_dir, "restaurants_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(restaurants_catalog, f, ensure_ascii=False, indent=2)
    with open(os.path.join(catalog_dir, "activities_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(activities_catalog, f, ensure_ascii=False, indent=2)
    add_ons_catalog: list[dict] = []
    for s in add_ons:
        gifts = []
        for g in s.get("gifts", []) or []:
            gifts.append(
                {
                    "gift_id": g.get("gift_id"),
                    "name": g.get("name"),
                    "price": g.get("price"),
                    "description": g.get("description"),
                    "features": g.get("features"),
                    "stock": g.get("stock"),
                }
            )
        add_ons_catalog.append(
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "category": s.get("category"),
                "sub_category": s.get("sub_category"),
                "district": s.get("district"),
                "address": s.get("address"),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
                "business_hours": s.get("business_hours"),
                "indoor": s.get("indoor"),
                "review_keywords": s.get("review_keywords"),
                "suitable_groups": s.get("suitable_groups"),
                "experience_tag": s.get("experience_tag"),
                "photo_score_derived": s.get("photo_score_derived"),
                "onsite_walking_level_estimated": s.get("onsite_walking_level_estimated"),
                "noise_level_estimated": s.get("noise_level_estimated"),
                "gift_type": s.get("gift_type"),
                "delivery_to_restaurant": s.get("delivery_to_restaurant"),
                "surprise_score_derived": s.get("surprise_score_derived"),
                "rating": s.get("rating"),
                "tags": s.get("tags"),
                "delivery_time_mins": s.get("delivery_time_mins"),
                "delivery_time_std_dev": s.get("delivery_time_std_dev"),
                "delivery_radius_km": s.get("delivery_radius_km"),
                "gifts": gifts,
            }
        )

    with open(os.path.join(catalog_dir, "add_ons_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(add_ons_catalog, f, ensure_ascii=False, indent=2)

    logger.info(
        f"phase=export_catalog | restaurants_catalog={len(restaurants_catalog)} | activities_catalog={len(activities_catalog)} | add_ons_catalog={len(add_ons_catalog)} | dir={catalog_dir}"
    )


if __name__ == "__main__":
    export_catalog()
