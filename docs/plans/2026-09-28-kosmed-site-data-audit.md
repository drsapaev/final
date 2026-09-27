# Аудит данных для публичного сайта Doktor KosMed Clinic

> **Статус:** черновик для обсуждения; результат шага 1 раздела 7 плана ([план сайта](2026-09-28-kosmed-public-site-plan.md)).
> **Дата:** 2026-09-28. **Метод:** read-only проход по backend-моделям и endpoint'ам (база — main `3b5b87007`), выборочная верификация ключевых утверждений по исходникам. Пути — от корня репозитория; `:NN` — номера строк.

## Сводка

| Область | Где редактируется сегодня | Публично доступно сегодня | Критичный разрыв для сайта |
|---|---|---|---|
| Настройки клиники | KV-таблица `clinic_settings` через закрытый `/admin/clinic/settings` | ничего (кроме `/setup/status` → `{initialized}`) | нет публичного чтения; ключи настроек расходятся между wizard и админкой; загруженный логотип не раздаётся сервером |
| Услуги и цены | `Service` через Admin-эндпоинты `/services` | `GET /api/v1/services` открыт, но отдаёт внутренние поля | нет флага публикации, описания, перевода, картинки; правила «какая цена публичная» не определены |
| Врачи | `Doctor` через Admin `/admin/doctors` | `/queue/available-specialists` (QR-формат), `/services/admin/doctors` (без имён) | нет био/фото/slug/флага публикации/переводов; имя живёт в `User.full_name` |
| Расписание и лимиты | `Schedule` (недельный шаблон), `DailyQueue` (на день), `Setting` category `queue` | нет | нет настроек и лимитов для записи на будущие даты; вся доступность требует авторизации персонала |
| Запись на приём | `Appointment` через web/mobile/portal — все авторизованы | нет (QR-join создаёт только талоны очереди, не записи) | `patient_id NOT NULL` — нет матчинга анонимного пациента; анти-абьюза нет вовсе; нет настройки режима записи |
| Языки | фронтовый i18n (localStorage), колонки `*_ru/_uz` на Department/ServiceCategory/MedicalSpecialty | — | `Service` и `Doctor` не имеют колонок локалей; нет URL-локалей и SEO-слоя |

## 1. Настройки клиники (контакты, логотип)

- Хранилище — универсальное KV: `ClinicSettings` (`key`/`value` JSON/`category`), backend/app/models/clinic.py:38-63. Ключи клиники создаёт first-run wizard: `clinic_name`, `clinic_address`, `clinic_phone`, `clinic_email`, `clinic_timezone`, `clinic_logo_url` — backend/app/services/setup_service.py:21-29. Рабочих часов, координат карты, соцсетей и юридического названия в ключах нет.
- **Расхождение ключей (риск SSOT):** экран админки ClinicSettings.tsx:49-56, 302-369 пишет другие ключи — `address`, `phone`, `email`, `timezone`, `logo_url` (без префикса `clinic_`). Одни и те же данные живут под двумя написаниями; до публичного чтения их надо сверстить.
- Единственные структурированные контакты/часы — `Branch`: `address`, `phone`, `email`, `working_hours` JSON `{"monday": {"start","end"}}` — backend/app/models/clinic.py:174-211; редактируется только через закрытые `/clinic/branches` (require_admin, clinic_management.py:55-155).
- Админ-поверхность: чтение `GET /admin/clinic/settings` — `get_current_active_user`, запись — `require_roles("Admin")` — backend/app/api/v1/endpoints/admin_clinic.py:47-136 (подтверждает тезис плана: настройки закрыты авторизацией).
- **Логотип не раздаётся:** `POST /admin/clinic/logo` сохраняет файл в относительный `static/uploads/clinic/…` (admin_clinic.py:176-223), но ни backend (`main.py`), ни шаблон nginx (`ops/vps/nginx/clinic.conf.template:10-54`) не монтируют `/static` — возвращаемый `logo_url` сегодня мёртв. Для сайта нужно решение по хранению/раздаче медиа.
- Контакты, захардкоженные в коде (источники дрейфа): `mobile_api_extended.py:874-907` (имя, адрес, телефон, email, часы, даже координаты 41.2995/69.2401), `mobile_api.py:327,533`, `telegram_notifications.py:103,310`, `print_api.py:339` и др. Перед публичным чтением их стоит свести к настройкам.

