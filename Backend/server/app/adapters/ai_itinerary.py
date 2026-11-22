import httpx

from app.config import settings
from app.core.errors import ApiError
from app.services.itinerary_fallback import build_fallback


def map_response(response: dict[str, object]) -> list[dict[str, object]]:
    if not isinstance(response, dict):
        raise ValueError("AI response must be an object")
    plan = response.get("plan", response.get("steps"))
    if not isinstance(plan, list):
        raise ValueError("AI response plan must be a list")
    return [dict(row) for row in plan if isinstance(row, dict)]


def generate_plan(payload: dict[str, object]) -> list[dict[str, object]]:
    if settings.mock_ai:
        return build_fallback(payload)
    if not settings.ai_itinerary_url or not settings.ai_itinerary_key:
        raise ApiError(503, "AI_UNAVAILABLE", "Dịch vụ tạo lịch trình chưa sẵn sàng")
    try:
        profile = payload["profile"]
        candidates = payload["candidates"]
        if not isinstance(profile, dict) or not isinstance(candidates, list):
            raise ValueError("Invalid itinerary request")
        wire_payload = {
            "date": payload["date"],
            "slots": payload["slots"],
            "profile": {
                key: profile[key]
                for key in (
                    "favFoods",
                    "favRestaurantIds",
                    "topRatedRestaurantIds",
                    "recentSearchFoodIds",
                    "avgPriceLevel",
                )
            },
            "candidates": [
                {
                    key: candidate[key]
                    for key in (
                        "id",
                        "name",
                        "district",
                        "priceLevel",
                        "open",
                        "close",
                        "mealSlots",
                        "foods",
                        "rating",
                    )
                }
                for candidate in candidates
                if isinstance(candidate, dict)
            ],
        }
        with httpx.Client(timeout=settings.ai_timeout_ms / 1000) as client:
            response = client.post(
                settings.ai_itinerary_url,
                json=wire_payload,
                headers={"Authorization": f"Bearer {settings.ai_itinerary_key}"},
            )
            response.raise_for_status()
            return map_response(response.json())
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise ApiError(503, "AI_UNAVAILABLE", "Không thể tạo lịch trình lúc này") from exc
