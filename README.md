# PeakPick Notification Service

Owns notification read models for ready-order and shortage messages.

Owned database tables:

- local `event_log`

Run locally:

```bash
pip install -r requirements.txt
uvicorn services.notification_service.main:app --reload --port 8006
```
