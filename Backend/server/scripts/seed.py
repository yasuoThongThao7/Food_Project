import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Article, Food, Restaurant, RestaurantFood, Review, User, utcnow

FOOD_DATA = [
    ("mi-quang", "Mì Quảng", "noodle"),
    ("banh-trang-cuon-thit-heo", "Bánh tráng cuốn thịt heo", "snack"),
    ("bun-cha-ca", "Bún chả cá", "noodle"),
    ("banh-xeo", "Bánh xèo", "snack"),
    ("bun-mam-nem", "Bún mắm nêm", "noodle"),
    ("banh-beo", "Bánh bèo", "snack"),
    ("nem-lui", "Nem lụi", "snack"),
    ("hai-san", "Hải sản", "seafood"),
    ("che", "Chè", "dessert"),
    ("ca-phe-muoi", "Cà phê muối", "drink"),
    ("cao-lau", "Cao lầu", "noodle"),
    ("banh-nam", "Bánh nậm", "snack"),
    ("goi-ca-nam-o", "Gỏi cá Nam Ô", "seafood"),
    ("oc-hut", "Ốc hút", "seafood"),
    ("my-quang-ech", "Mì Quảng ếch", "noodle"),
    ("banh-canh", "Bánh canh", "noodle"),
    ("kem-bo", "Kem bơ", "dessert"),
    ("sua-chua-muon", "Sữa chua muối", "dessert"),
    ("nuoc-mia", "Nước mía", "drink"),
    ("banh-mi", "Bánh mì", "snack"),
]
RESTAURANT_NAMES = [
    "Quán Bà Mua",
    "Mì Quảng 1A",
    "Bếp Trần",
    "Bún Chả Cá Bà Lữ",
    "Bánh Xèo Bà Dưỡng",
    "Mì Quảng Ếch Bếp Trang",
    "Hải Sản Bé Mặn",
    "Chè Liên",
    "Bánh Bèo Bà Tiên",
    "Nem Lụi Bà Hạnh",
    "Bún Mắm Vân",
    "Cao Lầu Phố Hội",
    "Ốc Hút Cô Ta",
    "Gỏi Cá Nam Ô",
    "Bánh Canh Ruộng",
    "Kem Bơ Cô Vân",
    "Bánh Mì Đồng Tiến",
    "Cà Phê Muối Nhà",
    "Hải Sản Năm Đảnh",
    "Quán Ăn Nhà",
    "Mì Quảng Cô Sáu",
    "Bún Chả Cá Ông Tạ",
    "Bếp Miền Trung",
    "Quán Đặc Sản Đà Thành",
    "Bánh Xèo Miền Trung",
    "Ăn Vặt Sơn Trà",
    "Hải Sản Thanh Hiền",
    "Chè Xoa Xoa",
    "Bánh Tráng Cuốn Đại Lộc",
    "Quán Ngon Hải Châu",
]
SLOTS = ["breakfast", "lunch", "snack", "dinner"]


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
        if admin is None:
            admin = User(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
                name="Quản trị viên",
                role="ADMIN",
            )
            db.add(admin)
        else:
            admin.role = "ADMIN"
        demo_users = []
        for email, name in [("demo1@example.com", "Minh Anh"), ("demo2@example.com", "Hoàng Nam")]:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email, password_hash=hash_password("demo-password-123"), name=name
                )
                db.add(user)
            demo_users.append(user)
        db.flush()
        foods = []
        for slug, name, category in FOOD_DATA:
            food = db.scalar(select(Food).where(Food.slug == slug))
            if food is None:
                food = Food(
                    slug=slug,
                    ai_label=slug,
                    name=name,
                    category=category,
                    description=f"{name} đặc sản Đà Nẵng.",
                    image_url=f"https://example.com/foods/{slug}.jpg",
                    price_min=15000,
                    price_max=90000,
                )
                db.add(food)
            foods.append(food)
        db.flush()
        restaurants = []
        districts = ["Hải Châu", "Sơn Trà", "Thanh Khê", "Ngũ Hành Sơn", "Liên Chiểu", "Cẩm Lệ"]
        addresses = ["Trần Phú", "Hoàng Diệu", "Nguyễn Văn Linh", "Lê Duẩn", "Phan Châu Trinh"]
        for index, name in enumerate(RESTAURANT_NAMES):
            slug = f"da-nang-quan-{index + 1:02d}"
            restaurant = db.scalar(select(Restaurant).where(Restaurant.slug == slug))
            if restaurant is None:
                slot = SLOTS[index % len(SLOTS)]
                opening = {
                    "breakfast": ("06:00", "14:00"),
                    "lunch": ("10:00", "16:00"),
                    "snack": ("14:00", "22:00"),
                    "dinner": ("17:00", "23:00"),
                }[slot]
                restaurant = Restaurant(
                    slug=slug,
                    name=name,
                    address=f"{index + 10} {addresses[index % len(addresses)]}, Đà Nẵng",
                    district=districts[index % len(districts)],
                    lat=16.02 + (index % 10) * 0.008,
                    lng=108.20 + (index % 10) * 0.01,
                    phone=f"090500{index:04d}",
                    open_time=opening[0],
                    close_time=opening[1],
                    price_level=index % 3 + 1,
                    image_url=f"https://example.com/restaurants/{slug}.jpg",
                    description=f"Địa điểm ăn uống được yêu thích tại Đà Nẵng: {name}.",
                    meal_slots=",".join(SLOTS),
                    rating_avg=4.0 + (index % 10) / 10,
                    rating_count=0,
                )
                db.add(restaurant)
            restaurants.append(restaurant)
        db.flush()
        for index, restaurant in enumerate(restaurants):
            for food in foods[index % len(foods) : (index % len(foods)) + 3]:
                link = db.get(RestaurantFood, (restaurant.id, food.id))
                if link is None:
                    db.add(
                        RestaurantFood(
                            restaurant_id=restaurant.id,
                            food_id=food.id,
                            price=25000 + index * 1000,
                            is_signature=(food.id % 3 == 0),
                        )
                    )
        db.flush()
        for index in range(40):
            reviewer = demo_users[index // len(restaurants)]
            restaurant = restaurants[index % len(restaurants)]
            review = db.scalar(
                select(Review).where(
                    Review.user_id == reviewer.id, Review.restaurant_id == restaurant.id
                )
            )
            if review is None:
                db.add(
                    Review(
                        user_id=reviewer.id,
                        restaurant_id=restaurant.id,
                        rating=4 + index % 2,
                        comment="Món ăn ngon, sẽ quay lại.",
                    )
                )
        db.flush()
        for restaurant in restaurants:
            rows = db.execute(
                select(Review.rating).where(Review.restaurant_id == restaurant.id)
            ).all()
            if rows:
                restaurant.rating_avg = sum(row[0] for row in rows) / len(rows)
                restaurant.rating_count = len(rows)
        for index in range(5):
            slug = f"cam-nang-am-thuc-da-nang-{index + 1}"
            if db.scalar(select(Article.id).where(Article.slug == slug)) is None:
                db.add(
                    Article(
                        slug=slug,
                        title=f"Cẩm nang ẩm thực Đà Nẵng {index + 1}",
                        summary="Khám phá món ngon và địa chỉ ẩm thực địa phương.",
                        content="## Hương vị Đà Nẵng\n\nThưởng thức những món ngon đặc sắc của thành phố.",
                        cover_url=f"https://example.com/articles/{slug}.jpg",
                        author_id=admin.id,
                        is_published=True,
                        published_at=utcnow(),
                    )
                )
        db.commit()


if __name__ == "__main__":
    run_seed()
