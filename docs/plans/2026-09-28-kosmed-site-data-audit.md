# Аудит данных для публичного сайта Doktor KosMed Clinic

> **Статус:** инвентаризация для обсуждения; результат шага 1 раздела 7 плана ([план сайта](2026-09-28-kosmed-public-site-plan.md)).
> **Дата:** 2026-09-28. **Метод:** read-only проход по backend-моделям и endpoint'ам (база — main `3b5b87007`), выборочная верификация ключевых утверждений по исходникам. Пути — от корня репозитория; `:NN` — номера строк.
> **Актуализация 2026-10-06:** проверены изменения до `origin/main` `d75108c11`; PR-0a #3616 и PR-0b #3621 уже merged. Исправлены владельцы настроек, статус безопасности и описание OTP. Перед реализацией читать [заметку передачи работы](2026-10-06-kosmed-public-site-handoff.md); старые номера строк перепроверять по текущим исходникам. Это статическая проверка, не доказательство развёртывания.
> **Актуализация 2026-10-08:** базовая точка обновлена до `origin/main` `759869284`; PR #3625 merged и закрыл расхождение ключей настроек клиники (раздел 1). Публичное чтение сайта, публикация каталога и отображение состояния очереди этим PR не добавлены. Это статическая проверка, не доказательство развёртывания.
> **Уточнение плана 2026-10-08:** на базе `c790a3598` владельцы Service/Doctor/ServiceCategory и действующих Admin DTO сверены повторно; выбранные правила публикации, стабильных slug и локалей подробно внесены в [раздел 11 плана](2026-09-28-kosmed-public-site-plan.md#11-подробные-требования-к-публикации-адресам-и-этапам-2a4). Они описывают будущую реализацию; найденные недостающие поля этим документом не добавлены.
> **Актуализация 2026-10-09:** `origin/main` — `7f30b231d`; PR #3636/#3637 уже включены (поля контента и админская публикация услуг/врачей). Таблицы разделов 2, 3 и 8 сохраняют первоначальные наблюдения как исторический снимок; для текущих полей источником истины являются модели, Admin DTO и handoff. Этап 3 публичного чтения реализуется в отдельной ветке и ещё не merged.
> **Решения владельца 2026-10-09:** для публичной цены использовать только `Service.price` + `Service.currency`; если суммы или валюты нет, показывать цену по запросу. Не публиковать `Doctor.cabinet`; услугу без пригодной категории оставлять в выдаче с пустой категорией; врача с отсутствующей/непереведённой специальностью оставлять без подписи специальности, не раскрывая код. Реализация публичного read API этапа 3 находится в отдельной рабочей ветке и ещё не входит в `main`.

## Сводка

| Область | Где редактируется сегодня | Публично доступно сегодня | Критичный разрыв для сайта |
|---|---|---|---|
| Настройки клиники | KV-таблица `clinic_settings` через закрытый `/admin/clinic/settings` | ничего (кроме `/setup/status` → `{initialized}`) | нет публичного чтения; загруженный логотип не раздаётся сервером; часть контактных данных захардкожена |
| Услуги и цены | `Service` через Admin-эндпоинты `/services` | `GET /api/v1/services` открыт, но отдаёт внутренние поля | нет флага публикации, описания, перевода, картинки; правила «какая цена публичная» не определены |
| Врачи | `Doctor` через Admin `/admin/doctors` | `/queue/available-specialists` (QR-формат); `/services/admin/doctors` теперь требует Admin (#3616) | нет био/фото/slug/флага публикации/переводов; имя живёт в `User.full_name` |
| Расписание и лимиты | `Schedule` (недельный шаблон), `DailyQueue` (на день), `ClinicSettings` category `queue` | нет отдельного анонимного API слотов для сайта | нет контракта настроек канала записи на будущие даты; дневные лимиты QR-очереди его не заменяют |
| Запись на приём | `Appointment` через web/mobile/portal — авторизованы | нет (QR-join создаёт талоны очереди); отдельный patient-access OTP уже есть | `patient_id NOT NULL` — нужен явный сценарий идентификации; guest booking и его защита/режим пока не спроектированы |
| Языки | фронтовый i18n (localStorage), колонки `*_ru/_uz` на Department/ServiceCategory/MedicalSpecialty | — | `Service` и `Doctor` не имеют колонок локалей; нет URL-локалей и SEO-слоя |

## 1. Настройки клиники (контакты, логотип)

- Хранилище — универсальное KV: `ClinicSettings` (`key`/`value` JSON/`category`), backend/app/models/clinic.py:38-63. Ключи клиники создаёт first-run wizard: `clinic_name`, `clinic_address`, `clinic_phone`, `clinic_email`, `clinic_timezone`, `clinic_logo_url` — backend/app/services/setup_service.py:21-29. Рабочих часов, координат карты, соцсетей и юридического названия в ключах нет.
- **Расхождение ключей (риск SSOT) закрыто PR #3625:** экран админки использует ключи `clinic_*`; миграция [0078](../../backend/alembic/versions/0078_clinic_settings_keys.py) переносит legacy-значения на канонические строки, ничего не удаляя; backend нормализует записи от старых клиентов. См. [тесты каноникализации](../../backend/tests/integration/test_clinic_settings_key_canonicalization.py). До публичного чтения всё ещё нужно определить разрешённые поля и источник актуальных контактов.
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
- Публичный `GET /queue/available-specialists` относится к QR-флоу (id, specialty, имя врача, кабинет — qr_queue/_specialists.py). `GET /services/admin/doctors` на исходную дату аудита был открытым; с PR #3616 требует `Admin` (services_ep/_services.py). Публичная карточка визита `/visits/info/{token}` отдаёт `doctor_name` по токену (visit_confirmation.py).

## 4. Лимиты и настройки записи

- Настройки `/admin/queue/settings` хранятся в `ClinicSettings` / таблице `clinic_settings` (category `queue`, JSON-значения): `get_settings_by_category` и `update_queue_settings` в crud/clinic.py. UI — QueueSettings.tsx → GET/PUT `/admin/queue/settings` (Admin, admin_clinic.py). Отдельная модель `Setting` / таблица `settings` существует, но не является владельцем этого CRUD.
- Все существующие лимиты управляют **только текущим днём QR-очереди**; отдельных настроек для записи на будущие даты (часы записи, горизонт, канал) нет. Параллельная механика на день: `OnlineDay` по department+дата (services/online_queue.py:122-159, ключи `queue::{dep}::{date}::*`) рядом с `DailyQueue` по врачу/ресурсу — это надо учитывать при «настройках канала записи» из плана.
- Существующие `QueueSettingsUpdate` (schemas/clinic.py) и `update_queue_settings` (crud/clinic.py) разрешают ограниченный набор ключей QR-очереди. Новый `booking_mode` через текущий PUT не сохранится. Для режима записи (раздел 8 плана) до кода определить хранилище, DTO и endpoint отдельного канала или явное расширение существующего контракта; не выбирать между `Setting` и `ClinicSettings` по похожему имени.

## 5. Запись на приём

- `Appointment` (models/appointment.py:17-76): `patient_id` **NOT NULL**, `doctor_id`, `appointment_date`, `appointment_time` — строка «HH:MM», статусы pending/paid/in_visit/completed/cancelled/no_show (models/enums.py:8-29). **DB-уникальности слота нет** — защита от двойного бронирования только на уровне приложения: `SELECT … FOR UPDATE` на строку врача перед проверкой занятости (services/appointment_slot_guard.py:1-52; список писателей задокументирован там же, :26-29; верифицировано). Новый публичный писатель обязан встать в этот же порядок.
- Все эндпоинты записи требуют авторизации: web `POST /appointments` (appointments.py:446-479), портал `/patients/booking` (patient_portal.py:754-975, обязательный `Idempotency-Key` :760-771), mobile `POST /mobile/appointments/book` (mobile_api.py:401-540). Публичный QR-join создаёт только талоны очереди с самозаявленными именем/телефоном, не записи и не пациентов (qr_queue/_join.py:70-186).
- Слоты: `list_available_slots` строится из недельного Schedule с **часовой гранулярностью** (минуты и `duration_minutes` услуг игнорируются, фолбэк 9-16 кроме вс — patient_appointments_api_service.py:69-140). Запись **не проверяет вхождение времени в расписание** — принимается любое незанятое время (общее свойство всех текущих писателей).
- **Анонимный сценарий требует явной идентификации пациента:** `patient_id` обязателен. Подтверждение телефона не определяет единственную карточку: services/patient_phone_scope.py допускает семейные номера. patient_otp_service.py использует уже установленную связь `Patient.user_id`, не выбирает произвольную карту по телефону. Согласовать сценарии нового/существующего пациента и родственника; не использовать `.first()` по номеру как готовый matching.
- В подключённом `/patient-access` уже есть OTP, ограничения по IP/телефону, защита от перечисления аккаунтов и одноразовые grants (endpoints/patient_access.py, services/patient_otp_service.py). Для guest booking выполнить gap-анализ и переиспользовать пригодные компоненты с отдельным назначением grant. Пользовательский idempotency-кеш `(user_id, key)` (middleware/idempotency_middleware.py) не является готовым анонимным решением; область ключа, хранение результата и конкурентный повтор требуют контракта.
- **Режим заявки ещё не определён:** `AppointmentStatus.PENDING` — ожидание оплаты, а `is_time_slot_occupied` в crud/appointment.py учитывает записи кроме отменённых. Заявка с врачом/датой/временем в Appointment занимает слот по текущему правилу. До реализации согласовать хранение заявки, резервирование, работу регистратора и переход к подтверждённой брони; не подменять это статусом оплаты.
- `website_appointments` / site_leads / callback_requests — не существуют (поиск по моделям и миграциям пуст), что соответствует запрету плана.

## 6. Языки (контекст для раздела 9 плана)

- Фронт: 5 локалей `ru, uz-Latn, uz-Cyrl, en, kk`, DEFAULT и fallback — `ru` (frontend/src/i18n/index.ts:28-29); `uz-Latn.ts` автогенерируется из ru скриптом scripts/i18n/generate_locales.py; язык живёт только в localStorage (index.ts:35-46) — URL-локалей, Accept-Language-детекции, hreflang, robots.txt/sitemap нет; `<html lang="en">` захардкожен (index.html:2). У лендинга есть собственные ru+uz-тексты (pages/landingContent.ts:1,692) — параллельная система.
- Backend-колонки локалей есть у Department (name_ru/name_uz, models/department.py:56-59), ServiceCategory (ru/uz/en, clinic.py:149-151), MedicalSpecialty (ru/uz/en); у `Service`, `Doctor`, ClinicSettings — нет. Для узбекского по умолчанию публичные read-model'ы должны отдавать оба варианта, а админка — позволять их редактировать.

## 7. Сопутствующие находки безопасности и текущий статус

1. `GET /api/v1/services/admin/doctors` был открыт на исходную дату аудита; исправлен в [#3616](https://github.com/drsapaev/final/pull/3616), merged. Теперь требует `Admin` (services_ep/_services.py; tests/integration/test_services_audit_endpoints_auth.py).
2. `GET /api/v1/services/{id}/history` и `GET /services/admin/audit/recent` были открыты; тот же #3616 закрыл их ролью `Admin`. Не повторять исправление по старым номерам строк.
3. `GET /services/queue-groups`, `GET /services/code-mappings` — открыты, отдают служебные маппинги очередей/маршрутизации.
4. Перенос записи мог занять чужой слот. **Статус 2026-10-06:** [PR-0b #3621](https://github.com/drsapaev/final/pull/3621) merged в `d75108c11`; живой `POST /mobile/appointments/reschedule` (mobile_api_extended.py) берёт блокировку врача и проверяет занятость перед CRUD, исключая переносимую запись. Focused tests — tests/integration/test_mobile_reschedule_slot_occupancy.py. Исходный TODO в patient_appointments.py указывал на неподключённый legacy; его удаление — отдельный cleanup. Merged не означает deployed.
5. Открытый `GET /services` отдаёт неактивные услуги и внутренние флаги (см. §2).

## 8. Исторический список недостающих публичных полей

Таблица ниже отражает исходный gap-анализ. Поля публикации, переводы, био, slug и timestamp первой публикации добавлены этапом 2a; операции управления ими добавлены этапом 2b и уже находятся в `main`. Строки о медиа и настройках клиники остаются предметом последующих решений.

| Сущность | Поле | Назначение | Как вводится |
|---|---|---|---|
| Service | флаг публикации (show_on_website) | видимость на сайте независимо от `active` | Alembic + админка |
| Service | name_uz, description_ru/uz | тексты услуги для пациента | Alembic + админка |
| Service | slug, website_first_published_at | стабильный ключ /services/:slug; фиксация после первой публикации | Alembic в 2a, операция публикации в 2b |
| Service | изображение | карточка услуги | Alembic + решение по медиа |
| ServiceCategory | открыть публичное чтение по активным категориям с доступными услугами | меню каталога; без нового флага публикации | публичный endpoint в 3 |
| Doctor | флаг публикации | показывать врача на сайте | Alembic + админка |
| Doctor | bio_ru/bio_uz в Doctor | проверенные тексты профиля; общий UserProfile не является публичным источником | Alembic в 2a + админка в 2b |
| Doctor | фото (связка с UserProfile.avatar_url или своё) | профиль врача | существующее поле + upload/раздача |
| Doctor | slug, website_first_published_at | стабильный ключ /doctors/:slug; фиксация после первой публикации | Alembic в 2a, операция публикации в 2b |
| ClinicSettings | рабочие часы уровня клиники, координаты/ссылка на карту, соцсети/telegram, переводы имени и адреса | страница контактов | KV-ключи (+ возможно Branch) |
| Настройки канала записи (владелец уточняется) | режим instant/request, доступность записи, допущенные услуги/врачи | раздел 8 плана | типизированный контракт в существующем backend; текущий `/admin/queue/settings` новые ключи не сохраняет |
| Инфраструктура | раздача медиа: `/static` не смонтирован ни в backend, ни в nginx | логотип, фото врачей | отдельное решение |

## 9. Открытые вопросы (согласуются до зависящей реализации)

Решения по цене, кабинету, недоступной категории и неполному справочнику специальностей приняты владельцем 2026-10-09 и записаны в разделе 11.7 плана. Открыты следующие вопросы:

1. Хранение и раздача медиа (логотип, фото врачей): backend static mount + nginx или внешнее хранилище.
2. Gap-анализ существующего OTP, назначение booking grant, защита анонимной записи и guest idempotency; сценарии нового/существующего пациента и родственника при семейном номере.
3. Представление и состояния заявки регистратору, резервирование слота, срок и переход к подтверждённой записи; точный контракт настроек канала.
4. Выдача содержимого и метаданных в HTML, механизм и срок обновления из админки, поведение при сбое обновления.
5. Правила расписания, длительности, перерывов и горизонта публичной записи.

Публикация скрыта по умолчанию; видимость категории производна от её активности, переводов и доступных услуг. Slug выбран публичным ключом с фиксацией после первой публикации; пространства услуг/врачей разделены. Узбекские страницы находятся в корне, русские — под `/ru/`. Решения по публичной цене, кабинету, категории и неполному переводу специальности приняты 2026-10-09 и отражены в разделе 11 плана. Текущий этап 3 добавляет отдельный read-only контракт в своей рабочей ветке; проверяйте его статус по Git/заметке передачи.

Согласовать оставшиеся вопросы до затрагивающей их реализации; отметка «вопрос владельцу» в PR не является решением. Текущая реализация этапа 3 — в рабочей ветке, её статус подтверждать по [актуальной заметке](2026-10-06-kosmed-public-site-handoff.md) и Git.
