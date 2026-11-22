from typing import Any

SLOTS = {
    "breakfast": ("06:00", "09:00", "Bắt đầu ngày mới với món ngon địa phương."),
    "lunch": ("11:00", "13:00", "Thưởng thức bữa trưa đặc sản Đà Nẵng."),
    "snack": ("15:00", "17:00", "Dừng chân ăn nhẹ và khám phá hương vị địa phương."),
    "dinner": ("18:00", "21:00", "Khép lại ngày bằng một bữa tối đáng nhớ."),
}


def build_fallback(payload: dict[str, Any]) -> list[dict[str, Any]]:
    profile = payload.get("profile", {})
    candidates = payload.get("candidates", [])
    if not isinstance(profile, dict) or not isinstance(candidates, list):
        return []
    favorites = set(profile.get("favRestaurantIds", []))
    rated = set(profile.get("topRatedRestaurantIds", []))
    search_ids = set(profile.get("recentSearchFoodIds", []))
    used: set[int] = set()
    plan: list[dict[str, Any]] = []
    for slot in SLOTS:
        options = [
            row
            for row in candidates
            if isinstance(row, dict)
            and slot in row.get("mealSlots", [])
            and row.get("id") not in used
        ]
        if not options:
            continue

        def score(row: dict[str, Any]) -> float:
            restaurant_id = row["id"]
            matching_foods = set(row.get("foodIds", [])) & search_ids
            return (
                3 * (restaurant_id in favorites)
                + 2 * (restaurant_id in rated)
                + bool(matching_foods)
                + float(row.get("rating", 0)) / 5
            )

        selected = max(
            options, key=lambda row: (score(row), float(row.get("rating", 0)), -int(row["id"]))
        )
        selected_id = int(selected["id"])
        used.add(selected_id)
        matching = [
            int(food_id) for food_id in selected.get("foodIds", []) if int(food_id) in search_ids
        ]
        plan.append(
            {
                "slot": slot,
                "restaurantId": selected_id,
                "foodId": matching[0] if matching else (selected.get("foodIds") or [None])[0],
                "reason": SLOTS[slot][2],
            }
        )
    return plan