## 2. Услуги и цены

- `Service` (backend/app/models/service.py:17): `name` String(256) — один столбец без локалей, `price` Numeric(12,2) nullable + `currency` (по умолчанию UZS, :30-33), `duration_minutes` (:58), `active` (:34), `category_id`, `department_id`, `doctor_id`, и служебные: `category_code`, `service_code`, `queue_tag`, `requires_doctor`, `allow_doctor_price_override`, `department_key`. Описания, картинки, slug и флага публикации нет.
- Цены: основная — `Service.price`; дефолт врача — `Doctor.price_default` (clinic.py:90); подтверждённые overrides — `DoctorPriceOverride` (models/doctor_price_override.py:19, статусы pending/approved/rejected); фактические начисления — `VisitService.price`. Правило «какая цена видна пациенту» нигде не зафиксировано; `price` nullable → нужен статус «цена по запросу».
- **Открытый `GET /api/v1/services`** (auth закомментирован — services_ep/_services.py:13-41): ответ `ServiceOut` (services_ep/_helpers.py:60-81, сборка :283-310) содержит пациент-значимые `name`, `price`, `currency`, `duration_minutes`, `unit` и внутренние `queue_tag`, `department_key`, `category_code`, `service_code`, `requires_doctor`, `allow_doctor_price_override`, `department`, `doctor_id`, `category_id`, `active`; отдаёт и неактивные строки. Публичный read-model должен быть отдельной проекцией, не этим схемом.
- Категории, наоборот, закрыты: `GET /services/categories` требует роли персонала (services_ep/_categories.py:9-21), хотя имена категорий триязычные (`name_ru/name_uz/name_en`, clinic.py:149-151).
- `specialty_data` — это JSONB внутри клинических EMR-записей v2 (models/emr_v2.py:69-73, schemas/emr_v2.py:57-60), редактируется только врачами через EMR (emr_v2.py:387-570). К каталогу услуг отношения не имеет; на сайт не попадает.
- Редактирование: POST/PUT/DELETE `/services` — Admin (_services.py:241-296), категории — Admin (_categories.py:24-78), динамические цены — Admin (dynamic_pricing.py:186-409).

## 3. Врачи

- `Doctor` (clinic.py:66-115): `user_id` UNIQUE 1:1, `department_id`, `specialty` — свободный код-строка, резолвится в `MedicalSpecialty.title_ru/title_uz/title_en` (models/medical_specialty.py:27-41), `cabinet`, `price_default`, `active`, лимиты онлайна (`start_number_online`, `max_online_per_day`, `auto_close_time`). Отображаемое имя — `User.full_name` (models/user.py:39).
- Публичных полей профиля нет: био/аватар существуют только на уровне `UserProfile` (`avatar_url` :80, `bio` :81, плюс `website` :82 и `social_links` :83 — backend/app/models/user_profile.py:79-85), с врачами не связаны; slug и флага публикации нет нигде.
- Админ-CRUD: `/admin/doctors` (список/создание/правка/деактивация/расписание) — все `require_roles("Admin")` (admin_doctors.py:156-886). Редактируемые поля: `user_id, specialty, cabinet, price_default, лимиты, active` (schemas/clinic.py:82-109) — имени/био/фото в форме врача нет.
- Расписание: `Schedule` — недельный шаблон (weekday 0-6, start/end, `breaks` JSON), clinic.py:118-139; исключений на даты/праздников нет. Потребители доступности — crud/clinic.py:950-1010 и patient_appointments_api_service.py:77-127. Очередь `DailyQueue` из Schedule не выводится — несёт свои `online_start_time/online_end_time/max_online_entries` (models/online_queue.py:131-199).
- Уже открыто без авторизации: `GET /queue/available-specialists` (QR-флоу: id, specialty, имя врача, кабинет — qr_queue/_specialists.py:9-129) и `GET /services/admin/doctors` (без имён; путь `/admin`, авторизации нет — _services.py:311-323, верифицировано). Публичная карточка визита `/visits/info/{token}` отдаёт `doctor_name` по токену (visit_confirmation.py:143-167).

