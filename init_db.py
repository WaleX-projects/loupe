import asyncio
from app.db.database import engine
from app.db.base import Base
# Import your models so SQLAlchemy registers them with Base.metadata
from app.db.models import Project, Sandbox  

async def init_db():
    async with engine.begin() as conn:
        # Drops existing tables (optional, be careful) and creates new ones
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())