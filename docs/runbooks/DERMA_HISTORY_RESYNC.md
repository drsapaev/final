# Пересчёт локализации в истории дерматологии

Используйте этот порядок для исторических проекций `DERMAHIST-BE-001`. Обычный GET берёт локализацию из `derma_history_entries.payload`. Поле в канонической ЭМК хранится в `specialty_data.localization.description`. Для перерасчёта используйте действующую команду `backend/scripts/resync_derma_history.py`. [Ревью исторических записей](https://github.com/drsapaev/final/pull/4115#issuecomment-6953736674)

## Проверка объёма

На согласованной цели проверьте PostgreSQL, версию приложения и миграцию. Считайте кандидатов на пересчёт под профилем чтения. Фильтр привязывает запись истории к тому же пациенту, ЭМК и визиту. Сохраняйте в журнале запуска только сводные числа и параметры цели.

```sql
BEGIN READ ONLY;

SELECT count(*) AS candidate_examinations,
       count(DISTINCT h.visit_id) AS candidate_visits
FROM derma_history_entries AS h
JOIN emr_records AS e
  ON e.id = h.record_id
 AND e.visit_id = h.visit_id
 AND e.patient_id = h.patient_id
JOIN visits AS v ON v.id = e.visit_id AND v.patient_id = e.patient_id
WHERE h.kind = 'examination'
  AND h.source = 'emr'
  AND e.is_active
  AND e.data ->> 'specialty' = 'dermatology'
  AND jsonb_typeof(e.data::jsonb #> '{specialty_data,localization,description}') = 'string'
  AND (e.data #>> '{specialty_data,localization,description}') ~ '[^[:space:]]'
  AND NULLIF(btrim(h.payload ->> 'localization'), '') IS NULL;

COMMIT;
```

Для согласования пакета тем же фильтром выберите `DISTINCT h.visit_id` в порядке ID с согласованным лимитом. Список держите в закрытой рабочей сессии оператора. Перед стартом сверяйте цель и состав пакета с задачей.

## Пересчёт пакета

1. Согласуйте окно со службой эксплуатации и остановите запись по выбранным визитам. Снимок затронутых производных строк храните в разрешённом хранилище резервных копий.
2. Запустите действующий scoped-режим только со сверенным списком визитов. `DATABASE_URL` подаётся из защищённой конфигурации. Команда пересчитывает обе категории проекции ЭМК выбранных визитов. Для каждого пакета используется отдельная транзакция.
3. Сверьте числа визитов, ЭМК и проекций с журналом команды. Через обычный GET проверьте локализацию, публичные идентификаторы, число записей и образец legacy-истории. Повторно проверьте число кандидатов тем же запросом. Перед следующим пакетом выясняйте причины любых расхождений.

```bash
CONFIRM_DERMA_HISTORY_RESYNC=1 python backend/scripts/resync_derma_history.py \
  --visit-ids "$REVIEWED_VISIT_IDS"
```

## Откат и критерий завершения

При ошибке внутри транзакции целевого пакета проверьте результат отката через GET и повторный подсчёт. Если нужен возврат уже закоммиченного пакета, используйте согласованный план восстановления сохранённых производных строк в том же окне. Каноническая ЭМК остаётся источником для сверки. Для отчёта запишите проверенный SHA, миграцию, число кандидатов до и после, число обработанных и отложенных визитов и результат проверки GET.
