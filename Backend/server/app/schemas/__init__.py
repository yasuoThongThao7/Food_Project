import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class InputModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class RegisterInput(InputModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class LoginInput(InputModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str


class ReviewInput(InputModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(max_length=500)


class FavoriteInput(InputModel):
    target_type: str
    target_id: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_target(self) -> "FavoriteInput":
        if self.target_type not in {"FOOD", "RESTAURANT"}:
            raise ValueError("targetType must be FOOD or RESTAURANT")
        return self


class BanInput(InputModel):
    banned: bool
    reason: str | None = Field(default=None, max_length=500)


class ItineraryInput(InputModel):
    date: str | None = None
    force_new: bool = False


class FoodInput(InputModel):
    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    ai_label: str
    description: str = ""
    category: str = "other"
    image_url: str = ""
    price_min: int = Field(default=0, ge=0)
    price_max: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str) -> str:
        if value not in {"noodle", "seafood", "snack", "dessert", "drink", "other"}:
            raise ValueError("Invalid food category")
        return value


class RestaurantInput(InputModel):
    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=180)
    address: str = Field(min_length=1, max_length=300)
    district: str = Field(min_length=1, max_length=100)
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    open_time: str = "06:00"
    close_time: str = "22:00"
    price_level: int = Field(default=1, ge=1, le=3)
    image_url: str = ""
    description: str = ""
    meal_slots: list[str] = Field(default_factory=lambda: ["breakfast", "lunch", "snack", "dinner"])
    is_active: bool = True

    @field_validator("open_time", "close_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Time must be HH:mm")
        return value

    @field_validator("meal_slots")
    @classmethod
    def valid_meal_slots(cls, value: list[str]) -> list[str]:
        if (
            not value
            or len(set(value)) != len(value)
            or any(slot not in {"breakfast", "lunch", "snack", "dinner"} for slot in value)
        ):
            raise ValueError("Invalid meal slots")
        return value


class ArticleInput(InputModel):
    slug: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    summary: str = ""
    content: str = ""
    cover_url: str = ""
    is_published: bool = False
