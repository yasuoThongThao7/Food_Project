from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_serializer

T = TypeVar("T")


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class Envelope(BaseModel, Generic[T]):
    ok: bool = True
    data: T
    meta: dict[str, int] | None = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @model_serializer(mode="wrap")
    def serialize(self, handler: Any) -> Any:
        result = handler(self)
        if self.meta is None:
            result.pop("meta", None)
        return result


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    ok: bool = False
    error: ErrorDetail
