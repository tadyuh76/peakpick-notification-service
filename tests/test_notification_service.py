from fastapi.testclient import TestClient

from services.notification_service.main import app, notifications


client = TestClient(app)


def test_notifications_filter_by_order_and_channel() -> None:
    notifications.clear()
    notifications.extend(
        [
            {
                "order_id": "order-1",
                "message": "Ready",
                "channel": "demo",
                "status": "Sent",
                "sent_at": "2026-06-09T00:00:00+00:00",
            },
            {
                "order_id": "order-2",
                "message": "Shortage",
                "channel": "staff",
                "status": "Sent",
                "sent_at": "2026-06-09T00:01:00+00:00",
            },
        ]
    )

    response = client.get("/notifications?order_id=order-2&channel=staff")

    assert response.status_code == 200
    assert response.json() == [notifications[1]]
