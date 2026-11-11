"""Background and on-demand polling service for inbound Telegram messages."""

import asyncio
import json
import logging
import uuid
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import AsyncSessionLocal
from app.models.inbound_message import InboundMessage
from app.models.telegram_config import TelegramConfiguration
from app.services.telegram_config_service import TelegramConfigService

logger = logging.getLogger(__name__)

# In-memory registry to track update offsets per Telegram configuration ID
_config_offsets: dict[uuid.UUID, int] = {}


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

                current_offset = _config_offsets.get(cfg.id)
                params: dict[str, int | str] = {"limit": 100}
                if current_offset is not None:
                    params["offset"] = current_offset

                url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                res = await client.get(url, params=params)

                # If a webhook was previously active, delete it to enable getUpdates
                if res.status_code == 409:
                    logger.info("Webhook conflict on Telegram bot %s. Deleting webhook to enable polling.", cfg.id)
                    await client.post(f"https://api.telegram.org/bot{bot_token}/deleteWebhook")
                    res = await client.get(url, params=params)

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

                _config_offsets[cfg.id] = max_offset

                if total_new > 0:
                    await db.commit()
                    # Acknowledge processed updates to Telegram so they aren't redelivered
                    await client.get(url, params={"offset": max_offset, "limit": 1})
                    logger.info("Saved %d new Telegram messages for bot config %s", total_new, cfg.id)

            except Exception as exc:
                logger.error("Error polling Telegram updates for config %s: %s", cfg.id, exc)

    return total_new


async def run_telegram_inbound_poller():
    """Background continuous loop polling active Telegram bots for new incoming messages."""
    logger.info("Starting background Telegram inbound message polling worker.")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await sync_telegram_inbound_messages(db)
        except asyncio.CancelledError:
            logger.info("Telegram inbound polling worker cancelled.")
            break
        except Exception as exc:
            logger.error("Unexpected error in Telegram polling worker: %s", exc)

        await asyncio.sleep(6)  # Poll interval
