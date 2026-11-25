import logging

from app.config import settings
from app.core.errors import ApiError
from app.services.itinerary_fallback import build_fallback

logger = logging.getLogger(__name__)


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
    if not settings.ai_itinerary_url or not settings.ai_itinerary_key or not settings.ai_itinerary_model:
        logger.error(
            "Groq itinerary configuration incomplete (url=%s, key=%s, model=%s)",
            bool(settings.ai_itinerary_url),
            bool(settings.ai_itinerary_key),
            bool(settings.ai_itinerary_model),
        )
        raise ApiError(503, "AI_UNAVAILABLE", "Dịch vụ tạo lịch trình chưa sẵn sàng")

    from app.adapters.groq_itinerary import generate_plan as generate_groq_plan

    return generate_groq_plan(payload)
