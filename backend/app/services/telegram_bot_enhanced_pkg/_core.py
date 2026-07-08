"""Core mixin for EnhancedTelegramBotService.

Split from telegram_bot_enhanced.py.
"""
from __future__ import annotations

from app.services.telegram_bot_enhanced_pkg._base import *  # noqa: F401, F403
from app.services.telegram_bot_enhanced_pkg._base import EnhancedTelegramBotServiceMixinBase

class CoreMixin(EnhancedTelegramBotServiceMixinBase):
    """Core methods for EnhancedTelegramBotService."""

    def __init__(self):
        super().__init__()
        self.admin_commands = {
            "/admin_stats": self._handle_admin_stats,
            "/admin_queues": self._handle_admin_queues,
            "/admin_patients": self._handle_admin_patients,
            "/admin_appointments": self._handle_admin_appointments,
            "/admin_doctors": self._handle_admin_doctors,
            "/admin_services": self._handle_admin_services,
            "/admin_notifications": self._handle_admin_notifications,
            "/admin_reports": self._handle_admin_reports,
            "/admin_backup": self._handle_admin_backup,
            "/admin_settings": self._handle_admin_settings,
        }

        self.user_commands = {
            "/start": self._handle_start,
            "/help": self._handle_help,
            "/menu": self._handle_menu,
            "/appointments": self._handle_appointments,
            "/book": self._handle_book,
            "/cancel": self._handle_cancel,
            "/reschedule": self._handle_reschedule,
            "/profile": self._handle_profile,
            "/doctors": self._handle_doctors,
            "/services": self._handle_services,
            "/queue": self._handle_queue,
            "/status": self._handle_status,
            "/feedback": self._handle_feedback,
            "/emergency": self._handle_emergency,
            "/language": self._handle_language,
            "/notifications": self._handle_notifications_settings,
        }


    async def _handle_command(
        self, command: str, chat_id: int, telegram_user, db: Session, max_retries: int = 2
    ):
        """
        Расширенная обработка команд с retry логикой

        ✅ SECURITY: Implements error handling and retry for command processing
        """
        for attempt in range(max_retries):
            try:
                # Проверяем права администратора
                is_admin = await self._check_admin_rights(telegram_user, db)

                # Обрабатываем админские команды
                if command in self.admin_commands and is_admin:
                    await self.admin_commands[command](chat_id, telegram_user, db)
                    return  # Success
                # Обрабатываем пользовательские команды
                elif command in self.user_commands:
                    await self.user_commands[command](chat_id, telegram_user, db)
                    return  # Success
                else:
                    await self._send_unknown_command_message(chat_id)
                    return  # Unknown command, no retry needed

            except Exception as e:
                logger.error(f"Ошибка обработки команды {command} (попытка {attempt + 1}/{max_retries}): {e}", exc_info=True)

                # Don't retry on certain errors
                if isinstance(e, ValueError | KeyError | AttributeError):
                    await self._send_error_message(chat_id)
                    return

                # Retry on transient errors
                if attempt < max_retries - 1:
                    wait_time = 1 * (attempt + 1)  # Linear backoff: 1s, 2s
                    logger.warning(f"Retrying command {command} in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed
                    await self._send_error_message(chat_id)
                    return


    async def _check_admin_rights(self, telegram_user, db: Session) -> bool:
        """Проверка прав администратора"""
        try:
            if not telegram_user or not telegram_user.linked_user_id:
                return False

            user = crud_user.get(db, id=telegram_user.linked_user_id)
            return user and user.role in ["Admin", "SuperAdmin"]
        except Exception:
            return False

    # ==================== АДМИНСКИЕ КОМАНДЫ ====================


    async def _send_error_message(self, chat_id: int):
        """Отправка сообщения об ошибке"""
        message = """❌ Произошла ошибка при выполнении команды.

Попробуйте позже или обратитесь в техподдержку."""

        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 Попробовать снова", "callback_data": "retry"}],
                [{"text": "📞 Техподдержка", "callback_data": "support"}],
            ]
        }

        await self._send_message(chat_id, message, reply_markup=keyboard)


    async def _send_message(
        self, chat_id: int, text: str, parse_mode: str = None, reply_markup: dict = None, max_retries: int = 3
    ):
        """
        Отправка сообщения через Telegram API с retry логикой

        ✅ SECURITY: Implements exponential backoff retry for reliability
        ✅ BUGFIX: Uses async HTTP client (httpx) instead of blocking requests
        """
        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": text}

        if parse_mode:
            data["parse_mode"] = parse_mode

        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        # ✅ BUGFIX: Use async HTTP client to avoid blocking event loop
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Retry logic with exponential backoff
            for attempt in range(max_retries):
                try:
                    response = await client.post(url, json=data)

                    # Check for rate limiting (429)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()

                    result = response.json()
                    if result.get("ok"):
                        return True
                    else:
                        error = result.get("description", "Unknown error")
                        logger.error(f"Telegram API error: {error}")

                        # Don't retry on certain errors (bad request, forbidden, etc.)
                        if response.status_code in (400, 401, 403, 404):
                            return False

                        # Retry on server errors (500, 502, 503, 504)
                        if response.status_code >= 500 and attempt < max_retries - 1:
                            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                            logger.warning(f"Server error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue

                        return False

                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Request timeout, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("Request timeout after all retries")
                        return False

                except httpx.NetworkError:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("Connection error after all retries")
                        return False

                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    return False

                except Exception as e:
                    logger.error(f"Unexpected error sending message: {e}")
                    return False

        return False


    async def send_admin_notification(self, message: str, db: Session):
        """
        Отправка уведомления всем администраторам с error handling

        ✅ SECURITY: Implements comprehensive error handling
        """
        try:
            # Получаем всех администраторов с Telegram
            admins = (
                db.query(User)
                .filter(
                    and_(
                        User.role.in_(["Admin", "SuperAdmin"]),
                        User.telegram_chat_id.isnot(None),
                    )
                )
                .all()
            )

            if not admins:
                logger.warning("No admins with Telegram chat ID found")
                return

            success_count = 0
            for admin in admins:
                try:
                    success = await self._send_message(
                        admin.telegram_chat_id,
                        f"🔔 **Уведомление администратора**\\n\\n{message}",
                        parse_mode="Markdown",
                    )
                    if success:
                        success_count += 1
                    else:
                        logger.warning(f"Failed to send notification to admin {admin.id}")
                except Exception as e:
                    logger.error(f"Error sending to admin {admin.id}: {e}")

            logger.info(f"Admin notification sent to {success_count}/{len(admins)} admins")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администраторам: {e}", exc_info=True)


    async def send_bulk_notification(
        self, message: str, user_ids: list[int], db: Session, batch_size: int = 10
    ):
        """
        Массовая отправка уведомлений с retry логикой

        ✅ SECURITY: Implements batch processing and error recovery
        """
        try:
            success_count = 0
            failed_count = 0
            failed_users = []

            # Process in batches to avoid rate limiting
            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i:i + batch_size]

                for user_id in batch:
                    try:
                        user = crud_user.get(db, id=user_id)
                        if user and user.telegram_chat_id:
                            success = await self._send_message(user.telegram_chat_id, message)
                            if success:
                                success_count += 1
                            else:
                                failed_count += 1
                                failed_users.append(user_id)
                        else:
                            logger.warning(f"User {user_id} has no Telegram chat ID")
                            failed_count += 1

                        # Небольшая задержка между отправками
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.error(f"Error sending to user {user_id}: {e}")
                        failed_count += 1
                        failed_users.append(user_id)

                # Longer delay between batches to respect rate limits
                if i + batch_size < len(user_ids):
                    await asyncio.sleep(1)

            # Retry failed users once
            if failed_users:
                logger.info(f"Retrying {len(failed_users)} failed notifications...")
                await asyncio.sleep(5)  # Wait before retry

                for user_id in failed_users[:]:
                    try:
                        user = crud_user.get(db, id=user_id)
                        if user and user.telegram_chat_id:
                            success = await self._send_message(user.telegram_chat_id, message)
                            if success:
                                success_count += 1
                                failed_users.remove(user_id)
                                failed_count -= 1
                    except Exception as e:
                        logger.error(f"Retry failed for user {user_id}: {e}")

            logger.info(f"Bulk notification: {success_count} sent, {failed_count} failed")
            return success_count

        except Exception as e:
            logger.error(f"Ошибка массовой отправки: {e}", exc_info=True)
            return success_count  # Return partial success count


# Глобальный экземпляр расширенного бота


def get_enhanced_telegram_bot() -> EnhancedTelegramBotService:
    """Получить экземпляр расширенного Telegram бота"""
    return enhanced_telegram_bot


