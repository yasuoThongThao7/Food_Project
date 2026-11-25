from datetime import date, timedelta

from sqlalchemy import select

from app.adapters import ai_itinerary, ai_search
from app.db import get_db
from app.models import Restaurant, Review, User
from tests.conftest import token


def auth(token_value):
    return {"Authorization": f"Bearer {token_value}"}


def test_register_login_and_validation_envelope(client):
    invalid = client.post(
        "/auth/register", json={"email": "new@example.com", "password": "short", "name": "New"}
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "VALIDATION"
    registered = client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "long-password", "name": "New"},
    )
    assert registered.status_code == 200
    assert registered.json()["data"]["user"]["email"] == "new@example.com"
    assert (
        client.post(
            "/auth/login", json={"email": "new@example.com", "password": "bad-pass"}
        ).status_code
        == 401
    )


def test_auth_rechecks_banned_status(client):
    jwt = token(client)
    with next(client.app.dependency_overrides[get_db]()) as db:
        user = db.scalar(select(User).where(User.email == "user@example.com"))
        user.is_banned, user.ban_reason = True, "Vi phạm quy định"
        db.commit()
    response = client.get("/auth/me", headers=auth(jwt))
    assert response.status_code == 403
    assert "Vi phạm quy định" in response.json()["error"]["message"]


def test_public_food_restaurant_articles_and_missing_items(client):
    health = client.get("/health").json()
    assert health["data"] == {"status": "ok"}
    assert client.get("/api/health").json() == health
    assert "meta" not in health
    assert client.get("/foods").json()["meta"]["total"] == 1
    assert client.get("/foods?limit=0").status_code == 400
    assert client.get(f"/foods/{client.food_id}").status_code == 200
    assert client.get("/foods/9999").status_code == 404
    assert client.get("/restaurants").status_code == 200
    assert client.get("/restaurants?sort=unknown").status_code == 400
    assert client.get(f"/restaurants/{client.restaurant_id}").json()["data"]["isFavorite"] is False
    assert client.get("/restaurants/9999").status_code == 404
    assert client.get("/restaurants/9999/reviews").status_code == 404
    assert client.get("/articles").status_code == 200
    assert client.get("/articles?limit=0").status_code == 400
    assert client.get("/articles/missing").status_code == 404
    wrong_method = client.post("/health")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["ok"] is False


def test_search_image_maps_labels_and_unmatched(client, monkeypatch):
    monkeypatch.setattr(
        ai_search,
        "detect_foods",
        lambda data, mime: [
            {"label": "mi-quang", "confidence": 0.9},
            {"label": "unknown", "confidence": 0.7},
        ],
    )
    response = client.post(
        "/search/image", files={"image": ("food.png", b"\x89PNG\r\n\x1a\nphoto", "image/png")}
    )
    assert response.status_code == 200
    assert response.json()["data"]["foods"][0]["food"]["slug"] == "mi-quang"
    assert response.json()["data"]["unmatched"] == ["unknown"]
    invalid = client.post("/search/image", files={"image": ("bad.png", b"nope", "image/png")})
    assert invalid.status_code == 400


def test_history_and_favorites(client):
    jwt = token(client)
    assert client.get("/auth/me", headers=auth(jwt)).json()["data"]["email"] == "user@example.com"
    response = client.post(
        "/search/image",
        headers=auth(jwt),
        files={"image": ("x.png", b"\x89PNG\r\n\x1a\nx", "image/png")},
    )
    assert response.status_code == 200
    assert client.get("/search/history", headers=auth(jwt)).status_code == 200
    assert client.delete("/search/history", headers=auth(jwt)).status_code == 200
    assert (
        client.post(
            "/favorites", headers=auth(jwt), json={"targetType": "FOOD", "targetId": client.food_id}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/favorites",
            headers=auth(jwt),
            json={"targetType": "INVALID", "targetId": client.food_id},
        ).status_code
        == 400
    )
    assert len(client.get("/favorites", headers=auth(jwt)).json()["data"]["foods"]) == 1
    assert client.delete(f"/favorites/FOOD/{client.food_id}", headers=auth(jwt)).status_code == 200
    assert client.delete(f"/favorites/FOOD/{client.food_id}", headers=auth(jwt)).status_code == 404


