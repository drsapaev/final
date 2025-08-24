-- Добавляем колонку planned_date в таблицу visits
ALTER TABLE visits ADD COLUMN planned_date DATE;

-- Всем существующим визитам проставим сегодняшнюю дату
UPDATE visits SET planned_date = DATE('now') WHERE planned_date IS NULL;
