# 📋 Руководство по объединению Pull Requests

## 🎯 Текущая ситуация

У вас есть:
- **Текущая ветка**: `feat/macos-ui-refactor` с исправлениями CI/CD
- **17 открытых PR** от Dependabot для обновления зависимостей
- **Цель**: Объединить успешные PR в основную ветку `main`

## 🚀 План действий

### Вариант 1: Объединение через GitHub UI (Рекомендуется)

#### Шаг 1: Push текущих изменений
```bash
# Вы уже закоммитили изменения, теперь нужно запушить
git push origin feat/macos-ui-refactor
```

#### Шаг 2: Создать PR для feat/macos-ui-refactor
1. Перейдите на https://github.com/drsapaev/final
2. Откройте "Pull requests" → "New pull request"
3. Выберите: `base: main` ← `compare: feat/macos-ui-refactor`
4. Дождитесь, пока CI/CD пройдет все проверки ✅
5. Нажмите "Merge pull request" → "Create merge commit"

#### Шаг 3: Объединить Dependabot PR в main
Для **каждого PR от Dependabot**:

1. Откройте PR (например, `ci(deps): bump actions/upload-artifact from 4 to 5`)
2. Проверьте статус CI/CD:
   - ✅ Все проверки зеленые → можно мержить
   - ❌ Есть ошибки → не мержить, дождитесь исправлений
3. Нажмите **"Merge pull request"**
4. Выберите тип мержа:
   - **Squash and merge** (рекомендуется для Dependabot) - создаст один чистый коммит
   - **Merge commit** - создаст merge commit
   - **Rebase and merge** - линейная история (не для Dependabot)

### Вариант 2: Объединение через терминал (для опытных)

```bash
# 1. Переключиться на main
git checkout main
git pull origin main

# 2. Для каждого успешного Dependabot PR:
git fetch origin dependabot/...
git merge origin/dependabot/... --squash
git commit -m "Merge: обновление зависимостей"
git push origin main

# 3. Объединить вашу ветку:
git merge origin/feat/macos-ui-refactor
# или
git pull origin feat/macos-ui-refactor
```

## 📊 Приоритеты для Dependabot PR

### 🔥 Высокий приоритет (начала эти):
1. **actions/upload-artifact from 4 to 5** (#29)
2. **actions/setup-node from 4 to 6** (#27)
3. **uvicorn from <0.31 to <0.39** (#26)
4. **python from 3.11.10 to 3.11.14** (#25)

### ⚠️ Средний приоритет:
5. **alembic from <1.14 to <1.18** (#24)
6. **pydantic from <2.9 to <2.13** (#19)
7. **httpx from <0.28 to <0.29** (#7)

### 📦 Низкий приоритет (можно позже):
- Остальные обновления библиотек

## ⚡ Быстрый скрипт для проверки статуса всех PR

Создайте `check_prs.sh`:

```bash
#!/bin/bash
# Проверяет статус всех открытых PR

echo "Проверяем статус PR..."
gh pr list --json number,title,state,isDraft,statusCheckRollup | \
  jq -r '.[] | "\(.number) - \(.title) - \(.state) - Checks: \(.statusCheckRollup | length)"'

echo "Для объединения успешных PR:"
echo "gh pr merge [NUMBER] --squash"
```

## ⚠️ Важные моменты

1. **Проверяйте CI/CD** перед мержем каждого PR
2. **Тестируйте локально** критичные обновления перед мержем
3. **Используйте Squash and merge** для Dependabot PR (чистая история)
4. **Сохраняйте Merge commit** для больших фич (легче откатить)

## 🔧 Автоматизация для GitHub Actions

Можно настроить автоматический мерж для Dependabot PR которые прошли все проверки:

```yaml
# .github/workflows/auto-merge-dependabot.yml
name: Auto-merge Dependabot
on:
  pull_request:
    types: [opened, synchronize, reopened]
jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.actor == 'dependabot[bot]'
    steps:
      - uses: actions/github-script@v6
        with:
          script: |
            github.rest.pulls.merge({
              owner: context.repo.owner,
              repo: context.repo.repo,
              pull_number: context.payload.pull_request.number,
              merge_method: 'squash'
            })
```

## 📝 Чеклист для объединения

- [ ] Ваша ветка `feat/macos-ui-refactor` запущена
- [ ] CI/CD прошел успешно
- [ ] PR создан и проверен
- [ ] Dependabot PR проверены на конфликты
- [ ] Тесты проходят локально
- [ ] Backup создан (git tag vX.X.X)
- [ ] Уведомления команды отправлены

## 🎯 Рекомендуемый порядок

1. ✅ **Сначала** объедините ваши исправления CI/CD (feat/macos-ui-refactor)
2. ⏳ **Затем** объединяйте Dependabot PR по одному
3. 🧪 **Тестируйте** после каждого критичного обновления
4. 📦 **Пакетные обновления**: меньшие библиотеки можно объединять группами

## 🆘 Если что-то пошло не так

```bash
# Безопасный откат merge-коммита
git revert -m 1 <merge-commit-hash>

# Проверка старого состояния без переписывания текущей ветки
git switch -c recovery/merge-check <commit-hash>

# Создать backup перед merge
git tag backup-$(date +%Y%m%d-%H%M%S)
git push origin backup-$(date +%Y%m%d-%H%M%S)
```