def test_review_upsert_recalculates_aggregate(client):
    jwt = token(client)
    path = f"/restaurants/{client.restaurant_id}/reviews"
    assert (
        client.post(path, headers=auth(jwt), json={"rating": 6, "comment": "bad"}).status_code
        == 400
    )
    first = client.post(path, headers=auth(jwt), json={"rating": 3, "comment": "Ổn"})
    assert first.status_code == 200
    second = client.post(path, headers=auth(jwt), json={"rating": 5, "comment": "Rất ngon"})
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert client.get(path).json()["meta"]["total"] == 1
    with next(client.app.dependency_overrides[get_db]()) as db:
        review_count = len(db.scalars(select(Review)).all())
        assert review_count == 1
        restaurant = db.get(Restaurant, client.restaurant_id)
        assert restaurant.rating_avg == 5
        assert restaurant.rating_count == 1


def test_itinerary_invalid_ai_falls_back_and_cache_does_not_call_again(client, monkeypatch):
    jwt = token(client)
    calls = []

    def invalid(payload):
        calls.append(payload)
        return [{"slot": "lunch", "restaurantId": -1, "reason": "invalid"}]

    monkeypatch.setattr(ai_itinerary, "generate_plan", invalid)
    day = (date.today() + timedelta(days=1)).isoformat()
    first = client.post("/itinerary/generate", headers=auth(jwt), json={"date": day})
    second = client.post("/itinerary/generate", headers=auth(jwt), json={"date": day})
    assert first.status_code == 200
    assert first.json()["data"]["source"] == "FALLBACK"
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert len(calls) == 1
    regenerated = client.post(
        "/itinerary/generate",
        headers=auth(jwt),
        json={"date": day, "forceNew": True},
    )
    assert regenerated.status_code == 200
    assert regenerated.json()["data"]["id"] != first.json()["data"]["id"]
    assert len(calls) == 2
    assert client.get("/itinerary", headers=auth(jwt)).status_code == 200
    assert (
        client.get(f"/itinerary/{first.json()['data']['id']}", headers=auth(jwt)).status_code == 200
    )
    assert client.get("/itinerary/9999", headers=auth(jwt)).status_code == 404
    second_token = client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "password-123", "name": "Other"},
    ).json()["data"]["token"]
    assert (
        client.get(
            f"/itinerary/{first.json()['data']['id']}", headers=auth(second_token)
        ).status_code
        == 403
    )


def test_sixth_new_itinerary_is_rate_limited(client, monkeypatch):
    jwt = token(client)
    monkeypatch.setattr(ai_itinerary, "generate_plan", lambda payload: [])
    for offset in range(5):
        day = (date.today() + timedelta(days=offset + 2)).isoformat()
        assert (
            client.post("/itinerary/generate", headers=auth(jwt), json={"date": day}).status_code
            == 200
        )
    day = (date.today() + timedelta(days=20)).isoformat()
    response = client.post("/itinerary/generate", headers=auth(jwt), json={"date": day})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT"


def test_admin_authorization_ban_and_crud(client):
    user_token = token(client)
    assert client.get("/admin/stats", headers=auth(user_token)).status_code == 403
    admin_token = token(client, "admin@example.com")
    assert client.get("/admin/stats", headers=auth(admin_token)).status_code == 200
    assert client.get("/admin/users", headers=auth(admin_token)).status_code == 200
    assert (
        client.patch(
            f"/admin/users/{client.user_id}/ban",
            headers=auth(admin_token),
            json={"banned": True, "reason": "test"},
        ).status_code
        == 200
    )
    assert client.get("/auth/me", headers=auth(user_token)).status_code == 403
    assert (
        client.patch(
            f"/admin/users/{client.admin_id}/ban", headers=auth(admin_token), json={"banned": True}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/admin/users/9999/ban", headers=auth(admin_token), json={"banned": True}
        ).status_code
        == 404
    )
    assert client.delete("/search/history").status_code == 401


