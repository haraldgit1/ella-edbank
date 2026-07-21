from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from edbank_mcp.config import settings

engine = create_async_engine(settings.mcp_database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
