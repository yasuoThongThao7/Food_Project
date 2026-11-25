import hashlib
import json
import threading
import time
from datetime import date as date_type
from datetime import timedelta
from typing import Any
import logging
import httpx
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import io
import uuid
from pathlib import Path
from PIL import Image, ImageOps
from app.adapters import ai_itinerary, ai_search
from app.core.deps import admin_user, current_user, optional_user
from app.core.envelope import Envelope
from app.core.errors import ApiError
from app.core.security import create_token, hash_password, verify_password
from app.db import get_db
from app.models import (
    Article,
    Favorite,
    Food,
    Itinerary,
    Restaurant,
    RestaurantFood,
    Review,
    SearchHistory,
    User,
    utcnow,
)
from app.schemas import (
    ArticleInput,
    BanInput,
    FavoriteInput,
    FoodInput,
    ItineraryInput,
    LoginInput,
    RegisterInput,
    RestaurantInput,
    ReviewInput,
)
from app.services.itinerary_fallback import SLOTS
# Import hàm xử lý AI đã được tách ra
from app.services.ai_service import process_image_and_predict

router = APIRouter()
auth_attempts: dict[str, list[float]] = {}
_geocode_lock = threading.Lock()
_last_geocode = 0.0
_BBOX = (15.9, 16.2, 107.9, 108.35)
logger = logging.getLogger(__name__)


def success(data: Any, meta: dict[str, int] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "data": data}
    if meta is not None:
        result["meta"] = meta
    return result


def user_json(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "isBanned": user.is_banned,
        "banReason": user.ban_reason,
        "createdAt": user.created_at.isoformat(),
    }


def food_json(food: Food) -> dict[str, Any]:
    return {
        "id": food.id,
        "slug": food.slug,
        "name": food.name,
        "aiLabel": food.ai_label,
        "description": food.description,
        "category": food.category,
        "imageUrl": food.image_url,
        "priceMin": food.price_min,
        "priceMax": food.price_max,
        "isActive": food.is_active,
    }


def restaurant_json(restaurant: Restaurant) -> dict[str, Any]:
    return {
        "id": restaurant.id,
        "slug": restaurant.slug,
        "name": restaurant.name,
        "address": restaurant.address,
        "district": restaurant.district,
        "lat": restaurant.lat,
        "lng": restaurant.lng,
        "phone": restaurant.phone,
        "openTime": restaurant.open_time,
        "closeTime": restaurant.close_time,
        "priceLevel": restaurant.price_level,
        "imageUrl": restaurant.image_url,
        "description": restaurant.description,
        "mealSlots": restaurant.meal_slots.split(","),
        "ratingAvg": restaurant.rating_avg,
        "ratingCount": restaurant.rating_count,
        "isActive": restaurant.is_active,
    }


def article_json(article: Article) -> dict[str, Any]:
    return {
        "id": article.id,
        "slug": article.slug,
        "title": article.title,
        "summary": article.summary,
        "content": article.content,
        "coverUrl": article.cover_url,
        "authorId": article.author_id,
        "isPublished": article.is_published,
        "publishedAt": article.published_at.isoformat() if article.published_at else None,
    }


def get_or_404(
    db: Session, model: Any, item_id: int, message: str = "Không tìm thấy dữ liệu"
) -> Any:
    value = db.get(model, item_id)
    if value is None:
        raise ApiError(404, "NOT_FOUND", message)
    return value


def _auth_rate_limit(request: Request) -> None:
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    recent = [item for item in auth_attempts.get(ip, []) if now - item < 60]
    if len(recent) >= 20:
        raise ApiError(429, "RATE_LIMIT", "Quá nhiều yêu cầu, vui lòng thử lại sau")
    recent.append(now)
    auth_attempts[ip] = recent


def _page(query: Any, page: int, limit: int) -> tuple[list[Any], dict[str, int]]:
    all_items = query.all()
    total = len(all_items)
    items = all_items[(page - 1) * limit : page * limit]
    return items, {"page": page, "limit": limit, "total": total}


