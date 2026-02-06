# 🔔 Notification System Architecture

> **Version**: 2.0  
> **Last Updated**: February 2026

## 🌟 Overview

The Notification System has been completely refactored to provide a unified, reliable, and asynchronous way to send notifications across multiple channels (Email, Telegram, SMS, Push). It uses a centralized `NotificationSenderService`, decoupled business logic, and background processing via Celery.

## 🏗️ Core Components

### 1. Unified Sender Service (`NotificationSenderService`)
Located in `app/services/notifications.py`.
- **Single Entry Point**: `send_notification()` handles all channel logic.
- **Provider Abstraction**: Decouples providers (SMTP, Telegram Bot, Eskiz SMS, FCM) from business logic.
- **Template Management**: Renders Jinja2 templates for emails and standardized text for other channels.
- **Logging & History**: Automatic tracking of all sent notifications in `NotificationHistory`.

### 2. Business Logic Services
- **`QueuePositionNotificationService`**: Handles queue-related notifications (status changes, "you are next", "called").
- **`RegistrarNotificationService`**: Notifications for registrars.
- **`LabNotificationService`**: Notifications for lab results.
- **`ForceMajeureService`**: Emergency mass notifications.

### 3. Asynchronous Processing (Celery) [Planned/In-Progress]
- **Tasks**: `tasks.notifications.send_notification_task`.
- **Queues**: `notifications` queue in Redis.
- **Retry Policy**: Exponential backoff for network failures.

### 4. Data Models
- **`UserNotificationSettings`**: User preferences for channels and types (SSOT in `app/models/user_profile.py`).
- **`NotificationHistory`**: Audit log of sent messages (`app/models/notification_history.py`).
- **`NotificationTemplate`**: Stored templates in DB (`app/models/notification_template.py`).

## 🔄 Data Flow

1. **Trigger**: Event occurs (e.g., patient joins queue).
2. **Business Service**: `QueuePositionNotificationService` prepares data.
3. **Dispatch**: Calls `NotificationSenderService.send_push()` or `send_notification()`.
4. **Validation**: Service checks `UserNotificationSettings` to see if user enabled this notification type/channel.
5. **Execution**:
    - **Push**: Direct websocket + FCM.
    - **Telegram**: HTTP call to Telegram Bot API.
    - **SMS**: HTTP call to SMS Provider (Eskiz).
    - **Email**: SMTP execution (potentially backgrounded).
6. **Logging**: Record added to `NotificationHistory`.

## 🔌 Channels & Providers

| Channel | Provider | Configuration | Key Features |
|---------|----------|---------------|--------------|
| **Email** | SMTP | `SMTP_SERVER`, `SMTP_PORT` | HTML Templates, Attachments |
| **Telegram** | Bot API | `TELEGRAM_BOT_TOKEN` | Markdown support, Instant delivery |
| **SMS** | Eskiz.uz | `SMS_API_KEY` | High reliability for critical alerts |
| **Push** | FCM + WS | `FIREBASE_CREDENTIALS` | Real-time in-app updates |

## 🛠️ Developer Usage

### Sending a Simple Notification
```python
from app.services.notifications import notification_sender_service

await notification_sender_service.send_notification(
    recipient=user,
    notification_type="appointment_reminder",
    channels=["telegram", "push"],
    title="Appointment Reminder",
    body="You have an appointment tomorrow at 10:00",
    data={"appointment_id": 123}
)
```

### Checking User Settings
```python
if user.notification_settings.email_enabled:
    # send email...
```

## 📊 Monitoring & Maintenance

- **History**: Check `NotificationHistory` table for delivery status.
- **Logs**: Application logs track provider responses and errors.
- **Admin Panel**: View status of queues and recent notifications.
