import httpx

from app.config import settings
from app.core.errors import ApiError


def map_response(response: dict[str, object]) -> list[dict[str, str | float]]:
    if not isinstance(response, dict):
        raise ValueError("AI response must be an object")
    predictions = response.get("predictions")
    if predictions is None:
        predictions = response.get("detections", [])
    if not isinstance(predictions, list):
        raise ValueError("AI response predictions must be a list")
    mapped: list[dict[str, str | float]] = []
    seen: set[str] = set()
    for item in predictions:
        if not isinstance(item, dict):
            continue
        label = item.get("label", item.get("dish"))
        confidence = item.get("confidence", item.get("score"))
        if (
            not isinstance(label, str)
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
        ):
            continue
        if not 0 <= confidence <= 1 or confidence < settings.ai_min_conf or label in seen:
            continue
        mapped.append({"label": label, "confidence": float(confidence)})
        seen.add(label)
    return sorted(mapped, key=lambda row: float(row["confidence"]), reverse=True)[:5]


def detect_foods(data: bytes, mime: str) -> list[dict[str, str | float]]:
    if settings.mock_ai:
        return [
            {"label": "mi-quang", "confidence": 0.99},
            {"label": "banh-xeo", "confidence": 0.91},
        ]
    if not settings.ai_search_url or not settings.ai_search_key:
        raise ApiError(503, "AI_UNAVAILABLE", "Dịch vụ nhận diện món ăn chưa sẵn sàng")
    try:
        with httpx.Client(timeout=settings.ai_timeout_ms / 1000) as client:
            response = client.post(
                settings.ai_search_url,
                files={"image": ("upload", data, mime)},
                headers={"Authorization": f"Bearer {settings.ai_search_key}"},
            )
            response.raise_for_status()
            return map_response(response.json())
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise ApiError(503, "AI_UNAVAILABLE", "Không thể nhận diện hình ảnh lúc này") from exc
