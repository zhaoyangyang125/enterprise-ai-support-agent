from typing import Annotated

from fastapi import Header
from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """表示通过认证得到的当前用户。 / Represents the authenticated current user."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    department_id: str | None = None
    role_ids: frozenset[str] = frozenset()


def get_current_user(
    x_user_id: Annotated[str, Header(alias="X-User-Id", min_length=1)],
    x_department_id: Annotated[
        str | None,
        Header(alias="X-Department-Id"),
    ] = None,
    x_role_ids: Annotated[str | None, Header(alias="X-Role-Ids")] = None,
) -> CurrentUser:
    """将开发用请求头转换为当前用户上下文。 / Converts the development header into the current-user context."""

    role_ids = frozenset(
        role_id.strip()
        for role_id in (x_role_ids or "").split(",")
        if role_id.strip()
    )
    return CurrentUser(
        user_id=x_user_id,
        department_id=x_department_id,
        role_ids=role_ids,
    )
