"""Endpoints for receiving inbound messages from Telegram and Gmail/Email."""

import json
import logging
import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_admin_auth
from app.models.inbound_message import InboundMessage
from app.models.telegram_config import TelegramConfiguration
from app.schemas.common import APIResponse
from app.schemas.inbound_message import EmailInboundPayload, InboundMessageResponse, TelegramWebhookPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inbound", tags=["Inbound Messages"])


@router.post("/telegram/{config_id}", summary="Telegram Webhook Receiver")
async def receive_telegram_webhook(
    config_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Receives inbound updates from Telegram Bot Webhooks."""
    # Find configuration if present
    cfg_q = await db.execute(select(TelegramConfiguration).where(TelegramConfiguration.id == config_id))
    cfg = cfg_q.scalar_one_or_none()

    msg = payload.get("message") or payload.get("channel_post") or payload.get("edited_message") or {}
    from_info = msg.get("from") or {}
    chat_info = msg.get("chat") or {}

    sender_id = str(chat_info.get("id") or from_info.get("id") or "unknown")
    sender_name = from_info.get("first_name") or from_info.get("username") or "Telegram User"
    text_content = msg.get("text") or msg.get("caption") or ""

    inbound = InboundMessage(
        application_id=cfg.application_id if cfg else None,
        provider="telegram",
        configuration_id=config_id,
        sender_identifier=sender_id,
        sender_name=sender_name,
        recipient_identifier=str(cfg.bot_token[:10]) if cfg else None,
        message_text=text_content,
        raw_payload=json.dumps(payload),
        status="received",
    )
    db.add(inbound)
    await db.commit()

    logger.info("Received inbound Telegram message from %s (config: %s)", sender_id, config_id)
    return {"ok": True, "message_id": str(inbound.id)}


@router.post("/email", summary="Generic / Gmail Inbound Email Receiver")
async def receive_email_inbound(
    payload: EmailInboundPayload,
    db: AsyncSession = Depends(get_db),
):
    """Ingests incoming emails from webhooks, Google Pub/Sub, or SMTP relays."""
    inbound = InboundMessage(
        provider="email",
        sender_identifier=payload.from_email,
        sender_name=payload.from_name,
        recipient_identifier=payload.to_email,
        subject=payload.subject,
        message_text=payload.body_text,
        raw_payload=payload.raw_payload,
        status="received",
    )
    db.add(inbound)
    await db.commit()

    logger.info("Received inbound Email from %s to %s", payload.from_email, payload.to_email)
    return {"ok": True, "message_id": str(inbound.id)}


@router.get("/messages", response_model=APIResponse[list[InboundMessageResponse]], summary="List inbound messages (Admin)")
async def list_inbound_messages(
    provider: str | None = Query(None, description="Filter by provider: telegram, email"),
    limit: int = 50,
    offset: int = 0,
    admin_auth: bool = Depends(require_admin_auth),
    db: AsyncSession = Depends(get_db),
):
    """Lists received incoming messages for inspection in dashboard."""
    query = select(InboundMessage).order_by(desc(InboundMessage.created_at)).offset(offset).limit(limit)
    if provider:
        query = query.where(InboundMessage.provider == provider)

    res = await db.execute(query)
    messages = res.scalars().all()

    return APIResponse(data=[InboundMessageResponse.model_validate(m) for m in messages])

