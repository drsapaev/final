# Performance Checklist (EMR v2)

Используется как обязательный чеклист в PR для экранов EMR v2 и смежных компонентов.

## Обязательные пункты

- [ ] Не использую `localStorage` и локальные TTL для кэша внутри компонентов.
- [ ] Debounce применяется только через `frontend/src/core/debouncePolicy.js` или `useDebouncedCallback`.
- [ ] При смене `visitId` используется `useVisitLifecycle` (очистка, abort, инвалидация).
- [ ] Любые async‑загрузки поддерживают отмену (AbortController/axios `signal`) или безопасный ignore.

## Ссылки

- `docs/architecture/ADR-0001-centralized-caching.md`
- `docs/architecture/performance-lessons.md`
