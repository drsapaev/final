# Notification Adapter Usage

Используйте единый adapter `notify` вместо прямых вызовов `alert(...)`.

```js
import notify from '../services/notifications/uiNotifications';

notify.success('Операция выполнена');
notify.error('Произошла ошибка');
notify.info('Информация для пользователя');
notify.warning('Проверьте введённые данные');
```

## Правило

- Для pilot-файлов (`AdminPanel`, `CashierPanel`) **не использовать** `alert(...)`.
- Для пользовательских сообщений использовать только `notify.*`.

- Для проверки pilot-миграции используйте `npm run check:no-alerts:pilot`.
