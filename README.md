# PeakPick Notification Service

Notification Service là microservice mô phỏng thông báo cho khách khi đơn sẵn sàng hoặc có vấn đề thiếu hàng.

## Database Riêng

Service này sở hữu database `peakpick_notification` với bảng:

- `event_log`

Notification trong bài là read model demo, chưa tích hợp SMS/email thật.

## Event

Nhận event:

- `NotificationRequested`
- `InventoryShortageDetected`

## Chạy Local

```bash
pip install -r requirements.txt
uvicorn services.notification_service.main:app --reload --port 8006
```
