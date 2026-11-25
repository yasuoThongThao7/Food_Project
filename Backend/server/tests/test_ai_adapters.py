import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.adapters import ai_itinerary, ai_search, groq_itinerary
from app.core.errors import ApiError


class StubHandler(BaseHTTPRequestHandler):
    itinerary_request = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(length)
        if self.path == "/search":
            body = b'{"detections":[{"dish":"mi-quang","score":0.88}]}'
        elif self.path == "/unauthorized":
            body = b'{"error":{"code":"invalid_api_key","message":"Invalid API Key"}}'
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        else:
            StubHandler.itinerary_request = {
                "authorization": self.headers.get("Authorization"),
                "body": json.loads(request_body),
            }
            content = json.dumps(
                {"plan": [{"slot": "breakfast", "restaurantId": 1, "reason": "stub"}]}
            )
            body = json.dumps(
                {"choices": [{"message": {"content": content}}]}
            ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


@pytest.fixture(scope="module")
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.mark.ai_adapters
def test_search_adapter_contract_against_local_stub(stub_server, monkeypatch):
    monkeypatch.setattr(ai_search.settings, "mock_ai", False)
    monkeypatch.setattr(ai_search.settings, "ai_search_url", stub_server + "/search")
    monkeypatch.setattr(ai_search.settings, "ai_search_key", "test-key")
    assert ai_search.detect_foods(b"image", "image/jpeg")[0]["label"] == "mi-quang"


@pytest.mark.ai_adapters
def test_search_map_response_accepts_alternate_field_names():
    mapped = ai_search.map_response(
        {"detections": [{"dish": "banh-xeo", "score": 0.75}]}
    )
    assert mapped == [{"label": "banh-xeo", "confidence": 0.75}]


@pytest.mark.ai_adapters
def test_itinerary_map_response_accepts_alternate_field_names():
    mapped = ai_itinerary.map_response(
        {"steps": [{"slot": "lunch", "restaurantId": 7, "reason": "stub"}]}
    )
    assert mapped[0]["restaurantId"] == 7


@pytest.mark.ai_adapters
def test_itinerary_adapter_contract_against_local_stub(stub_server, monkeypatch):
    monkeypatch.setattr(ai_itinerary.settings, "mock_ai", False)
    monkeypatch.setattr(ai_itinerary.settings, "ai_itinerary_url", stub_server + "/itinerary")
    monkeypatch.setattr(ai_itinerary.settings, "ai_itinerary_key", "test-key")
    monkeypatch.setattr(ai_itinerary.settings, "ai_itinerary_model", "test-model")
    plan = ai_itinerary.generate_plan(
        {
            "date": "2026-11-21",
            "slots": ["breakfast", "lunch", "snack", "dinner"],
            "profile": {
                "favFoods": [],
                "favRestaurantIds": [],
                "topRatedRestaurantIds": [],
                "recentSearchFoodIds": [],
                "avgPriceLevel": 2,
            },
            "candidates": [
                {
                    "id": 1,
                    "name": "Quán Ngon",
                    "district": "Hải Châu",
                    "priceLevel": 2,
                    "open": "06:00",
                    "close": "22:00",
                    "mealSlots": ["breakfast", "lunch", "snack", "dinner"],
                    "foods": ["Mì Quảng"],
                    "foodIds": [3],
                    "rating": 4.5,
                }
            ],
        }
    )
    assert plan[0]["slot"] == "breakfast"
    assert StubHandler.itinerary_request["authorization"] == "Bearer test-key"
    assert StubHandler.itinerary_request["body"]["model"] == "test-model"
    assert StubHandler.itinerary_request["body"]["response_format"] == {"type": "json_object"}
    assert "foodIds" in StubHandler.itinerary_request["body"]["messages"][1]["content"]


def test_itinerary_adapter_requires_model_configuration(monkeypatch):
    monkeypatch.setattr(ai_itinerary.settings, "mock_ai", False)
    monkeypatch.setattr(ai_itinerary.settings, "ai_itinerary_url", "http://example.test")
    monkeypatch.setattr(ai_itinerary.settings, "ai_itinerary_key", "test-key")
    monkeypatch.setattr(ai_itinerary.settings, "ai_itinerary_model", "")
    with pytest.raises(ApiError) as exc_info:
        ai_itinerary.generate_plan({"profile": {}, "candidates": []})
    assert exc_info.value.code == "AI_UNAVAILABLE"


@pytest.mark.ai_adapters
def test_groq_http_error_is_logged_without_logging_api_key(stub_server, monkeypatch, caplog):
    monkeypatch.setattr(groq_itinerary.settings, "ai_itinerary_url", stub_server + "/unauthorized")
    monkeypatch.setattr(groq_itinerary.settings, "ai_itinerary_key", "test-secret")
    monkeypatch.setattr(groq_itinerary.settings, "ai_itinerary_model", "test-model")

    with caplog.at_level(logging.ERROR), pytest.raises(ApiError) as exc_info:
        groq_itinerary.generate_plan({"profile": {}, "candidates": []})

    assert exc_info.value.code == "AI_UNAVAILABLE"
    assert "HTTP 401" in caplog.text
    assert "invalid_api_key" in caplog.text
    assert "Invalid API Key" in caplog.text
    assert "test-secret" not in caplog.text
