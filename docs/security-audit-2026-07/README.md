# Security Audit — июль 2026

Полный отчёт аудита безопасности подсистем обмена сообщениями в системе управления
медицинской клиникой `drsapaev/final`.

## Содержимое

| Файл | Описание | Страниц | Размер |
|------|----------|---------|--------|
| `audit_chat_security.pdf` | Основной отчёт аудита пользовательского in-app чата (18 находок) | 44 | 387 КБ |
| `audit_ai_chat_appendix.pdf` | Приложение: аудит AI-чата (AI Gateway, провайдеры, PII) — 12 находок | 26 | 311 КБ |
| `patches/` | Готовые код-патчи для устранения Волны 1 (6 файлов) | — | ~46 КБ |
| `patches/README.md` | Инструкция по применению патчей | — | 9 КБ |

## Сводка по находкам

### Пользовательский чат (основной отчёт)

18 находок: **2 Critical**, **4 High**, **6 Medium**, **6 Low**.

| ID | Серьёзность | Название |
|----|-------------|----------|
| F-001 | Critical | JWT-токен в URL Query String WebSocket |
| F-002 | Critical | Отсутствие tenant-изоляции таблицы messages |
| F-003 | High | Неполная валидация голосовых файлов (только расширение) |
| F-004 | High | Слабая авторизация доступа к файлам через Message.content.contains() |
| F-005 | High | Отсутствие rate-limiting на WS-событиях и REST чата |
| F-006 | High | Спуфинг typing-индикатора и утечка online-статуса |
| F-007..F-012 | Medium | Audit-log silent failure, PII в previews, нет шифрования at-rest, Markdown без sanitize, DNS rebinding, fire-and-forget asyncio |
| F-013..F-018 | Low | N+1 в conversations, in-memory state, предсказуемые имена файлов, нет CSP, retention, bare except |

### AI-чат (приложение)

12 находок: **1 Critical**, **4 High**, **5 Medium**, **2 Low**.

| ID | Серьёзность | Название |
|----|-------------|----------|
| FA-001 | Critical | JWT-токен в URL WebSocket AI-чата (дублирует F-001) |
| FA-002 | High | Prompt injection через user content в system_prompt |
| FA-003 | High | AI-ответы не валидируются перед отображением (XSS риск) |
| FA-004 | High | Cache не изолирован по tenant (cross-user cache hit) |
| FA-005 | High | Раскрытие деталей ошибок внешних LLM-провайдеров |
| FA-006..FA-010 | Medium | PII Anonymizer неполный, аудит без payload, streaming rate limit, общий cache TTL, нет watermarking |
| FA-011..FA-012 | Low | API keys без KMS, in-memory circuit breaker |

**Всего: 30 находок**, 3 Critical, 8 High, 11 Medium, 8 Low.

## Суммарные трудозатраты на remediation

- Основной отчёт: 43.5 чел-дней
- AI-чат: 30.5 чел-дней
- **Итого: 74 чел-дня** (3 волны: 1-2 недели / 1 месяц / 1 квартал)

## Порядок ознакомления

1. Прочитать `audit_chat_security.pdf` (44 страницы)
2. Прочитать приложение `audit_ai_chat_appendix.pdf` (26 страниц)
3. Перейти в `patches/` — там 6 готовых патчей для Волны 1
4. Следовать инструкции в `patches/README.md` для применения

## Готовые патчи Волны 1

Каталог `patches/` содержит готовый код для устранения 6 высокоприоритетных находок:

| ID  | Файл                                         | Серьёзность |
|-----|----------------------------------------------|-------------|
| F-001 | `patch_F001_jwt_in_url.py`                 | Critical    |
| F-002 | `patch_F002_tenant_isolation.py`           | Critical    |
| F-003 | `patch_F003_audio_magic_bytes.py`          | High        |
| F-004 | `patch_F004_file_auth.py`                  | High        |
| F-005 | `patch_F005_rate_limiting.py`              | High        |
| F-006 | `patch_F006_typing_online_auth.py`         | High        |

Каждый патч — самостоятельный Python-файл с подробными комментариями, кодом
новой версии изменяемых функций и инструкциями по применению. См. `patches/README.md`
для пошагового плана применения (зависимости, порядок, миграции, тесты, риски).

## Стандарты аудита

- OWASP Application Security Verification Standard (ASVS) v4.0
- OWASP Top 10 (2021)
- OWASP Top 10 for LLM Applications (для AI-чата)
- NIST AI RMF (для AI-чата)
- HIPAA Security Rule (45 CFR §164.302-318)
- GDPR (Regulation (EU) 2016/679)
- RFC 6455 (WebSocket Protocol)
- RFC 7519 (JSON Web Token)
- CVSS v3.1 для оценки серьёзности

## Метаданные аудита

- **Дата проведения:** 6 июля 2026 г.
- **Метод:** white-box code review (статический анализ)
- **Объём:** 18 файлов пользовательского чата + 10 файлов AI-чата (~6500 строк кода)
- **Аудитор:** Z.ai Security Audit
- **Конфиденциальность:** Internal Use
