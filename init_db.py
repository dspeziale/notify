"""Database initialization and administrator bootstrap script."""

import asyncio
import logging
from sqlalchemy import select
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import generate_api_key
from app.database.base import Base
from app.database.session import AsyncSessionLocal, engine
from app.models.api_key import APIKey
from app.models.application import Application
from app.models.permission import NotificationPermission

setup_logging(debug=True)
logger = logging.getLogger("init_db")


async def init_database():
    """Initializes tables and optionally creates a default bootstrap application."""
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema synchronized successfully.")

    async with AsyncSessionLocal() as session:
        # Check if any application exists
        result = await session.execute(select(Application))
        existing_app = result.scalars().first()

        if not existing_app:
            logger.info("No applications found. Creating default 'Default-Client' application...")
            app = Application(
                name="Default-Client",
                description="Default bootstrap client application",
                status="active",
                rate_limit_per_minute=120,
            )
            session.add(app)
            await session.flush()

            # Grant permissions
            for perm in ["telegram:send", "gmail:send"]:
                session.add(NotificationPermission(application_id=app.id, permission=perm))

            # Generate API Key
            raw_key, key_prefix, hashed_key = generate_api_key()
            api_key = APIKey(
                application_id=app.id,
                name="Default Bootstrap Key",
                key_prefix=key_prefix,
                hashed_key=hashed_key,
                is_admin=False,
                is_active=True,
            )
            session.add(api_key)
            await session.commit()

            print("=" * 70)
            print("🚀 BOOTSTRAP APPLICATION CREATED:")
            print(f"Application ID: {app.id}")
            print(f"Application Name: {app.name}")
            print(f"Initial API Key: {raw_key}")
            print("⚠️  SAVE THIS API KEY IMMEDIATELY! It will never be shown again.")
            print("=" * 70)
        else:
            logger.info("Database already contains applications. Bootstrap skipped.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())

