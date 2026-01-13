from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ..core.config import settings

# 根据不同数据库驱动调整连接池参数，确保在多数据库环境下表现稳定
# SQL echo 默认关闭，避免日志过多，可通过环境变量 SQL_ECHO=true 开启
import os
sql_echo = os.getenv("SQL_ECHO", "").lower() in ("true", "1", "yes")
engine_kwargs = {"echo": sql_echo}
if settings.is_sqlite_backend:
    # SQLite 场景下禁用连接池并放宽线程检查，避免多协程读写冲突
    # 设置较长的超时时间（30秒）以减少 database is locked 错误
    engine_kwargs.update(
        pool_pre_ping=False,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
else:
    # MySQL 场景保持健康检查与连接复用，适用于生产环境的长连接需求
    engine_kwargs.update(pool_pre_ping=True, pool_recycle=3600)

engine = create_async_engine(settings.sqlalchemy_database_uri, **engine_kwargs)


# SQLite 启用 WAL 模式，允许读写并发，显著减少锁冲突
if settings.is_sqlite_backend:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30秒超时
        cursor.close()

# 统一的 Session 工厂，禁用 expire_on_commit 方便返回模型对象
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖项：提供一个作用域内共享的数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
