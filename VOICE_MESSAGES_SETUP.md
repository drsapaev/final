# Инструкция по запуску голосовых сообщений

## 1. Установка зависимостей

### Backend (опционально - для получения длительности аудио)

```bash
cd backend
pip install pydub
```

**Установка ffmpeg:**
- Windows: `choco install ffmpeg` или скачать с https://ffmpeg.org
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

> **Примечание:** Если ffmpeg не установлен, система будет работать, но длительность аудио будет примерной.

## 2. Применение миграции БД

### Вариант А: Через Alembic (рекомендуется)

```bash
cd backend
alembic upgrade head
```

### Вариант Б: Вручную (если Alembic не настроен)

Выполните SQL команды из файла `alembic/versions/voice_messages_001_add_voice_support.py` вручную в вашей БД.

Или просто перезапустите сервер - SQLAlchemy создаст новые поля автоматически (если используете `create_all()`).

## 3. Создание директории для файлов

```bash
cd backend
mkdir -p uploads/voice_messages
```

## 4. Запуск

### Backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 18000
```

### Frontend

```bash
cd frontend
npm run dev
```

## 5. Тестирование

1. Откройте фронтенд: http://localhost:5173
2. Войдите как пользователь с правами отправки сообщений (например, doctor)
3. Откройте чат с другим пользователем
4. Нажмите кнопку микрофона (🎤)
5. Разрешите доступ к микрофону в браузере
6. Запишите голосовое сообщение (5-10 секунд)
7. Нажмите "Остановить"
8. Прослушайте предпросмотр
9. Нажмите "Отправить"
10. Проверьте что сообщение появилось в чате

### Проверка в другой вкладке

1. Откройте второе окно браузера
2. Войдите как получатель
3. Откройте чат
4. Проверьте что голосовое сообщение пришло
5. Нажмите Play для воспроизведения

## 6. Возможные проблемы

### Ошибка "Microphone access denied"

- Разрешите доступ к микрофону в настройках браузера
- Chrome: Settings → Privacy and security → Site Settings → Microphone

### Ошибка "File too large"

- Максимальный размер файла: 10 MB
- Максимальная длительность: 5 минут

### Ошибка "pydub not installed"

- Установите: `pip install pydub`
- Или система будет работать с примерной длительностью

### Файл не воспроизводится

- Проверьте что файл существует в `backend/uploads/voice_messages/`
- Проверьте права доступа к директории
- Проверьте что backend возвращает правильный MIME type

## 7. API Endpoints

### Отправка голосового сообщения

```bash
POST /api/v1/messages/send-voice
Content-Type: multipart/form-data

Form fields:
- recipient_id: int
- audio_file: file (webm, mp3, wav, ogg, m4a)
```

### Стриминг голосового сообщения

```bash
GET /api/v1/messages/voice/{message_id}/stream
Authorization: Bearer {token}
```

## 8. Откат изменений (если нужно)

### Откат миграции

```bash
cd backend
alembic downgrade -1
```

### Удаление файлов

```bash
rm -rf backend/uploads/voice_messages
```

Готово! 🎙️
