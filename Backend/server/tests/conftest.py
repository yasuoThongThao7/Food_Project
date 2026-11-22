import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db import Base, get_db
from app.main import app
from app.models import Food, Restaurant, RestaurantFood, User


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestingSession() as db:
        user = User(
            email="user@example.com", password_hash=hash_password("password-123"), name="Nguyen"
        )
        admin = User(
            email="admin@example.com",
            password_hash=hash_password("password-123"),
            name="Admin",
            role="ADMIN",
        )
        food = Food(
            slug="mi-quang",
            ai_label="mi-quang",
            name="Mì Quảng",
            category="noodle",
            price_min=20000,
            price_max=50000,
        )
        db.add_all([user, admin, food])
        db.flush()
        restaurant = Restaurant(
            slug="quan-ngon",
            name="Quán Ngon",
            address="1 Trần Phú",
            district="Hải Châu",
            lat=16.05,
            lng=108.22,
            open_time="05:00",
            close_time="23:00",
            meal_slots="breakfast,lunch,snack,dinner",
            rating_avg=4.5,
            rating_count=0,
        )
        db.add(restaurant)
        db.flush()
        db.add(
            RestaurantFood(
                restaurant_id=restaurant.id, food_id=food.id, price=35000, is_signature=True
            )
        )
        db.commit()
        user_id, admin_id, restaurant_id, food_id = user.id, admin.id, restaurant.id, food.id
    with TestClient(app) as test_client:
        test_client.user_id = user_id
        test_client.admin_id = admin_id
        test_client.restaurant_id = restaurant_id
        test_client.food_id = food_id
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def token(client, email="user@example.com"):
    response = client.post("/auth/login", json={"email": email, "password": "password-123"})
    assert response.status_code == 200
    return response.json()["data"]["token"]
