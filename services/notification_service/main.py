from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request

from shared.event_bus import build_event_bus
from shared.events import EventEnvelope, EventType
from shared.logging import configure_logging, log_event
from shared.settings import get_settings


settings = get_settings("notification-service")
logger = configure_logging(settings.service_name)
notifications: list[dict[str, object]] = []


def _database_enabled() -> bool:
    return bool(settings.database_url)


def _notification_from_event_row(row: dict[str, object]) -> dict[str, object] | None:
    payload = row["payload"]
    if not isinstance(payload, dict):
        return None

    event_type = str(row["event_type"])
    if event_type == EventType.NOTIFICATION_REQUESTED:
        return {
            "order_id": row["aggregate_id"],
            "message": payload["message"],
            "channel": payload.get("channel", "demo"),
            "status": "Sent",
            "sent_at": row["occurred_at"].isoformat(),
        }

    if event_type == EventType.INVENTORY_SHORTAGE_DETECTED:
        return {
            "order_id": row["aggregate_id"],
            "message": "Inventory shortage detected. Staff should review the order.",
            "channel": "staff",
            "status": "Sent",
            "sent_at": row["occurred_at"].isoformat(),
            "details": payload.get("shortages", []),
        }

    return None


async def _notifications_from_event_log() -> list[dict[str, object]]:
    return await asyncio.to_thread(_notifications_from_event_log_sync)


def _notifications_from_event_log_sync() -> list[dict[str, object]]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT event_type, aggregate_id, payload, occurred_at
            FROM event_log
            WHERE event_type IN (%s, %s)
            ORDER BY occurred_at ASC, created_at ASC
            """,
            (EventType.NOTIFICATION_REQUESTED, EventType.INVENTORY_SHORTAGE_DETECTED),
        ).fetchall()

    return [
        notification
        for row in rows
        if (notification := _notification_from_event_row(dict(row))) is not None
    ]


async def handle_notification_requested(
    event: EventEnvelope,
    state: list[dict[str, object]] = notifications,
) -> None:
    notification = {
        "order_id": event.aggregate_id,
        "message": event.payload["message"],
        "channel": event.payload.get("channel", "demo"),
        "status": "Sent",
        "sent_at": datetime.now(UTC).isoformat(),
    }
    state.append(notification)
    log_event(logger, settings.service_name, "notification sent", order_id=event.aggregate_id)


async def handle_inventory_shortage(
    event: EventEnvelope,
    state: list[dict[str, object]] = notifications,
) -> None:
    notification = {
        "order_id": event.aggregate_id,
        "message": "Inventory shortage detected. Staff should review the order.",
        "channel": "staff",
        "status": "Sent",
        "sent_at": datetime.now(UTC).isoformat(),
        "details": event.payload["shortages"],
    }
    state.append(notification)


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_bus = build_event_bus(settings)
    await event_bus.connect()
    await event_bus.subscribe(
        EventType.NOTIFICATION_REQUESTED,
        handle_notification_requested,
        queue_name=f"{settings.service_name}.notification-requested",
    )
    await event_bus.subscribe(
        EventType.INVENTORY_SHORTAGE_DETECTED,
        handle_inventory_shortage,
        queue_name=f"{settings.service_name}.inventory-shortage",
    )
    app.state.event_bus = event_bus
    log_event(logger, settings.service_name, "event subscriptions ready", bus=settings.event_bus)
    try:
        yield
    finally:
        await event_bus.close()


app = FastAPI(
    title="PeakPick Notification Service",
    version="0.1.0",
    description="Simulated ready, delay, and shortage notifications.",
    lifespan=lifespan,
)


@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "event_bus_connected": request.app.state.event_bus.is_connected,
    }


@app.get("/notifications")
async def list_notifications() -> list[dict[str, object]]:
    if _database_enabled():
        return await _notifications_from_event_log()
    return notifications