## 4. Лимиты и настройки записи

- Настройки очереди хранятся в `Setting` (category `queue`: `timezone`, `queue_start_hour`, `auto_close_time`, `start_number_{specialty}`, `max_per_day_{specialty}`) — crud/clinic.py:469-548; UI — QueueSettings.tsx → GET/PUT `/admin/queue/settings` (Admin, admin_clinic.py:229-258).
- Все существующие лимиты управляют **только текущим днём QR-очереди**; отдельных настроек для записи на будущие даты (часы записи, горизонт, канал) нет. Параллельная механика на день: `OnlineDay` по department+дата (services/online_queue.py:122-159, ключи `queue::{dep}::{date}::*`) рядом с `DailyQueue` по врачу/ресурсу — это надо учитывать при «настройках канала записи» из плана.
- Настройка режима записи (подтверждение сразу / заявка регистратору — раздел 8 плана) естественно ложится в тот же `Setting`-механизм (категория `queue` или `clinic`) с редактированием через существующий `PUT /admin/queue/settings`; feature-flag-фреймворка в проекте нет.

## 5. Запись на приём

- `Appointment` (models/appointment.py:17-76): `patient_id` **NOT NULL**, `doctor_id`, `appointment_date`, `appointment_time` — строка «HH:MM», статусы pending/paid/in_visit/completed/cancelled/no_show (models/enums.py:8-29). **DB-уникальности слота нет** — защита от двойного бронирования только на уровне приложения: `SELECT … FOR UPDATE` на строку врача перед проверкой занятости (services/appointment_slot_guard.py:1-52; список писателей задокументирован там же, :26-29; верифицировано). Новый публичный писатель обязан встать в этот же порядок.
- Все эндпоинты записи требуют авторизации: web `POST /appointments` (appointments.py:446-479), портал `/patients/booking` (patient_portal.py:754-975, обязательный `Idempotency-Key` :760-771), mobile `POST /mobile/appointments/book` (mobile_api.py:401-540). Публичный QR-join создаёт только талоны очереди с самозаявленными именем/телефоном, не записи и не пациентов (qr_queue/_join.py:70-186).
- Слоты: `list_available_slots` строится из недельного Schedule с **часовой гранулярностью** (минуты и `duration_minutes` услуг игнорируются, фолбэк 9-16 кроме вс — patient_appointments_api_service.py:69-140). Запись **не проверяет вхождение времени в расписание** — принимается любое незанятое время (общее свойство всех текущих писателей).
- **Анонимный сценарий потребует нового шага матчинга пациента**: `patient_id` обязателен, а существующие писатели получают его только из авторизованного пользователя. Публичная запись (в любом режиме из раздела 8) — это create-or-match пациента по телефону с явным решением о PHI/дедупликации.
- Анти-абьюз отсутствует: captcha/honeypot — ноль вхождений по backend; SlowAPI-лимиты навешаны только на login/SMS/telegram/email (main.py:244-253; email_sms_enhanced.py:340,388); idempotency-кеш ключуется `(user_id, key)` (middleware/idempotency_middleware.py:11) и для анонимов не работает — защиту повторных отправок надо проектировать заново.
- `website_appointments` / site_leads / callback_requests — не существуют (поиск по моделям и миграциям пуст), что соответствует запрету плана.

## 6. Языки (контекст для раздела 9 плана)

