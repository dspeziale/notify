"""Background and on-demand polling service for inbound Telegram messages.
Includes Redis-backed distributed locking to ensure only a single worker polls Telegram,
preventing Telegram Bot API 409 Conflict errors across multi-process deployments.
"""

import asyncio
import json
import logging
import random
import uuid
import httpx
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.inbound_message import InboundMessage
from app.models.telegram_config import TelegramConfiguration
from app.services.telegram_config_service import TelegramConfigService

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None
_config_offsets: dict[uuid.UUID, int] = {}


async def _get_redis() -> aioredis.Redis | None:
    """Returns or creates the shared async Redis client."""
    global _redis_client
    if settings.REDIS_ENABLED and settings.REDIS_URL and aioredis:
        if _redis_client is None:
            try:
                _redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception as exc:
                logger.warning("Could not connect to Redis for Telegram poller: %s", exc)
                _redis_client = None
        return _redis_client
    return None


async def get_bot_offset(cfg_id: uuid.UUID) -> int | None:
    """Gets the latest acknowledged update_id offset for a Telegram bot."""
    redis = await _get_redis()
    if redis:
        try:
            val = await redis.get(f"vortex:tg_offset:{cfg_id}")
            if val is not None:
                return int(val)
        except Exception:
            pass
    return _config_offsets.get(cfg_id)


async def set_bot_offset(cfg_id: uuid.UUID, offset: int) -> None:
    """Persists the latest acknowledged update_id offset."""
    _config_offsets[cfg_id] = offset
    redis = await _get_redis()
    if redis:
        try:
            await redis.set(f"vortex:tg_offset:{cfg_id}", str(offset), ex=86400 * 7)
        except Exception:
            pass


async def sync_telegram_inbound_messages(db: AsyncSession) -> int:
    """Fetches new messages from Telegram for all active bot configurations and saves them to InboundMessage."""
    svc = TelegramConfigService(db)
    result = await db.execute(
        select(TelegramConfiguration).where(TelegramConfiguration.is_active == True)  # noqa: E712
    )
    configs = result.scalars().all()
    if not configs:
        return 0

    total_new = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for cfg in configs:
            try:
                bot_token = await svc.get_decrypted_token(cfg)
                if not bot_token:
                    continue

                current_offset = await get_bot_offset(cfg.id)
                params: dict[str, int | str] = {"limit": 100, "timeout": 1}
                if current_offset is not None:
                    params["offset"] = current_offset

                url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                res = await client.get(url, params=params)

                # Handle webhook active conflict
                if res.status_code == 409:
                    err_desc = res.json().get("description", "").lower()
                    if "webhook" in err_desc:
                        logger.info("Webhook active on bot %s. Deleting webhook...", cfg.id)
                        await client.post(f"https://api.telegram.org/bot{bot_token}/deleteWebhook", json={"drop_pending_updates": False})
                        await asyncio.sleep(0.5)
                        res = await client.get(url, params=params)
                    else:
                        logger.debug("Telegram polling conflict on bot %s: %s", cfg.id, err_desc)
                        continue

                if res.status_code != 200:
                    logger.warning("Telegram getUpdates returned %s for config %s", res.status_code, cfg.id)
                    continue

                data = res.json()
                updates = data.get("result") or []
                if not updates:
                    continue

                max_offset = current_offset or 0
                for update in updates:
                    update_id = update.get("update_id", 0)
                    if update_id >= max_offset:
                        max_offset = update_id + 1

                    msg = (
                        update.get("message")
                        or update.get("channel_post")
                        or update.get("edited_message")
                        or {}
                    )
                    if not msg:
                        continue

                    from_info = msg.get("from") or {}
                    chat_info = msg.get("chat") or {}
                    sender_id = str(chat_info.get("id") or from_info.get("id") or "unknown")
                    sender_name = from_info.get("first_name") or from_info.get("username") or "Telegram User"
                    text_content = msg.get("text") or msg.get("caption") or ""

                    inbound = InboundMessage(
                        application_id=cfg.application_id,
                        provider="telegram",
                        configuration_id=cfg.id,
                        sender_identifier=sender_id,
                        sender_name=sender_name,
                        recipient_identifier=str(cfg.name or "Telegram Bot"),
                        message_text=text_content,
                        raw_payload=json.dumps(update),
                        status="received",
                    )
                    db.add(inbound)
                    total_new += 1

                await set_bot_offset(cfg.id, max_offset)

                if total_new > 0:
                    await db.commit()
                    # Acknowledge to Telegram
                    await client.get(url, params={"offset": max_offset, "limit": 1})
                    logger.info("Saved %d new Telegram messages for bot config %s", total_new, cfg.id)

            except Exception as exc:
                logger.error("Error polling Telegram updates for config %s: %s", cfg.id, exc)

    return total_new


async def run_telegram_inbound_poller():
    """Background continuous loop polling active Telegram bots.
    Uses Redis distributed leasing with worker ownership renewal to ensure only ONE worker
    process polls Telegram at any given time, preventing Telegram Bot API 409 Conflicts.
    """
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    lock_key = "vortex:telegram_poller_lock"
    logger.info("Starting background Telegram inbound polling worker (%s).", worker_id)

    # Stagger worker starts to avoid boot race
    await asyncio.sleep(random.uniform(0.5, 3.0))

    while True:
        have_lock = False
        redis = None
        try:
            redis = await _get_redis()
            if redis:
                # Try to acquire lock if free
                acquired = await redis.set(lock_key, worker_id, ex=8, nx=True)
                if not acquired:
                    # Check if currently held by this same worker
                    curr_owner = await redis.get(lock_key)
                    if curr_owner == worker_id:
                        # Refresh our own lease for 8 seconds
                        await redis.set(lock_key, worker_id, ex=8)
                        have_lock = True
                    else:
                        have_lock = False
                else:
                    have_lock = True
            else:
                # In standalone/no-redis environments, poller runs directly
                have_lock = True

            if have_lock:
                async with AsyncSessionLocal() as db:
                    await sync_telegram_inbound_messages(db)

        except asyncio.CancelledError:
            logger.info("Telegram inbound polling worker (%s) cancelled.", worker_id)
            if redis and have_lock:
                try:
                    curr_owner = await redis.get(lock_key)
                    if curr_owner == worker_id:
                        await redis.delete(lock_key)
                except Exception:
                    pass
            break
        except Exception as exc:
            logger.error("Unexpected error in Telegram polling worker (%s): %s", worker_id, exc)

        await asyncio.sleep(3.5)
