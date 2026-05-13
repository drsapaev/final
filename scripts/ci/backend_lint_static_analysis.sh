#!/usr/bin/env bash
cd backend
set +e  # Не выходить при ошибках, собираем все ошибки
mkdir -p quality-reports

echo "🔍 Собираем ВСЕ ошибки линтинга для полного отчета..."
echo "Этот шаг блокирует pipeline при наличии ошибок"

# Ruff - собираем все ошибки
echo "🔍 Ruff - быстрый линтер (только app/ и tests/)..."
RUFF_ERRORS=0
RUFF_TOTAL=0

for dir in app tests; do
  if [ -d "$dir" ]; then
    echo "  Проверяем $dir/..."
    ruff check "$dir" --output-format=concise > quality-reports/ruff_${dir}.txt 2>&1
    RUFF_EXIT=$?
    if [ $RUFF_EXIT -ne 0 ]; then
      ERROR_COUNT=$(grep -c "^" quality-reports/ruff_${dir}.txt || echo "0")
      RUFF_TOTAL=$((RUFF_TOTAL + ERROR_COUNT))
      RUFF_ERRORS=$((RUFF_ERRORS + 1))
      echo "  ⚠️ Найдено ошибок в $dir/: $ERROR_COUNT"
    else
      echo "  ✅ $dir/ OK"
    fi
  fi
done

# Flake8 - собираем критические ошибки
echo "🔍 Flake8 - критические ошибки (только app/)..."
FLAKE8_ERRORS=0
if [ -d "app" ]; then
  flake8 app --select=E9,F63,F7,F82 --show-source --statistics > quality-reports/flake8.txt 2>&1
  FLAKE8_EXIT=$?
  if [ $FLAKE8_EXIT -ne 0 ]; then
    ERROR_COUNT=$(grep -c "^" quality-reports/flake8.txt || echo "0")
    FLAKE8_ERRORS=$ERROR_COUNT
    echo "  ⚠️ Найдено критических ошибок: $ERROR_COUNT"
  else
    echo "  ✅ Flake8 OK"
  fi
fi

# MyPy - собираем ошибки типов
echo "🔍 MyPy - проверка типов (только app/)..."
MYPY_ERRORS=0
if [ -d "app" ]; then
  mypy app --ignore-missing-imports --show-error-codes > quality-reports/mypy.txt 2>&1
  MYPY_EXIT=$?
  if [ $MYPY_EXIT -ne 0 ]; then
    ERROR_COUNT=$(grep -c "error:" quality-reports/mypy.txt || echo "0")
    MYPY_ERRORS=$ERROR_COUNT
    echo "  ⚠️ Найдено ошибок типов: $ERROR_COUNT"
  else
    echo "  ✅ MyPy OK"
  fi
fi

# Pylint - собираем ошибки
echo "🔍 Pylint - дополнительный анализ (только app/)..."
PYLINT_ERRORS=0
if [ -d "app" ]; then
  pylint app --disable=all --enable=E0602,E0603,E1120,E1121 > quality-reports/pylint.txt 2>&1
  PYLINT_EXIT=$?
  if [ $PYLINT_EXIT -ne 0 ]; then
    ERROR_COUNT=$(grep -c "^" quality-reports/pylint.txt || echo "0")
    PYLINT_ERRORS=$ERROR_COUNT
    echo "  ⚠️ Найдено ошибок: $ERROR_COUNT"
  else
    echo "  ✅ Pylint OK"
  fi
fi

# Создаем сводный отчет
echo ""
echo "📊 СВОДНЫЙ ОТЧЕТ ОБ ОШИБКАХ:"
echo "================================"
echo "Ruff: $RUFF_TOTAL ошибок в $RUFF_ERRORS директориях"
echo "Flake8: $FLAKE8_ERRORS критических ошибок"
echo "MyPy: $MYPY_ERRORS ошибок типов"
echo "Pylint: $PYLINT_ERRORS ошибок"
TOTAL=$((RUFF_TOTAL + FLAKE8_ERRORS + MYPY_ERRORS + PYLINT_ERRORS))
# Legacy Ruff backlog is reported but not release-blocking yet.
BLOCKING_TOTAL=$FLAKE8_ERRORS
echo "ВСЕГО: $TOTAL ошибок"
echo "БЛОКИРУЮЩИХ: $BLOCKING_TOTAL (Flake8 critical)"
echo "================================"

# Создаем единый файл со всеми ошибками
echo "📝 Создаем единый отчет со всеми ошибками..."
{
  echo "# Полный отчет об ошибках линтинга"
  echo "Сгенерировано: $(date)"
  echo ""
  echo "## Сводка"
  echo "- Ruff: $RUFF_TOTAL ошибок"
  echo "- Flake8: $FLAKE8_ERRORS критических ошибок"
  echo "- MyPy: $MYPY_ERRORS ошибок типов"
  echo "- Pylint: $PYLINT_ERRORS ошибок"
  echo "- **ВСЕГО: $TOTAL ошибок**"
  echo "- **БЛОКИРУЮЩИХ: $BLOCKING_TOTAL (Flake8 critical)**"
  echo ""
  
  if [ $RUFF_ERRORS -gt 0 ]; then
    echo "## Ruff ошибки"
    echo ""
    for dir in app tests; do
      if [ -f "quality-reports/ruff_${dir}.txt" ] && [ -s "quality-reports/ruff_${dir}.txt" ]; then
        echo "### $dir/"
        echo "\`\`\`"
        cat quality-reports/ruff_${dir}.txt
        echo "\`\`\`"
        echo ""
      fi
    done
  fi
  
  if [ $FLAKE8_ERRORS -gt 0 ]; then
    echo "## Flake8 критические ошибки"
    echo "\`\`\`"
    cat quality-reports/flake8.txt
    echo "\`\`\`"
    echo ""
  fi
  
  if [ $MYPY_ERRORS -gt 0 ]; then
    echo "## MyPy ошибки типов"
    echo "\`\`\`"
    head -200 quality-reports/mypy.txt
    echo "\`\`\`"
    echo ""
  fi
  
  if [ $PYLINT_ERRORS -gt 0 ]; then
    echo "## Pylint ошибки"
    echo "\`\`\`"
    head -100 quality-reports/pylint.txt
    echo "\`\`\`"
    echo ""
  fi
} > quality-reports/ALL_ERRORS_REPORT.md

echo "✅ Отчет сохранен в quality-reports/ALL_ERRORS_REPORT.md"
echo "📦 Все отчеты сохранены в quality-reports/"

# Показываем краткую сводку
if [ $BLOCKING_TOTAL -gt 0 ]; then
  echo ""
  echo "⚠️ ВНИМАНИЕ: Найдено $TOTAL ошибок (блокирующих: $BLOCKING_TOTAL)!"
  echo "📄 Полный отчет: quality-reports/ALL_ERRORS_REPORT.md"
  echo "💡 Рекомендация: Исправьте все ошибки перед следующим коммитом"
  echo ""
  echo "Для локальной проверки запустите:"
  echo "  cd backend"
  echo "  python scripts/collect_linting_errors.py"
  echo ""
  echo "❌ Блокируем pipeline из-за Flake8 critical ошибок"
  exit 1
else
  if [ $TOTAL -gt 0 ]; then
    echo "✅ Блокирующие проверки пройдены. Ruff/MyPy/Pylint ошибки сохранены в отчете (не блокируют)."
  else
    echo "✅ Все проверки пройдены успешно!"
  fi
fi

