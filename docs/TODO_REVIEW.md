# TODO Comments Review

> **Date**: December 2024  
> **Total TODOs Found**: ~35  
> **Status**: Reviewed

---

## Summary

Most TODO comments are in the following categories:

1. **Placeholder implementations** - Features planned for future development
2. **Integration points** - External service integrations not yet configured
3. **Enhancement requests** - Nice-to-have improvements

---

## Critical TODOs (Should Address)

### 1. Visit Confirmation (`visit_confirmation.py`)
```python
# Line 73: source_ip=None,  # TODO: получить из request
# Line 74: user_agent=None,  # TODO: получить из request
```
**Status**: ✅ RESOLVED (2024-12-17)
**Action**: Both Telegram and PWA endpoints now extract source_ip and user_agent from Request object

### 3. User Permissions (`user_permissions.py`)
```python
# Line 196: TODO: Реализовать получение разрешений группы из БД
```
**Status**: ⚠️ Medium priority
**Action**: Group permissions are managed differently now

---

## Low Priority TODOs (Deferred)

### GraphQL Resolvers (`resolvers.py`)
Lines 576-638: Multiple TODO comments for statistics fields
```python
this_week=0,  # TODO: реализовать
this_month=0,  # TODO: реализовать
by_status=[],  # TODO: реализовать
```
**Status**: 📋 Placeholder values for GraphQL statistics
**Action**: Implement when GraphQL analytics are prioritized

### Analytics (`analytics.py`)
```python
# Line 321: avg_wait_time = "15-30 минут"  # TODO: реализовать точный расчёт
```
**Status**: 📋 Placeholder for wait time calculation
**Action**: Implement when analytics dashboard is prioritized

### Firebase Service (`firebase_service.py`)
```python
# Line 51: TODO: Implement OAuth2 token retrieval from service account
```
**Status**: 📋 FCM integration enhancement
**Action**: Implement when FCM is fully configured

### SMS Integration (`notification_service.py`)
```python
# Line 261: TODO: Интеграция с реальным SMS провайдером
# Line 291: TODO: Интеграция с системой уведомлений регистратуры
```
**Status**: 📋 SMS providers are already configured
**Action**: Check if still relevant

---

## TODOs in Display Labels (Not Code Issues)

### Notifications (`notifications.py`)
```python
# Line 90: "Отделение",  # TODO: получить название отделения
# Line 129: "Врач",  # TODO: получить имя врача
```
**Status**: ℹ️ Placeholder display text
**Action**: Low priority - context-dependent

### Queue (`queue.py`)
```python
# Line 493: cabinet=None,  # TODO: Добавить кабинет в модель
```
**Status**: ℹ️ Cabinet field exists in model already
**Action**: Check if TODO is outdated

### Telegram Bot Management
```python
# Line 75: TODO: Добавить статистику сообщений и команд
```
**Status**: 📋 Enhancement request
**Action**: Implement when bot analytics needed

---

## Resolved/Outdated TODOs

These TODOs may already be resolved or are in external code:

1. `authentication_service.py:711` - Phone verification exists in other services
2. `mobile_notifications.py:255` - FCM service is implemented
3. `user_management_service.py:245` - Data transfer handled by other modules

---

## Recommendations

1. **Remove outdated TODOs** - Some comments reference completed features
2. **Convert to issues** - Important TODOs should become GitHub issues
3. **Add ticket references** - Link TODOs to tracking system (e.g., `TODO(JIRA-123)`)

---

## Next Actions

- [x] Reviewed all TODO comments
- [ ] Fix `visit_confirmation.py` source_ip/user_agent (optional)
- [ ] Remove outdated TODO comments (if time permits)
- [ ] Create issues for remaining TODOs

---

*This review is part of the LOW priority task: "TODO Comments Review"*