- Фронт: 5 локалей `ru, uz-Latn, uz-Cyrl, en, kk`, DEFAULT и fallback — `ru` (frontend/src/i18n/index.ts:28-29); `uz-Latn.ts` автогенерируется из ru скриптом scripts/i18n/generate_locales.py; язык живёт только в localStorage (index.ts:35-46) — URL-локалей, Accept-Language-детекции, hreflang, robots.txt/sitemap нет; `<html lang="en">` захардкожен (index.html:2). У лендинга есть собственные ru+uz-тексты (pages/landingContent.ts:1,692) — параллельная система.
- Backend-колонки локалей есть у Department (name_ru/name_uz, models/department.py:56-59), ServiceCategory (ru/uz/en, clinic.py:149-151), MedicalSpecialty (ru/uz/en); у `Service`, `Doctor`, ClinicSettings — нет. Для узбекского по умолчанию публичные read-model'ы должны отдавать оба варианта, а админка — позволять их редактировать.

## 7. Сопутствующие находки безопасности (вне скоупа сайта; требуют отдельного решения)

1. `GET /api/v1/services/admin/doctors` — путь `/admin`, авторизации нет (верифицировано; _services.py:311-323).
2. `GET /api/v1/services/{id}/history` и `GET /services/admin/audit/recent` — открыты без авторизации и отдают историю цен (старое/новое значение) и имена персонала (верифицировано; _services.py:349-395, 398-438).
3. `GET /services/queue-groups`, `GET /services/code-mappings` — открыты, отдают служебные маппинги очередей/маршрутизации.
4. Перенос записи пациента не проверяет занятость слота и не берёт блокировку (`# TODO: Проверить доступность слота`, patient_appointments.py:333 → patient_appointments_api_service.py:169-179).
5. Открытый `GET /services` отдаёт неактивные услуги и внутренние флаги (см. §2).

## 8. Сводный список недостающих публичных полей

| Сущность | Поле | Назначение | Как вводится |
|---|---|---|---|
| Service | флаг публикации (show_on_website) | видимость на сайте независимо от `active` | Alembic + админка |
| Service | name_uz, description_ru/uz | тексты услуги для пациента | Alembic + админка |
| Service | slug (или публичный стабильный код) | URL /services/:slug | Alembic |
| Service | изображение | карточка услуги | Alembic + решение по медиа |
| ServiceCategory | открыть публичное чтение (published-only) | меню каталога | новый публичный endpoint |
| Doctor | флаг публикации | показывать врача на сайте | Alembic + админка |
| Doctor | bio_ru/bio_uz (или привязка к UserProfile.bio) | профиль врача | Alembic + админка |
| Doctor | фото (связка с UserProfile.avatar_url или своё) | профиль врача | существующее поле + upload/раздача |
| Doctor | slug | URL /doctors/:slug | Alembic |
| ClinicSettings | reconcile ключей `clinic_*` vs `address/phone/…` | единый SSOT контактов | фиксы wizard/UI |
| ClinicSettings | рабочие часы уровня клиники, координаты/ссылка на карту, соцсети/telegram, переводы имени и адреса | страница контактов | KV-ключи (+ возможно Branch) |
| Setting (queue/clinic) | ключ режима записи instant/request, доступность записи, допущенные услуги/врачи | раздел 8 плана | KV через существующий `/admin/queue/settings` |
| Инфраструктура | раздача медиа: `/static` не смонтирован ни в backend, ни в nginx | логотип, фото врачей | отдельное решение |

## 9. Открытые вопросы (решаются до/во время Этапа 1)

1. Публичная цена: показывать `Service.price` как есть? Статус «цена по запросу» для nullable? Учитывать ли `Doctor.price_default`/overrides в отображении?
2. Показывать ли кабинет врача на публичном профиле (поле существует, но операционное)?
3. Финальная схема URL при узбекском по умолчанию (раздел 9 плана: корень = uz с `/ru/…` или корень = ru с редиректом).
4. Хранение и раздача медиа (логотип, фото врачей): backend static mount + nginx или внешнее хранилище.
5. Выбор механизмов анти-абьюза для анонимной записи (rate limit, honeypot/captcha, идемпотентность без user_id) и правила матчинга/создания пациента по телефону (PHI!).
