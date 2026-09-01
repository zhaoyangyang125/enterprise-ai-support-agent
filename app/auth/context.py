from typing import Annotated

from fastapi import Header
from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """表示通过认证得到的当前用户。 / Represents the authenticated current user."""

    model_config = ConfigDict(frozen=True)

    user_id: str


def get_current_user(
    x_user_id: Annotated[str, Header(alias="X-User-Id", min_length=1)],
) -> CurrentUser:
    """将开发用请求头转换为当前用户上下文。 / Converts the development header into the current-user context."""

    return CurrentUser(user_id=x_user_id)
