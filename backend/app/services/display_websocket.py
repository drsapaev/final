"""
WebSocket сервис для табло очереди
Основа: passport.md стр. 2571-3324, detail.md стр. 1567-1789
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.api.v1.endpoints.ws_token import accept_echoing_subprotocol
from app.db.session import SessionLocal
from app.models.display_config import DisplayBoard
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.ws_redis_pubsub import RedisPubSubBridge

logger = logging.getLogger(__name__)


class DisplayWebSocketManager:
    """Менеджер WebSocket соединений для табло"""

    def __init__(self, pubsub: RedisPubSubBridge | None = None):
        # Активные соединения по board_id
        self.connections: dict[str, set[WebSocket]] = {}
        # Последнее состояние каждого табло
        self.board_states: dict[str, dict[str, Any]] = {}
        self._pubsub = pubsub or RedisPubSubBridge(
            channel_prefix="display_ws",
            redis_url=(os.getenv("WS_REDIS_URL") or os.getenv("REDIS_URL")),
        )
        # RQ-24.a.1: формат имени пациента борда (DisplayBoard.
        # show_patient_names: full/initials/none), кэш на board_id —
        # без чтения конфига на каждое сообщение.
        # DISPLAYPRIVACY-BE-001 (audit PR #3961): кэш ИНВАЛИДИРУЕТСЯ при
        # успешном админ-обновлении show_patient_names (локально +
        # control-сообщение другим воркерам) — раньше устаревший 'full'
        # раскрывал имена до рестарта.
        self._name_format_cache: dict[str, str] = {}
        # Redis pubsub-обработчики по board_id (connect/disconnect):
        # восстановлено — черновик PR #3214 заменил эту строку кэшем
        # вместо добавления, что ломало connect() (CI RED HEAD).
        self._redis_handlers: dict[str, Any] = {}

    async def connect(self, websocket: WebSocket, board_id: str, user=None) -> None:
        """Подключение нового WebSocket с опциональной аутентификацией"""
        try:
            await accept_echoing_subprotocol(websocket)

            if board_id not in self.connections:
                self.connections[board_id] = set()

            self.connections[board_id].add(websocket)

            # Сохраняем информацию о пользователе для этого соединения
            if user:
                if not hasattr(websocket, "_user_info"):
                    websocket._user_info = {}
                websocket._user_info["user"] = user
                websocket._user_info["authenticated"] = True
                logger.info(
                    f"Аутентифицированный WebSocket подключен к табло {board_id} (пользователь: {user.username})"
                )
            else:
                logger.info(f"Анонимный WebSocket подключен к табло {board_id}")

            logger.info(
                f"Всего соединений к табло {board_id}: {len(self.connections[board_id])}"
            )
            await self._ensure_redis_subscription(board_id)
            # DISPLAYPRIVACY-BE-001 (audit PR #3961): подписка control-канала
            # инвалидации кэша формата имён — до первого резолва политики
            # (кэш-запись без подписки пропустила бы control-сообщение).
            await self._ensure_nameformat_ctl_subscription()

            # Отправляем текущее состояние табло
            await self._send_current_state(websocket, board_id)

        except Exception as e:
            logger.error(f"Ошибка подключения WebSocket: {e}")

    async def disconnect(self, websocket: WebSocket, board_id: str) -> None:
        """Отключение WebSocket"""
        try:
            if board_id in self.connections:
                self.connections[board_id].discard(websocket)

                if len(self.connections[board_id]) == 0:
                    del self.connections[board_id]
                    await self._remove_redis_subscription(board_id)

            logger.info(f"WebSocket отключен от табло {board_id}")

        except Exception as e:
            logger.error(f"Ошибка отключения WebSocket: {e}")

    async def broadcast_to_board(self, board_id: str, message: dict[str, Any]) -> str:
        """Отправка сообщения всем подключенным к табло.

        DISPLAYDELIVERY-BE-001 (audit PR #3961): возвращает статус доставки
        по табло вместо молчаливого проглатывания сбоя. Возможные значения:

        - ``"delivered_local"`` — на этом воркере живой сокет получил
          сообщение и Redis publish для других воркеров прошёл;
        - ``"published_only"`` — на этом воркере нет сокетов; сообщение
          опубликовано для других воркеров (их доставка отсюда не
          подтверждается — ACK-семантики нет);
        - ``"failed"`` — локальная отправка или publish возбудили ошибку.

        Никогда не бросает исключение наружу.
        """
        # DISPLAYPRIVACY-BE-001 (audit PR #3961): гарантируем подписку
        # control-канала до доставки (единственная choke-point всех
        # broadcast-путей — кэш-записи без подписки не должны терять
        # control-сообщения инвалидации).
        await self._ensure_nameformat_ctl_subscription()
        try:
            sent = await self._broadcast_to_board_local(board_id, message)
            if not isinstance(sent, int):
                sent = int(sent or 0)
        except Exception as e:
            logger.error(f"Ошибка локальной отправки для табло {board_id}: {e}")
            return "failed"
        try:
            await self._pubsub.publish(self._board_channel(board_id), message)
        except Exception as e:
            logger.error(f"Ошибка publish для табло {board_id}: {e}")
            return "failed"
        if sent > 0:
            return "delivered_local"
        return "published_only"

    def _board_channel(self, board_id: str) -> str:
        return f"board:{board_id}"

    async def _ensure_redis_subscription(self, board_id: str) -> None:
        if board_id in self._redis_handlers:
            return

        async def _handler(payload: dict[str, Any], _board_id: str = board_id) -> None:
            await self._broadcast_to_board_local(_board_id, payload)

        # DISPLAYRELAY-BE-003 (audit PR #3961): подписка выполняется ПЕРЕД
        # кэшированием обработчика. Мост возвращает честный статус подписки;
        # сбой НЕ кэшируется — следующее подключение к тому же табло
        # повторит попытку (раньше мёртвый кэш жил вечно для живых сокетов).
        subscribed = False
        try:
            subscribed = bool(
                await self._pubsub.subscribe(self._board_channel(board_id), _handler)
            )
        except Exception as e:
            logger.error(f"Ошибка Redis-подписки для табло {board_id}: {e}")
        if subscribed:
            self._redis_handlers[board_id] = _handler
        else:
            logger.warning(
                f"Redis-подписка табло {board_id} не выполнена; "
                "повтор при следующем подключении"
            )

    async def _remove_redis_subscription(self, board_id: str) -> None:
        handler = self._redis_handlers.pop(board_id, None)
        if handler is None:
            return
        await self._pubsub.unsubscribe(self._board_channel(board_id), handler)

    async def _broadcast_to_board_local(
        self, board_id: str, message: dict[str, Any]
    ) -> int:
        """Локальная доставка сокетам табло; возвращает число успешных
        отправок (0 — нет живых сокетов на этом воркере)."""
        if board_id not in self.connections:
            return 0

        # Обновляем состояние табло
        self.board_states[board_id] = {
            **self.board_states.get(board_id, {}),
            **message,
            "last_update": datetime.now(UTC).isoformat(),
        }

        # Отправляем всем подключенным
        disconnected = set()
        sent = 0
        for websocket in self.connections[board_id].copy():
            try:
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
                sent += 1
            except WebSocketDisconnect:
                disconnected.add(websocket)
            except Exception as e:
                logger.error(f"Ошибка отправки WebSocket сообщения: {e}")
                disconnected.add(websocket)

        # Удаляем отключенные соединения
        for ws in disconnected:
            self.connections[board_id].discard(ws)

        if disconnected:
            logger.info(f"Удалено {len(disconnected)} отключенных соединений")
        return sent

    def build_patient_call_message(
        self,
        queue_entry: OnlineQueueEntry,
        doctor_name: str,
        cabinet: str = None,
        board_ids: list[str] | None = None,
    ) -> dict:
        """Собрать payload вызова пациента (синхронно, может обращаться к
        lazy-отношениям queue_entry — вызывать при открытой сессии).

        Codex P2 (round-14): сборка payload отделена от отправки, чтобы
        GraphQL-мутация могла собрать сообщение в worker-треде (сессия
        открыта там), а на event loop осталась только network-отправка.
        """
        # RQ-24.a.1: формат имён по show_patient_names целевых табло
        name_format = self._resolve_name_format(board_ids)
        return {
            "type": "patient_call",
            "data": {
                "id": queue_entry.id,
                "queue_entry_id": queue_entry.id,
                "queue_number": queue_entry.number,
                "patient_name": self._format_patient_name(
                    queue_entry.patient_name, name_format
                ),
                "doctor_name": doctor_name,
                "cabinet": cabinet or "Каб. не указан",
                "specialty": (
                    queue_entry.queue.specialist.specialty
                    if queue_entry.queue.specialist
                    else "Врач"
                ),
                "called_at": (
                    queue_entry.called_at.isoformat()
                    if queue_entry.called_at
                    else datetime.now(UTC).isoformat()
                ),
                "urgency": "normal",  # normal, urgent, emergency
            },
            "display_duration": 30,  # Секунды показа
            "sound_enabled": True,
            "voice_text": f"Пациент номер {queue_entry.number}, пройдите в {cabinet or 'кабинет врача'}",
        }

    def _resolve_untargeted_board_ids(self) -> list[str]:
        """DISPLAYRELAY-BE-001 (audit PR #3961): ``board_ids=None`` означает
        «все активные табло системы», а не «локальные сокеты ЭТОГО воркера».
        Целевой набор резолвится из реестра DisplayBoard (строки БД —
        достижимы с других воркеров через per-board Redis publish) и
        объединяется с локально подключёнными комнатами (dedup). При сбое
        реестра — честный деградационный фолбэк только на локальные комнаты
        (best effort, без крэша).

        Follow-up #4035 (P2-остаток ревью): «активные» — именно
        ``DisplayBoard.active``. Выведенная из эксплуатации (``active=False``)
        табло не входит в нетаргетированный набор ни из реестра, ни из
        локально подключённых комнат, и её политика формата имён не влияет
        на strictest-format агрегацию. Явные цели (``board_ids=[...]``) этот
        фильтр не трогает — права на явный выбор не обходятся молча.
        """
        local = [n for n in self.connections.keys() if n]
        try:
            db = SessionLocal()
            try:
                rows = (
                    db.query(DisplayBoard.name)
                    .filter(DisplayBoard.active == True)
                    .all()
                )
                names = [r[0] for r in rows]
                active_names = set(names)
            finally:
                db.close()
        except Exception as e:
            logger.error(
                "DISPLAYRELAY-BE-001: реестр табло недоступен "
                f"({e}); нетаргетированная трансляция — только локальные комнаты"
            )
            return local
        merged: list[str] = []
        seen: set[str] = set()
        for name in [*names, *(n for n in local if n in active_names)]:
            if name and name not in seen:
                seen.add(name)
                merged.append(name)
        return merged

    async def broadcast_patient_call_data(
        self,
        call_message: dict,
        board_ids: list[str] = None,
    ) -> dict[str, str]:
        """Отправить ПРЕДВАРИТЕЛЬНО СОБРАННЫЙ payload вызова на табло.

        DISPLAYDELIVERY-BE-001 (audit PR #3961): возвращает статусы доставки
        по каждому табло (см. ``broadcast_to_board``); сбои логируются и
        возвращаются, не бросаются наружу.
        """
        statuses: dict[str, str] = {}
        try:
            # DISPLAYTARGET-BE-001: [] означает «явный пустой набор целей»
            # (ничего не отправлять); None — «все активные табло».
            # DISPLAYRELAY-BE-001 (audit PR #3961): «все» резолвится из
            # реестра DisplayBoard ∪ локальные комнаты, не только локальные
            # сокеты этого воркера.
            if board_ids is None:
                board_ids = self._resolve_untargeted_board_ids()

            # Отправляем на указанные табло
            for board_id in board_ids:
                statuses[board_id] = await self.broadcast_to_board(
                    board_id, call_message
                )

            logger.info(
                f"Вызов пациента #{call_message['data']['queue_number']} "
                f"отправлен на {len(board_ids)} табло"
            )

        except Exception as e:
            logger.error(f"Ошибка трансляции вызова пациента: {e}")
        return statuses

    async def broadcast_patient_call(
        self,
        queue_entry: OnlineQueueEntry,
        doctor_name: str,
        cabinet: str = None,
        board_ids: list[str] = None,
    ) -> dict[str, str]:
        """Трансляция вызова пациента на табло.

        DISPLAYDELIVERY-BE-001 (audit PR #3961): возвращает статусы доставки
        по каждому табло (см. ``broadcast_to_board``); сбои логируются и
        возвращаются, не бросаются наружу.
        """
        statuses: dict[str, str] = {}
        try:
            # RQ-24.a.1: формат имён резолвится внутри
            # build_patient_call_message по show_patient_names целевых
            # табло (board_ids передается явно; kwarg name_format не
            # существует в сигнатуре — CI RED HEAD был TypeError).
            # DISPLAYTARGET-BE-001: [] — явный пустой набор целей;
            # None — все активные табло.
            # DISPLAYRELAY-BE-001 (audit PR #3961): «все» — реестр ∪ локальные.
            if board_ids is None:
                board_ids = self._resolve_untargeted_board_ids()
            call_message = self.build_patient_call_message(
                queue_entry, doctor_name, cabinet, board_ids=board_ids
            )
            statuses = await self.broadcast_patient_call_data(
                call_message, board_ids=board_ids
            )

            logger.info(
                f"Вызов пациента #{queue_entry.number} отправлен на {len(board_ids)} табло"
            )

        except Exception as e:
            logger.error(f"Ошибка трансляции вызова пациента: {e}")
        return statuses

    async def broadcast_daily_queue_state(
        self,
        daily_queue: DailyQueue,
        board_ids: list[str] = None,
        event_type: str | None = None,
    ) -> None:
        """Трансляция обновления очереди"""
        db = None
        try:
            db = SessionLocal()

            # Получаем текущую очередь
            queue_entries = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == daily_queue.id)
                .order_by(OnlineQueueEntry.number)
                .all()
            )

            # Формируем данные очереди
            # RQ-24.a.1: формат имён по show_patient_names целевых табло
            name_format = self._resolve_name_format(board_ids)
            queue_data = []
            for entry in queue_entries:
                try:
                    queue_data.append(
                        {
                            # QR-FE-008: queue-scoped identity — каждая строка
                            # несёт владельца (daily_queue.id) и собственный id,
                            # чтобы табло могло влить этот per-queue сабсет в
                            # мультиочередной борд, не затирая строки других
                            # очередей (зеркало initial_state).
                            "id": entry.id,
                            "queue_id": daily_queue.id,
                            "number": entry.number,
                            "patient_name": self._format_patient_name(
                                entry.patient_name, name_format
                            ),
                            "status": entry.status,
                            "source": entry.source,
                            # DISPLAYSESSION-BE-001 (audit PR #3961):
                            # created_at nullable — легаси-строки без даты
                            # сериализуются в null, как в initial_state,
                            # вместо убийства всего обновления табло.
                            "created_at": (
                                entry.created_at.isoformat()
                                if entry.created_at
                                else None
                            ),
                            "called_at": (
                                entry.called_at.isoformat() if entry.called_at else None
                            ),
                        }
                    )
                except Exception as row_exc:
                    # Управляемый построчный отказ: битая строка пропускается
                    # с логом, обновление остальных строк доставляется.
                    logger.error(
                        f"Пропущена строка очереди "
                        f"id={getattr(entry, 'id', '?')} при сериализации: "
                        f"{row_exc}"
                    )

            # Codex P2 (round-14): resource/bridged очередь — владелец и
            # кабинет с оси ресурса (реестр), как в call-обёртках
            # (round-11/12/13): реконнект/стейт-апдейт не должен
            # перезаписывать корректное presentation-имя табло на «Врач»
            # без кабинета. Врач-очереди байт-идентичны.
            if daily_queue.queue_resource_id is not None:
                resource = daily_queue.queue_resource
                display_owner = (
                    resource.display_name if resource is not None else "Ресурс очереди"
                )
                display_cabinet = daily_queue.cabinet_number or (
                    resource.default_cabinet if resource is not None else None
                )
                specialty_label = daily_queue.queue_tag or "Специалист"
            else:
                display_owner = (
                    daily_queue.specialist.user.full_name
                    if daily_queue.specialist and daily_queue.specialist.user
                    else "Врач"
                )
                display_cabinet = (
                    daily_queue.specialist.cabinet if daily_queue.specialist else None
                )
                specialty_label = (
                    daily_queue.specialist.specialty
                    if daily_queue.specialist
                    else "Специалист"
                )

            update_message = {
                "type": "queue_update",
                **({"event_type": event_type} if event_type else {}),
                "data": {
                    # QR-FE-008: backend-owned snapshot scope — payload
                    # описывает ровно ОДНУ дневную очередь; потребители
                    # обязаны вливать его по queue_id, а не заменять весь
                    # мультиочередной борд.
                    "queue_id": daily_queue.id,
                    "doctor_name": display_owner,
                    "specialty": specialty_label,
                    "cabinet": display_cabinet,
                    "queue_date": daily_queue.day.isoformat(),
                    "opened_at": (
                        daily_queue.opened_at.isoformat()
                        if daily_queue.opened_at
                        else None
                    ),
                    "queue_entries": queue_data,
                    "stats": {
                        "total": len(queue_entries),
                        "waiting": len(
                            [e for e in queue_entries if e.status == "waiting"]
                        ),
                        "called": len(
                            [e for e in queue_entries if e.status == "called"]
                        ),
                        "served": len(
                            [e for e in queue_entries if e.status == "served"]
                        ),
                    },
                },
            }

            # Отправляем на табло
            if not board_ids:
                board_ids = list(self.connections.keys())

            for board_id in board_ids:
                await self.broadcast_to_board(board_id, update_message)

        except Exception as e:
            logger.error(f"Ошибка трансляции обновления очереди: {e}")
        finally:
            # DISPLAYSESSION-BE-001 (audit PR #3961): сессия закрывается на
            # успехе И на сбое — раньше close() стоял в конце happy-path и
            # любой эксепшен оставлял соединение до GC.
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    async def broadcast_announcement(
        self,
        announcement_text: str,
        announcement_type: str = "info",
        duration: int = 60,
        board_ids: list[str] = None,
    ) -> dict[str, str]:
        """Трансляция объявления.

        DISPLAYDELIVERY-BE-001 (audit PR #3961): возвращает статусы доставки
        по каждому табло (см. ``broadcast_to_board``); сбои логируются и
        возвращаются, не бросаются наружу.
        """
        statuses: dict[str, str] = {}
        try:
            announcement_message = {
                "type": "announcement",
                "data": {
                    "text": announcement_text,
                    "announcement_type": announcement_type,  # info, warning, emergency
                    "created_at": datetime.now(UTC).isoformat(),
                },
                "display_duration": duration,
                "sound_enabled": announcement_type in ["warning", "emergency"],
                "voice_text": (
                    announcement_text if announcement_type == "emergency" else None
                ),
            }

            # DISPLAYTARGET-BE-001: [] — явный пустой набор целей;
            # None — все активные табло.
            # DISPLAYRELAY-BE-001 (audit PR #3961): «все» — реестр ∪ локальные.
            if board_ids is None:
                board_ids = self._resolve_untargeted_board_ids()

            for board_id in board_ids:
                statuses[board_id] = await self.broadcast_to_board(
                    board_id, announcement_message
                )

            logger.info(f"Объявление отправлено на {len(board_ids)} табло")

        except Exception as e:
            logger.error(f"Ошибка трансляции объявления: {e}")
        return statuses

    async def _send_current_state(self, websocket: WebSocket, board_id: str) -> None:
        """Отправка текущего состояния табло новому подключению"""
        try:
            # Получаем актуальные данные из базы
            db = SessionLocal()
            try:
                # Codex round-29 P2: день снапшота табло — clinic_today
                # SSOT (таймзона настроек очередей): resource-очереди
                # создаются на КЛИНИК-локальном дне, и host date.today()
                # в окне 19:00-24:00Z отдавал пустой/вчерашний снапшот
                # при (пере)подключении табло.
                from app.crud.clinic import clinic_today

                today = clinic_today(db)

                # Получаем активные очереди на сегодня
                queues = (
                    db.query(DailyQueue)
                    .filter(DailyQueue.day == today, DailyQueue.active == True)
                    .all()
                )

                queue_entries = []
                for queue in queues:
                    # Codex P2 (round-14): resource-ось — владелец из
                    # реестра (display_name), не «Врач #None» при NULL
                    # specialist; label считается на очередь, не на запись
                    entries = (
                        db.query(OnlineQueueEntry)
                        .filter(
                            OnlineQueueEntry.queue_id == queue.id,
                            OnlineQueueEntry.status.in_(["waiting", "called"]),
                        )
                        .order_by(OnlineQueueEntry.number)
                        .all()
                    )

                    if queue.queue_resource_id is not None:
                        resource = queue.queue_resource
                        owner_label = (
                            resource.display_name
                            if resource is not None
                            else "Ресурс очереди"
                        )
                    elif queue.specialist and queue.specialist.user:
                        owner_label = queue.specialist.user.full_name
                    else:
                        owner_label = f"Врач #{queue.specialist_id}"

                    # RQ-24.a.1: формат имён по настройке этого табло
                    name_format = self._resolve_name_format([board_id])
                    for entry in entries:
                        queue_entries.append(
                            {
                                "id": entry.id,
                                # QR-FE-008: очередь-владелец каждой строки
                                # снапшота — зеркало scoped-обновлений.
                                "queue_id": queue.id,
                                "number": entry.number,
                                "patient_name": self._format_patient_name(
                                    entry.patient_name or "Пациент", name_format
                                ),
                                "status": entry.status,
                                "specialist_id": queue.specialist_id,
                                "specialist_name": owner_label,
                                "created_at": (
                                    entry.created_at.isoformat()
                                    if entry.created_at
                                    else None
                                ),
                                "called_at": (
                                    entry.called_at.isoformat()
                                    if entry.called_at
                                    else None
                                ),
                            }
                        )

                current_state = {
                    "type": "initial_state",
                    "data": {
                        "queue_entries": queue_entries,
                        "current_call": self.board_states.get(board_id, {}).get(
                            "current_call"
                        ),
                        "announcements": self.board_states.get(board_id, {}).get(
                            "announcements", []
                        ),
                        "last_update": datetime.now(UTC).isoformat(),
                        "board_id": board_id,
                        "total_entries": len(queue_entries),
                        "waiting_entries": len(
                            [e for e in queue_entries if e["status"] == "waiting"]
                        ),
                    },
                }

                await websocket.send_text(json.dumps(current_state, ensure_ascii=False))
                logger.info(
                    f"Отправлено актуальное состояние для табло {board_id}: {len(queue_entries)} записей"
                )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Ошибка отправки текущего состояния: {e}")
            # Отправляем пустое состояние в случае ошибки
            try:
                empty_state = {
                    "type": "initial_state",
                    "data": {
                        "queue_entries": [],
                        "current_call": None,
                        "announcements": [],
                        "last_update": datetime.now(UTC).isoformat(),
                        "board_id": board_id,
                        "error": "Ошибка загрузки данных",
                    },
                }
                await websocket.send_text(json.dumps(empty_state, ensure_ascii=False))
            except Exception:
                pass

    def _resolve_name_format(self, board_ids: list[str] | None) -> str:
        """Строгий формат имён среди целевых табло (PHI: none ⊂ initials ⊂ full).

        DISPLAYPRIVACY-BE-002 (audit PR #3961): fail-closed masking. Любая
        неудача резолва политики приватности — ошибка БД/сессии, неизвестное
        табло (нет строки), невалидное сохранённое значение, отсутствие
        целевых табло — резолвится в ``'none'`` (маскировать имя), НИКОГДА не
        деградирует в ``'initials'``/``'full'``. Результаты неудач НЕ
        кэшируются: временный сбой не должен маскировать (или раскрывать)
        табло навсегда; кэшируются только реальные строки с валидными
        значениями (обновление кэша — после рестарта).
        """
        formats: list[str] = []
        try:
            ids = board_ids if board_ids else list(self.connections.keys())
            if not ids:
                # Fail-closed: нет целевых табло — маскируем (было 'initials').
                return "none"
            cache = getattr(self, "_name_format_cache", None)
            if cache is None:
                # Минимальные инстансы (тесты строят менеджер через
                # __new__ в обход __init__) — кэш инициализируется лениво.
                cache = {}
                self._name_format_cache = cache
            db = SessionLocal()
            try:
                for b in ids:
                    cached = cache.get(b)
                    if cached is None:
                        row = (
                            db.query(DisplayBoard)
                            .filter(DisplayBoard.name == b)
                            .first()
                        )
                        if row is not None and row.show_patient_names in (
                            "full",
                            "initials",
                            "none",
                        ):
                            cached = row.show_patient_names
                            cache[b] = cached
                        else:
                            # Fail-closed: неизвестное табло или невалидное
                            # значение маскирует имя; НЕ кэшируем — строка
                            # может появиться/стать валидной позже.
                            cached = "none"
                    formats.append(cached)
            finally:
                db.close()
        except Exception:
            # Fail-closed: любой сбой резолва (БД недоступна, минимальный
            # инстанс без соединений) маскирует имя — 'none', не 'initials'.
            # Не кэшируем: после восстановления политики резолвятся заново.
            return "none"
        if any(f == "none" for f in formats):
            return "none"
        if any(f == "initials" for f in formats):
            return "initials"
        return "full"

    # DISPLAYPRIVACY-BE-001 (audit PR #3961): control-канал инвалидации
    # кэша формата имён. Кэш per-процессен; админ-PUT и следующий
    # call/announcement POST могут попасть на разные uvicorn-воркеры,
    # поэтому локального сброса недостаточно — публикация control-сообщения
    # заставляет остальные воркеры сбросить устаревшую запись.
    NAMEFORMAT_CTL_CHANNEL = "nameformat_ctl"

    def invalidate_name_format_cache(self, board_name: str | None = None) -> None:
        """Сбросить кэш формата имён: локально — синхронно и немедленно,
        на других воркерах — best-effort control-сообщением (без ACK;
        сбой публикации только логируется). Вызывается из успешного
        админ-обновления ``DisplayBoard.show_patient_names``
        (``board_name=None`` — консервативная очистка всего кэша).
        """
        try:
            cache = getattr(self, "_name_format_cache", None)
            if isinstance(cache, dict):
                if board_name is None:
                    cache.clear()
                else:
                    cache.pop(board_name, None)
        except Exception as e:
            logger.warning(
                "DISPLAYPRIVACY-BE-001: локальная инвалидация кэша формата "
                f"имён не удалась: {e}"
            )
        dispatch_async(self._publish_nameformat_invalidation(board_name))

    async def _publish_nameformat_invalidation(self, board_name: str | None) -> None:
        """Best-effort публикация control-сообщения инвалидации.

        ``publish_ephemeral``: одноразовый клиент без общего listener/lock —
        безопасно вызывается из sync-контекста админ-PUT через
        ``dispatch_async`` (в тредпуле нет running loop).
        """
        try:
            await asyncio.wait_for(
                self._pubsub.publish_ephemeral(
                    self.NAMEFORMAT_CTL_CHANNEL,
                    {
                        "type": "nameformat_invalidate",
                        "board_name": board_name,
                        "source_ts": datetime.now(UTC).isoformat(),
                    },
                ),
                timeout=3.0,
            )
        except Exception as e:
            logger.warning(
                "DISPLAYPRIVACY-BE-001: control-publish инвалидации формата "
                f"имён не удался (best-effort): {e}"
            )

    async def _ensure_nameformat_ctl_subscription(self) -> None:
        """Подписать этот воркер на control-канал инвалидации (идемпотентно).

        Вызывается до первого резолва политики на каждом пути
        (connect / broadcast_to_board): воркер с кэш-записями обязан быть
        подписан, иначе control-сообщение будет пропущено и устаревший
        ``full`` доживёт до рестарта.

        Follow-up #4035 (P1-остаток ревью): неудавшаяся подписка НЕ кэширует
        успех и явно отменяет регистрацию обработчика в мосте (мост мог
        добавить обработчик до проверки готовности Redis и не откатить её
        сам). Иначе повтор с тем же обработчиком видит ``was_added=False``,
        пропускает реальный Redis SUBSCRIBE и возвращает ``True`` — воркер
        навсегда кэширует ``_nameformat_ctl_ok=True`` без реальной подписки
        и после даунгрейда ``full→none`` продолжает показывать полные имена.
        """
        if getattr(self, "_nameformat_ctl_ok", False):
            return
        handler = getattr(self, "_nameformat_ctl_handler", None)
        if handler is None:
            handler = self._handle_nameformat_ctl
            self._nameformat_ctl_handler = handler
        try:
            ok = bool(
                await self._pubsub.subscribe(self.NAMEFORMAT_CTL_CHANNEL, handler)
            )
        except Exception as e:
            logger.error(
                "DISPLAYPRIVACY-BE-001: подписка control-канала формата "
                f"имён не удалась: {e}"
            )
            ok = False
        if not ok:
            # Откат bridge-level регистрации (если мост не сделал это сам):
            # без него повторная попытка того же обработчика — ложный успех.
            try:
                await self._pubsub.unsubscribe(self.NAMEFORMAT_CTL_CHANNEL, handler)
            except Exception:
                pass
        self._nameformat_ctl_ok = ok

    async def _handle_nameformat_ctl(self, payload: dict) -> None:
        """Обработчик control-сообщений инвалидации кэша формата имён."""
        try:
            if (
                not isinstance(payload, dict)
                or payload.get("type") != "nameformat_invalidate"
            ):
                return
            cache = getattr(self, "_name_format_cache", None)
            if not isinstance(cache, dict):
                return
            name = payload.get("board_name")
            if name is None:
                cache.clear()
            else:
                cache.pop(name, None)
            logger.info(
                "DISPLAYPRIVACY-BE-001: кэш формата имён инвалидирован по "
                f"control-сообщению (board={name or '*'})"
            )
        except Exception as e:
            logger.error(
                "DISPLAYPRIVACY-BE-001: обработка control-сообщения формата "
                f"имён не удалась: {e}"
            )

    def _format_patient_name(
        self, full_name: str, format_type: str = "initials"
    ) -> str:
        """Форматирование имени пациента для табло"""
        if not full_name:
            return "Пациент"

        try:
            if format_type == "full":
                return full_name
            elif format_type == "initials":
                parts = full_name.split()
                if len(parts) >= 2:
                    return f"{parts[0]} {parts[1][0]}."
                if parts:
                    # DISPLAYNAME-BE-001 (audit PR #3961): однотоковое имя
                    # не раскрывается дословно — маска первой буквой.
                    return f"{parts[0][:1]}."
                return "Пациент"
            elif format_type == "none":
                return "Пациент"
            else:
                return full_name

        except Exception:
            return "Пациент"

    def get_board_connections_count(self, board_id: str) -> int:
        """Получить количество подключений к табло"""
        return len(self.connections.get(board_id, set()))

    def get_all_boards_status(self) -> dict[str, dict[str, Any]]:
        """Статус табло с живыми ЛОКАЛЬНЫМИ соединениями этого воркера.

        DISPLAYSTATUS-BE-001 (audit PR #3961): в multi-Uvicorn-топологии
        это только соединения ЭТОГО процесса — отсутствие табло здесь не
        означает «офлайн системно»: реальный TV может быть подключён к
        другому воркеру. Эндпоинт обязан помечать такой статус как
        неопределённый (online_scope=worker_local).
        """
        status = {}
        for board_id, connections in self.connections.items():
            status[board_id] = {
                "connections": len(connections),
                "last_update": self.board_states.get(board_id, {}).get("last_update"),
                "active": len(connections) > 0,
            }
        return status

    async def broadcast_queue_update(self, queue_entry, event_type: str) -> None:
        """Трансляция обновления очереди"""
        try:
            if event_type != "queue.created":
                if queue_entry.queue:
                    await self.broadcast_daily_queue_state(
                        queue_entry.queue,
                        event_type=event_type,
                    )
                    return

            # RQ-24.a.1: формат имён по show_patient_names целевых табло
            name_format = self._resolve_name_format(None)
            message = {
                "type": "queue_update",
                "event_type": event_type,
                "data": {
                    "queue_entry_id": queue_entry.id,
                    "number": queue_entry.number,
                    "patient_name": self._format_patient_name(
                        queue_entry.patient_name, name_format
                    ),
                    "status": queue_entry.status,
                    "source": queue_entry.source,
                    "created_at": (
                        queue_entry.created_at.isoformat()
                        if queue_entry.created_at
                        else None
                    ),
                    "called_at": (
                        queue_entry.called_at.isoformat()
                        if queue_entry.called_at
                        else None
                    ),
                    "specialist_id": queue_entry.queue.specialist_id,
                    "department": f"specialist_{queue_entry.queue.specialist_id}",
                    "queue_id": queue_entry.queue.id,
                },
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Отправляем на все табло
            for board_id in self.connections.keys():
                await self.broadcast_to_board(board_id, message)

            logger.info(
                f"Трансляция обновления очереди: {event_type} для пациента №{queue_entry.number}"
            )

        except Exception as e:
            logger.error(f"Ошибка трансляции обновления очереди: {e}")

    async def broadcast_queue_event(
        self, department: str, event_type: str, data: dict[str, Any]
    ) -> None:
        """
        Отправляет события очереди всем подключенным табло отделения

        Args:
            department: Отделение (cardiology, dermatology, etc.)
            event_type: Тип события (queue.created, queue.called, queue.completed, queue.cancelled)
            data: Данные события
        """
        board_id = f"dept_{department}"

        message = {
            "type": "queue_event",
            "event": event_type,
            "department": department,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data,
        }

        await self.broadcast_to_board(board_id, message)
        logger.info(f"Broadcasted {event_type} event to department {department}")


display_manager = DisplayWebSocketManager()


def get_display_manager() -> DisplayWebSocketManager:
    """Получить экземпляр менеджера табло"""
    return display_manager


def dispatch_async(coro) -> None:
    """
    Safely dispatch an async coroutine from sync or async contexts.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:
        loop.create_task(coro)
