from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_access_token
from ..db.session import get_session
from ..repositories.user_repository import UserRepository
from ..schemas.user import UserInDB
from ..services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_user_from_token(
    token: str,
    session: AsyncSession,
) -> UserInDB:
    """从 token 解析用户信息（核心逻辑，供复用）。"""
    payload = decode_access_token(token)
    username = payload["sub"]
    repo = UserRepository(session)
    user = await repo.get_by_username(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")
    service = AuthService(session)
    schema = UserInDB.model_validate(user)
    schema.must_change_password = service.requires_password_reset(user)
    return schema


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> UserInDB:
    return await get_user_from_token(token, session)


async def get_current_user_ws(
    token: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> Optional[UserInDB]:
    """WebSocket 版本的用户认证（从 query 参数读取 token）。

    WebSocket 不支持 Authorization header，所以通过 ?token=xxx 传递。
    如果没有 token 或 token 无效，返回 None。
    """
    if not token:
        return None
    try:
        return await get_user_from_token(token, session)
    except HTTPException:
        return None


async def get_current_admin(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user