def test_admin_food_article_and_restaurant_operations(client):
    admin_token = token(client, "admin@example.com")
    headers = auth(admin_token)
    food_payload = {
        "slug": "new-food",
        "name": "Món mới",
        "aiLabel": "new-food",
        "category": "other",
        "priceMin": 1,
        "priceMax": 2,
    }
    assert (
        client.post(
            "/admin/foods", headers=headers, json={**food_payload, "category": "invalid"}
        ).status_code
        == 400
    )
    food = client.post("/admin/foods", headers=headers, json=food_payload)
    assert food.status_code == 200
    food_id = food.json()["data"]["id"]
    assert (
        client.put(
            f"/admin/foods/{food_id}", headers=headers, json={**food_payload, "name": "Món sửa"}
        ).status_code
        == 200
    )
    assert client.delete(f"/admin/foods/{food_id}", headers=headers).status_code == 200
    assert client.put("/admin/foods/9999", headers=headers, json=food_payload).status_code == 404
    assert client.delete("/admin/foods/9999", headers=headers).status_code == 404
    article_payload = {"slug": "test-article", "title": "Bài viết", "isPublished": True}
    assert (
        client.post("/admin/articles", headers=headers, json={"slug": "invalid"}).status_code == 400
    )
    article = client.post("/admin/articles", headers=headers, json=article_payload)
    assert article.status_code == 200
    article_id = article.json()["data"]["id"]
    assert client.get("/articles/test-article").status_code == 200
    assert (
        client.put(
            f"/admin/articles/{article_id}", headers=headers, json=article_payload
        ).status_code
        == 200
    )
    assert client.delete(f"/admin/articles/{article_id}", headers=headers).status_code == 200
    assert (
        client.put("/admin/articles/9999", headers=headers, json=article_payload).status_code == 404
    )
    assert client.delete("/admin/articles/9999", headers=headers).status_code == 404
    restaurant_payload = {
        "slug": "new-restaurant",
        "name": "Nhà hàng",
        "address": "Trần Phú",
        "district": "Hải Châu",
        "lat": 16.0,
        "lng": 108.1,
        "priceLevel": 1,
    }
    restaurant = client.post("/admin/restaurants", headers=headers, json=restaurant_payload)
    assert restaurant.status_code == 200
    restaurant_id = restaurant.json()["data"]["id"]
    assert (
        client.put(
            f"/admin/restaurants/{restaurant_id}", headers=headers, json=restaurant_payload
        ).status_code
        == 200
    )
    assert client.delete(f"/admin/restaurants/{restaurant_id}", headers=headers).status_code == 200
    assert (
        client.put("/admin/restaurants/9999", headers=headers, json=restaurant_payload).status_code
        == 404
    )
    assert client.delete("/admin/restaurants/9999", headers=headers).status_code == 404
    restaurant_payload.update({"slug": "invalid", "lat": 20, "lng": 108})
    assert (
        client.post("/admin/restaurants", headers=headers, json=restaurant_payload).status_code
        == 400
    )


def test_all_protected_routes_reject_missing_auth(client):
    protected = [
        ("GET", "/auth/me", None),
        ("GET", "/search/history", None),
        ("DELETE", "/search/history", None),
        ("POST", f"/restaurants/{client.restaurant_id}/reviews", {"rating": 4, "comment": "Tốt"}),
        ("GET", "/favorites", None),
        ("POST", "/favorites", {"targetType": "FOOD", "targetId": client.food_id}),
        ("DELETE", f"/favorites/FOOD/{client.food_id}", None),
        ("POST", "/itinerary/generate", {}),
        ("GET", "/itinerary", None),
        ("GET", "/itinerary/1", None),
        ("GET", "/admin/stats", None),
        ("GET", "/admin/users", None),
        ("PATCH", f"/admin/users/{client.user_id}/ban", {"banned": True}),
        (
            "POST",
            "/admin/restaurants",
            {"slug": "x", "name": "x", "address": "x", "district": "x", "lat": 16, "lng": 108},
        ),
        (
            "PUT",
            "/admin/restaurants/1",
            {"slug": "x", "name": "x", "address": "x", "district": "x", "lat": 16, "lng": 108},
        ),
        ("DELETE", "/admin/restaurants/1", None),
        ("POST", "/admin/foods", {"slug": "x", "name": "x", "aiLabel": "x"}),
        ("PUT", "/admin/foods/1", {"slug": "x", "name": "x", "aiLabel": "x"}),
        ("DELETE", "/admin/foods/1", None),
        ("POST", "/admin/articles", {"slug": "x", "title": "x"}),
        ("PUT", "/admin/articles/1", {"slug": "x", "title": "x"}),
        ("DELETE", "/admin/articles/1", None),
    ]
    for method, path, body in protected:
        response = client.request(method, path, json=body)
        assert response.status_code == 401, (method, path, response.text)
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