def _geocode(address: str) -> tuple[float, float]:
    global _last_geocode
    if not _geocode_lock.acquire(timeout=20):
        raise ApiError(503, "AI_UNAVAILABLE", "Dịch vụ định vị tạm thời không khả dụng")
    try:
        wait = 1.0 - (time.monotonic() - _last_geocode)
        if wait > 0:
            time.sleep(wait)
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{address}, Da Nang, Vietnam", "format": "json", "limit": 1},
            headers={"User-Agent": "DaNangFoodGuide/1.0 (admin geocoding)"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            raise ApiError(400, "VALIDATION", "Không tìm thấy địa chỉ tại Đà Nẵng")
        return float(results[0]["lat"]), float(results[0]["lon"])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise ApiError(400, "VALIDATION", "Không thể xác định tọa độ địa chỉ") from exc
    finally:
        _last_geocode = time.monotonic()
        _geocode_lock.release()


def _validate_coordinates(lat: float, lng: float) -> None:
    if not (_BBOX[0] <= lat <= _BBOX[1] and _BBOX[2] <= lng <= _BBOX[3]):
        raise ApiError(400, "VALIDATION", "Tọa độ phải nằm trong phạm vi thành phố Đà Nẵng")


@router.post("/auth/register", tags=["auth"], response_model=Envelope[dict[str, Any]])
def register(
    payload: RegisterInput, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _auth_rate_limit(request)
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise ApiError(409, "CONFLICT", "Email đã được sử dụng")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Email đã được sử dụng") from exc
    return success({"token": create_token(user.id), "user": user_json(user)})


@router.post("/auth/login", tags=["auth"], response_model=Envelope[dict[str, Any]])
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _auth_rate_limit(request)
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise ApiError(401, "UNAUTHORIZED", "Email hoặc mật khẩu không chính xác")
    if user.is_banned:
        raise ApiError(
            403, "BANNED", f"Tài khoản đã bị khóa: {user.ban_reason or 'Không có lý do'}"
        )
    return success({"token": create_token(user.id), "user": user_json(user)})


@router.get("/auth/me", tags=["auth"], response_model=Envelope[dict[str, Any]])
def me(user: User = Depends(current_user)) -> dict[str, Any]:
    return success(user_json(user))


@router.post("/search/image", tags=["search"], response_model=Envelope[dict[str, Any]])
def search_image(
    image: UploadFile = File(...),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    allowed = {
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/webp": (b"RIFF",),
    }
    if image.content_type not in allowed:
        raise ApiError(400, "VALIDATION", "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP")
    data = image.file.read(5 * 1024 * 1024 + 1)
    if not data or len(data) > 5 * 1024 * 1024:
        raise ApiError(400, "VALIDATION", "Ảnh phải có dung lượng tối đa 5MB")
    valid_magic = data.startswith(allowed[image.content_type][0])
    if image.content_type == "image/webp":
        valid_magic = len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if not valid_magic:
        raise ApiError(400, "VALIDATION", "Định dạng nội dung ảnh không hợp lệ")
    predictions = ai_search.detect_foods(data, image.content_type)
    mapped: list[dict[str, Any]] = []
    unmatched: list[str] = []
    saved_ids: list[int] = []
    for prediction in predictions:
        label = str(prediction["label"])
        food = db.scalar(select(Food).where(Food.ai_label == label, Food.is_active.is_(True)))
        if food is None:
            unmatched.append(label)
            continue
        saved_ids.append(food.id)
        links = db.execute(
            select(RestaurantFood, Restaurant)
            .join(Restaurant, Restaurant.id == RestaurantFood.restaurant_id)
            .where(RestaurantFood.food_id == food.id, Restaurant.is_active.is_(True))
            .order_by(Restaurant.rating_avg.desc())
            .limit(10)
        ).all()
        mapped.append(
            {
                "food": food_json(food),
                "confidence": float(prediction["confidence"]),
                "restaurants": [
                    {
                        **restaurant_json(restaurant),
                        "price": link.price,
                        "isSignature": link.is_signature,
                    }
                    for link, restaurant in links
                ],
            }
        )
    if user:
        db.add(SearchHistory(user_id=user.id, detected_food_ids=saved_ids))
        db.commit()
    return success({"foods": mapped, "unmatched": unmatched})


@router.get("/search/history", tags=["search"], response_model=Envelope[list[dict[str, Any]]])
def search_history(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    rows = db.scalars(
        select(SearchHistory)
        .where(SearchHistory.user_id == user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(20)
    ).all()
    return success(
        [
            {
                "id": row.id,
                "createdAt": row.created_at.isoformat(),
                "foods": [
                    food_json(food)
                    for food_id in row.detected_food_ids
                    if (food := db.get(Food, food_id)) is not None
                ],
                "imageUrl": f"/uploads/{row.image_path}" if row.image_path else None,
                "result": row.result_json,
            }
            for row in rows
        ]
    )


@router.delete("/search/history", tags=["search"], response_model=Envelope[dict[str, int]])
def clear_search_history(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    rows = db.scalars(select(SearchHistory).where(SearchHistory.user_id == user.id)).all()
    image_paths = [row.image_path for row in rows if row.image_path]
    for row in rows:
        db.delete(row)
    db.commit()
    for path in image_paths:
        (UPLOAD_ROOT / path).unlink(missing_ok=True)
    return success({"deleted": len(rows)})


@router.get("/foods", tags=["foods"], response_model=Envelope[list[dict[str, Any]]])
def list_foods(
    q: str | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(Food).where(Food.is_active.is_(True))
    if category and category not in {"noodle", "seafood", "snack", "dessert", "drink", "other"}:
        raise ApiError(400, "VALIDATION", "Danh mục món ăn không hợp lệ")
    if q:
        query = query.where(or_(Food.name.ilike(f"%{q}%"), Food.description.ilike(f"%{q}%")))
    if category:
        query = query.where(Food.category == category)
    stmt = db.scalars(query.order_by(Food.name))
    items, meta = _page(stmt, page, limit)
    return success([food_json(food) for food in items], meta)


@router.get("/foods/{id}", tags=["foods"], response_model=Envelope[dict[str, Any]])
def get_food(id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    food = get_or_404(db, Food, id)
    if not food.is_active:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy món ăn")
    links = db.execute(
        select(RestaurantFood, Restaurant)
        .join(Restaurant, Restaurant.id == RestaurantFood.restaurant_id)
        .where(RestaurantFood.food_id == id, Restaurant.is_active.is_(True))
    ).all()
    return success(
        {
            **food_json(food),
            "restaurants": [
                {
                    **restaurant_json(restaurant),
                    "price": link.price,
                    "isSignature": link.is_signature,
                }
                for link, restaurant in links
            ],
        }
    )


@router.get("/restaurants", tags=["restaurants"], response_model=Envelope[list[dict[str, Any]]])
def list_restaurants(
    q: str | None = None,
    district: str | None = None,
    food_id: int | None = Query(None, alias="foodId"),
    price_level: int | None = Query(None, ge=1, le=3),
    sort: str = "rating",
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(Restaurant).where(Restaurant.is_active.is_(True))
    if q:
        query = query.where(
            or_(Restaurant.name.ilike(f"%{q}%"), Restaurant.address.ilike(f"%{q}%"))
        )
    if district:
        query = query.where(Restaurant.district.ilike(f"%{district}%"))
    if price_level:
        query = query.where(Restaurant.price_level == price_level)
    if food_id:
        query = query.join(RestaurantFood, RestaurantFood.restaurant_id == Restaurant.id).where(
            RestaurantFood.food_id == food_id
        )
    if sort not in {"rating", "new"}:
        raise ApiError(400, "VALIDATION", "Giá trị sort không hợp lệ")
    ordering = Restaurant.rating_avg.desc() if sort == "rating" else Restaurant.id.desc()
    result = db.scalars(query.order_by(ordering).distinct())
    items, meta = _page(result, page, limit)
    return success([restaurant_json(item) for item in items], meta)


@router.get("/restaurants/{id}", tags=["restaurants"], response_model=Envelope[dict[str, Any]])
def get_restaurant(
    id: int, db: Session = Depends(get_db), user: User | None = Depends(optional_user)
) -> dict[str, Any]:
    restaurant = get_or_404(db, Restaurant, id)
    if not restaurant.is_active:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy nhà hàng")
    links = db.execute(
        select(RestaurantFood, Food)
        .join(Food, Food.id == RestaurantFood.food_id)
        .where(RestaurantFood.restaurant_id == id, Food.is_active.is_(True))
    ).all()
    favorite = bool(
        user
        and db.scalar(
            select(Favorite.id).where(
                Favorite.user_id == user.id,
                Favorite.target_type == "RESTAURANT",
                Favorite.target_id == id,
            )
        )
    )
    return success(
        {
            **restaurant_json(restaurant),
            "foods": [
                {**food_json(food), "price": link.price, "isSignature": link.is_signature}
                for link, food in links
            ],
            "isFavorite": favorite,
        }
    )


@router.get(
    "/restaurants/{id}/reviews", tags=["reviews"], response_model=Envelope[list[dict[str, Any]]]
)
def list_reviews(
    id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    restaurant = get_or_404(db, Restaurant, id)
    if not restaurant.is_active:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy nhà hàng")
    query = select(Review).where(Review.restaurant_id == id).order_by(Review.created_at.desc())
    items, meta = _page(db.scalars(query), page, limit)
    return success(
        [
            {
                "id": review.id,
                "rating": review.rating,
                "comment": review.comment,
                "createdAt": review.created_at.isoformat(),
                "user": (lambda person: {"id": person.id, "name": person.name})(
                    get_or_404(db, User, review.user_id)
                ),
            }
            for review in items
        ],
        meta,
    )


@router.post("/restaurants/{id}/reviews", tags=["reviews"], response_model=Envelope[dict[str, Any]])
def upsert_review(
    id: int, payload: ReviewInput, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    restaurant = get_or_404(db, Restaurant, id)
    if not restaurant.is_active:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy nhà hàng")
    review = db.scalar(select(Review).where(Review.user_id == user.id, Review.restaurant_id == id))
    if review:
        review.rating, review.comment, review.created_at = payload.rating, payload.comment, utcnow()
    else:
        review = Review(
            user_id=user.id, restaurant_id=id, rating=payload.rating, comment=payload.comment
        )
        db.add(review)
    db.flush()
    aggregate = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.restaurant_id == id)
    ).one()
    restaurant.rating_avg, restaurant.rating_count = float(aggregate[0] or 0), int(aggregate[1])
    db.commit()
    db.refresh(review)
    return success(
        {
            "id": review.id,
            "rating": review.rating,
            "comment": review.comment,
            "createdAt": review.created_at.isoformat(),
        }
    )


@router.get("/favorites", tags=["favorites"], response_model=Envelope[dict[str, Any]])
def list_favorites(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    rows = db.scalars(select(Favorite).where(Favorite.user_id == user.id)).all()
    foods = [
        food_json(food)
        for row in rows
        if row.target_type == "FOOD"
        and (food := db.get(Food, row.target_id)) is not None
        and food.is_active
    ]
    restaurants = [
        restaurant_json(item)
        for row in rows
        if row.target_type == "RESTAURANT"
        and (item := db.get(Restaurant, row.target_id)) is not None
        and item.is_active
    ]
    return success({"foods": foods, "restaurants": restaurants})


@router.post("/favorites", tags=["favorites"], response_model=Envelope[dict[str, Any]])
def add_favorite(
    payload: FavoriteInput, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    model = Food if payload.target_type == "FOOD" else Restaurant
    target = get_or_404(db, model, payload.target_id)
    if not target.is_active:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy dữ liệu")
    favorite = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.target_type == payload.target_type,
            Favorite.target_id == payload.target_id,
        )
    )
    if favorite is None:
        favorite = Favorite(
            user_id=user.id, target_type=payload.target_type, target_id=payload.target_id
        )
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
    return success(
        {"id": favorite.id, "targetType": favorite.target_type, "targetId": favorite.target_id}
    )


@router.delete(
    "/favorites/{targetType}/{targetId}",
    tags=["favorites"],
    response_model=Envelope[dict[str, bool]],
)
def remove_favorite(
    targetType: str,
    targetId: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    if targetType not in {"FOOD", "RESTAURANT"}:
        raise ApiError(400, "VALIDATION", "targetType phải là FOOD hoặc RESTAURANT")
    favorite = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.target_type == targetType,
            Favorite.target_id == targetId,
        )
    )
    if favorite is None:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy mục yêu thích")
    db.delete(favorite)
    db.commit()
    return success({"deleted": True})


def _candidate_payload(db: Session, user: User) -> dict[str, Any]:
    favorites = db.scalars(select(Favorite).where(Favorite.user_id == user.id)).all()
    favorite_restaurants = {row.target_id for row in favorites if row.target_type == "RESTAURANT"}
    favorite_food_ids = {row.target_id for row in favorites if row.target_type == "FOOD"}
    favorite_foods = [
        food_json(food)
        for food_id in favorite_food_ids
        if (food := db.get(Food, food_id)) is not None
    ]
    ratings = db.execute(
        select(Review.restaurant_id).where(Review.user_id == user.id, Review.rating >= 4)
    ).all()
    rated = {int(row[0]) for row in ratings}
    histories = db.scalars(
        select(SearchHistory)
        .where(SearchHistory.user_id == user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(20)
    ).all()
    searched = list(
        dict.fromkeys(food_id for row in histories for food_id in row.detected_food_ids)
    )
    avg_price = db.scalar(
        select(func.avg(Restaurant.price_level))
        .join(Favorite, Favorite.target_id == Restaurant.id)
        .where(Favorite.user_id == user.id, Favorite.target_type == "RESTAURANT")
    )
    restaurants = db.scalars(
        select(Restaurant)
        .where(Restaurant.is_active.is_(True))
        .order_by(Restaurant.rating_avg.desc())
    ).all()
    enriched: list[dict[str, Any]] = []
    search_match_ids: set[int] = set(searched)
    for restaurant in restaurants:
        links = db.execute(
            select(RestaurantFood.food_id, Food.name)
            .join(Food, Food.id == RestaurantFood.food_id)
            .where(RestaurantFood.restaurant_id == restaurant.id, Food.is_active.is_(True))
            .limit(3)
        ).all()
        enriched.append(
            {
                "id": restaurant.id,
                "name": restaurant.name,
                "district": restaurant.district,
                "priceLevel": restaurant.price_level,
                "open": restaurant.open_time,
                "close": restaurant.close_time,
                "mealSlots": restaurant.meal_slots.split(","),
                "foods": [row.name for row in links],
                "foodIds": [row.food_id for row in links],
                "rating": restaurant.rating_avg,
                "isFav": restaurant.id in favorite_restaurants,
                "rated": restaurant.id in rated,
                "matchesSearch": bool({row.food_id for row in links} & search_match_ids),
            }
        )
    enriched.sort(
        key=lambda row: (
            not row["isFav"],
            not row["rated"],
            not row["matchesSearch"],
            -row["rating"],
        )
    )
    candidates = enriched[:40]
    return {
        "profile": {
            "favFoods": [{"id": food["id"], "name": food["name"]} for food in favorite_foods],
            "favRestaurantIds": list(favorite_restaurants),
            "topRatedRestaurantIds": list(rated),
            "recentSearchFoodIds": searched,
            "avgPriceLevel": float(avg_price) if avg_price is not None else None,
        },
        "candidates": candidates,
    }


def _validate_ai_plan(plan: list[dict[str, object]], candidates: list[dict[str, Any]]) -> bool:
    candidate_map = {int(row["id"]): row for row in candidates}
    if len(plan) != len(SLOTS) or {row.get("slot") for row in plan} != set(SLOTS):
        return False
    restaurants: set[int] = set()
    for row in plan:
        try:
            rid = int(row["restaurantId"])
            slot = str(row["slot"])
            candidate = candidate_map[rid]
            reason = row["reason"]
            if (
                rid in restaurants
                or not isinstance(reason, str)
                or len(reason) > 120
                or slot not in candidate["mealSlots"]
            ):
                return False
            start, end, _ = SLOTS[slot]
            if candidate["open"] > start or candidate["close"] < end:
                return False
            food_id = row.get("foodId")
            if food_id is not None and int(food_id) not in candidate["foodIds"]:
                return False
            restaurants.add(rid)
        except (KeyError, TypeError, ValueError):
            return False
    return True


@router.post("/itinerary/generate", tags=["itinerary"], response_model=Envelope[dict[str, Any]])
def generate_itinerary(
    payload: ItineraryInput, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    try:
        chosen_date = date_type.fromisoformat(payload.date) if payload.date else date_type.today()
    except ValueError as exc:
        raise ApiError(400, "VALIDATION", "Ngày không hợp lệ") from exc
    if payload.date and chosen_date.isoformat() != payload.date:
        raise ApiError(400, "VALIDATION", "Ngày phải theo định dạng YYYY-MM-DD")
    context = _candidate_payload(db, user)
    ai_payload: dict[str, Any] = {"date": chosen_date.isoformat(), "slots": list(SLOTS), **context}
    encoded = json.dumps(ai_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    hash_input = f"{user.id}{chosen_date.isoformat()}{encoded}"
    if payload.force_new:
        hash_input += uuid.uuid4().hex
    input_hash = hashlib.sha1(hash_input.encode()).hexdigest()
    cached = db.scalar(
        select(Itinerary).where(
            Itinerary.user_id == user.id,
            Itinerary.date == chosen_date.isoformat(),
            Itinerary.input_hash == input_hash,
        )
    )
    if cached:
        logger.info("Returning cached %s itinerary id=%s", cached.source, cached.id)
        return success(_itinerary_json(db, cached))
    since = utcnow() - timedelta(hours=1)
    count = (
        db.scalar(
            select(func.count(Itinerary.id)).where(
                Itinerary.user_id == user.id, Itinerary.created_at >= since
            )
        )
        or 0
    )
    if count >= 5:
        raise ApiError(429, "RATE_LIMIT", "Bạn đã tạo tối đa 5 lịch trình trong một giờ")
    try:
        plan = ai_itinerary.generate_plan(ai_payload)
        if not _validate_ai_plan(plan, context["candidates"]):
            raise ValueError("Invalid AI plan")
        source = "AI"
    except (ApiError, ValueError, TypeError, KeyError) as exc:
        logger.warning(
            "Itinerary AI failed or returned an invalid plan (%s): %s; using FALLBACK",
            type(exc).__name__,
            getattr(exc, "message", str(exc)),
        )
        from app.services.itinerary_fallback import build_fallback

        plan = build_fallback(ai_payload)
        source = "FALLBACK"
    itinerary = Itinerary(
        user_id=user.id,
        date=chosen_date.isoformat(),
        plan_json=plan,
        source=source,
        input_hash=input_hash,
    )
    db.add(itinerary)
    db.commit()
    db.refresh(itinerary)
    return success(_itinerary_json(db, itinerary))


def _itinerary_json(db: Session, itinerary: Itinerary) -> dict[str, Any]:
    plan: list[dict[str, Any]] = []
    for row in itinerary.plan_json:
        restaurant = db.get(Restaurant, int(row["restaurantId"]))
        if restaurant is None:
            continue
        item: dict[str, Any] = {
            "slot": row["slot"],
            "restaurant": restaurant_json(restaurant),
            "reason": row["reason"],
        }
        if row.get("foodId") is not None and (food := db.get(Food, int(row["foodId"]))) is not None:
            item["food"] = food_json(food)
        plan.append(item)
    return {"id": itinerary.id, "date": itinerary.date, "source": itinerary.source, "plan": plan}


@router.get("/itinerary", tags=["itinerary"], response_model=Envelope[list[dict[str, Any]]])
def list_itineraries(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    rows = db.scalars(
        select(Itinerary)
        .where(Itinerary.user_id == user.id)
        .order_by(Itinerary.created_at.desc())
        .limit(10)
    ).all()
    return success([_itinerary_json(db, row) for row in rows])


@router.get("/itinerary/{id}", tags=["itinerary"], response_model=Envelope[dict[str, Any]])
def get_itinerary(
    id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    itinerary = get_or_404(db, Itinerary, id)
    if itinerary.user_id != user.id:
        raise ApiError(403, "FORBIDDEN", "Bạn không có quyền xem lịch trình này")
    return success(_itinerary_json(db, itinerary))


@router.get("/articles", tags=["articles"], response_model=Envelope[list[dict[str, Any]]])
def list_articles(
    page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=50), db: Session = Depends(get_db)
) -> dict[str, Any]:
    query = (
        select(Article).where(Article.is_published.is_(True)).order_by(Article.published_at.desc())
    )
    items, meta = _page(db.scalars(query), page, limit)
    return success([article_json(item) for item in items], meta)


@router.get("/articles/{slug}", tags=["articles"], response_model=Envelope[dict[str, Any]])
def get_article(slug: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.scalar(select(Article).where(Article.slug == slug, Article.is_published.is_(True)))
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy bài viết")
    return success(article_json(item))


@router.get("/admin/stats", tags=["admin"], response_model=Envelope[dict[str, int]])
def admin_stats(db: Session = Depends(get_db), user: User = Depends(admin_user)) -> dict[str, Any]:
    since = utcnow() - timedelta(days=7)
    return success(
        {
            "users": int(db.scalar(select(func.count(User.id))) or 0),
            "restaurants": int(
                db.scalar(select(func.count(Restaurant.id)).where(Restaurant.is_active.is_(True)))
                or 0
            ),
            "foods": int(
                db.scalar(select(func.count(Food.id)).where(Food.is_active.is_(True))) or 0
            ),
            "reviews": int(db.scalar(select(func.count(Review.id))) or 0),
            "searches7d": int(
                db.scalar(
                    select(func.count(SearchHistory.id)).where(SearchHistory.created_at >= since)
                )
                or 0
            ),
        }
    )


@router.get("/admin/users", tags=["admin"], response_model=Envelope[list[dict[str, Any]]])
def admin_users(
    q: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
) -> dict[str, Any]:
    query = select(User)
    if q:
        query = query.where(or_(User.email.ilike(f"%{q}%"), User.name.ilike(f"%{q}%")))
    items, meta = _page(db.scalars(query.order_by(User.id)), page, 12)
    return success([user_json(item) for item in items], meta)


@router.patch("/admin/users/{id}/ban", tags=["admin"], response_model=Envelope[dict[str, Any]])
def ban_user(
    id: int, payload: BanInput, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    target = get_or_404(db, User, id)
    if target.id == user.id or target.role == "ADMIN":
        raise ApiError(403, "FORBIDDEN", "Không thể khóa tài khoản quản trị viên")
    target.is_banned = payload.banned
    target.ban_reason = payload.reason if payload.banned else None
    db.commit()
    return success(user_json(target))


def _restaurant_values(payload: RestaurantInput) -> dict[str, Any]:
    values = payload.model_dump()
    lat, lng = values.get("lat"), values.get("lng")
    if lat is None or lng is None:
        lat, lng = _geocode(payload.address)
    _validate_coordinates(float(lat), float(lng))
    values["lat"], values["lng"] = float(lat), float(lng)
    values["meal_slots"] = ",".join(payload.meal_slots)
    return values


@router.post("/admin/restaurants", tags=["admin"], response_model=Envelope[dict[str, Any]])
def create_restaurant(
    payload: RestaurantInput, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    restaurant = Restaurant(**_restaurant_values(payload))
    db.add(restaurant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Slug nhà hàng đã tồn tại") from exc
    db.refresh(restaurant)
    return success(restaurant_json(restaurant))


@router.put("/admin/restaurants/{id}", tags=["admin"], response_model=Envelope[dict[str, Any]])
def update_restaurant(
    id: int,
    payload: RestaurantInput,
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
) -> dict[str, Any]:
    restaurant = get_or_404(db, Restaurant, id)
    for key, value in _restaurant_values(payload).items():
        setattr(restaurant, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Slug nhà hàng đã tồn tại") from exc
    return success(restaurant_json(restaurant))


@router.delete("/admin/restaurants/{id}", tags=["admin"], response_model=Envelope[dict[str, bool]])
def delete_restaurant(
    id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    restaurant = get_or_404(db, Restaurant, id)
    restaurant.is_active = False
    db.commit()
    return success({"deleted": True})


@router.post("/admin/foods", tags=["admin"], response_model=Envelope[dict[str, Any]])
def create_food(
    payload: FoodInput, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    if (
        payload.category not in {"noodle", "seafood", "snack", "dessert", "drink", "other"}
        or payload.price_max < payload.price_min
    ):
        raise ApiError(400, "VALIDATION", "Thông tin món ăn không hợp lệ")
    food = Food(**payload.model_dump())
    db.add(food)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Slug hoặc nhãn AI đã tồn tại") from exc
    db.refresh(food)
    return success(food_json(food))


@router.put("/admin/foods/{id}", tags=["admin"], response_model=Envelope[dict[str, Any]])
def update_food(
    id: int, payload: FoodInput, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    food = get_or_404(db, Food, id)
    if (
        payload.category not in {"noodle", "seafood", "snack", "dessert", "drink", "other"}
        or payload.price_max < payload.price_min
    ):
        raise ApiError(400, "VALIDATION", "Thông tin món ăn không hợp lệ")
    for key, value in payload.model_dump().items():
        setattr(food, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Slug hoặc nhãn AI đã tồn tại") from exc
    return success(food_json(food))


@router.delete("/admin/foods/{id}", tags=["admin"], response_model=Envelope[dict[str, bool]])
def delete_food(
    id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    food = get_or_404(db, Food, id)
    food.is_active = False
    db.commit()
    return success({"deleted": True})


def _save_article(
    payload: ArticleInput, author_id: int, existing: Article | None = None
) -> Article:
    values = payload.model_dump()
    if existing is None:
        existing = Article(
            **values, author_id=author_id, published_at=utcnow() if payload.is_published else None
        )
    else:
        for key, value in values.items():
            setattr(existing, key, value)
        existing.published_at = (
            utcnow()
            if payload.is_published and existing.published_at is None
            else existing.published_at
        )
    return existing


@router.post("/admin/articles", tags=["admin"], response_model=Envelope[dict[str, Any]])
def create_article(
    payload: ArticleInput, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    article = _save_article(payload, user.id)
    db.add(article)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Slug bài viết đã tồn tại") from exc
    db.refresh(article)
    return success(article_json(article))


@router.put("/admin/articles/{id}", tags=["admin"], response_model=Envelope[dict[str, Any]])
def update_article(
    id: int, payload: ArticleInput, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    article = get_or_404(db, Article, id)
    _save_article(payload, user.id, article)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Slug bài viết đã tồn tại") from exc
    return success(article_json(article))


@router.delete("/admin/articles/{id}", tags=["admin"], response_model=Envelope[dict[str, bool]])
def delete_article(
    id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)
) -> dict[str, Any]:
    article = get_or_404(db, Article, id)
    db.delete(article)
    db.commit()
    return success({"deleted": True})


@router.get("/health", tags=["health"], response_model=Envelope[dict[str, str]])
def health() -> dict[str, Any]:
    return success({"status": "ok"})


UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"   # server/uploads
PREDICTION_DIR = UPLOAD_ROOT / "predictions"
MAX_PREDICT_IMAGE_BYTES = 10 * 1024 * 1024
_ai_lock = threading.Lock()


def _run_prediction(image_bytes: bytes) -> dict[str, Any]:
    # Nạp lười: thiếu file model thì chỉ endpoint này lỗi 503, app vẫn khởi động bình thường
    try:
        from app.services.ai_service import process_image_and_predict
    except (FileNotFoundError, ImportError) as exc:
        logger.error("AI service unavailable: %s", exc)
        raise ApiError(503, "AI_UNAVAILABLE", "Dịch vụ nhận diện tạm thời không khả dụng") from exc
    with _ai_lock:  # tránh nhiều luồng cùng chạy YOLO/CNN một lúc
        return process_image_and_predict(image_bytes)


def _save_prediction_image(image_bytes: bytes) -> str:
    PREDICTION_DIR.mkdir(parents=True, exist_ok=True)
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    name = f"{uuid.uuid4().hex}.jpg"
    image.save(PREDICTION_DIR / name, "JPEG", quality=90, optimize=True)
    return f"predictions/{name}"


@router.post("/predict", tags=["search"], response_model=Envelope[dict[str, Any]])
def predict_food(
    file: UploadFile = File(...),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # 1. Kiểm tra định dạng file
    if not file.content_type or not file.content_type.startswith("image/"):
        raise ApiError(400, "VALIDATION", "Vui lòng tải lên file hình ảnh hợp lệ.")

    # 2. Đọc file dưới dạng bytes (giới hạn 10MB)
    image_bytes = file.file.read(MAX_PREDICT_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_PREDICT_IMAGE_BYTES:
        raise ApiError(400, "VALIDATION", "Ảnh phải có dung lượng tối đa 10MB")

    # 3. Gọi hàm xử lý AI từ service
    try:
        result = _run_prediction(image_bytes)
    except ValueError as exc:  # lỗi đọc ảnh từ ai_service
        raise ApiError(400, "VALIDATION", str(exc)) from exc
    except ApiError:
        raise
    except Exception as exc:
        logger.exception("Prediction error")
        raise ApiError(500, "INTERNAL", "Đã có lỗi xảy ra trong quá trình nhận diện.") from exc

    # 4. Đã đăng nhập và nhận diện được món -> lưu lịch sử (lỗi lưu không làm hỏng kết quả)
    if user and result.get("success"):
        image_path: str | None = None
        try:
            names = [dish["class_name"] for dish in result["dishes"]]
            food_ids = {
                food.ai_label: food.id
                for food in db.scalars(
                    select(Food).where(Food.ai_label.in_(names), Food.is_active.is_(True))
                )
            }
            image_path = _save_prediction_image(image_bytes)
            history = SearchHistory(
                user_id=user.id,
                detected_food_ids=[food_ids[name] for name in names if name in food_ids],
                image_path=image_path,
                result_json=result,
            )
            db.add(history)
            db.commit()
            db.refresh(history)
            result = {**result, "history_id": history.id, "image_url": f"/uploads/{image_path}"}
        except Exception:
            db.rollback()
            if image_path:
                (UPLOAD_ROOT / image_path).unlink(missing_ok=True)
            logger.exception("Could not save prediction history")

    return success(result)