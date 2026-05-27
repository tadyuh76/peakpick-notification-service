from __future__ import annotations

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
    return notifications

