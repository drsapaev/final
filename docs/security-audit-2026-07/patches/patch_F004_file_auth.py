"""
PATCH F-004: Прямая авторизация файлов через message_id
=======================================================

Файлы:
  1. backend/app/services/messages_api_service.py — download_chat_file с message_id
  2. frontend/src/components/chat/ChatWindow.jsx — обновить URL скачивания

Проблема: substring-поиск по Message.content.contains("/download/{filename}")
позволяет злоумышленнику авторизовать доступ к файлу, отправив жертве сообщение
с этим путём в тексте.

Решение: каждый download-запрос принимает message_id, сервер проверяет, что
filename соответствует file_id сообщения, а user — отправитель или получатель.
"""


# === 1. backend/app/services/messages_api_service.py ===
SERVICE_PATCH = '''
# Заменить endpoint download_chat_file (строки 824-857):

@router.get("/download/{message_id}/{filename}")
async def download_chat_file(
    message_id: int,
    filename: str,
    name: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Скачать файловое вложение.

    Авторизация: current_user должен быть отправителем или получателем message_id.
    filename должен соответствовать вложению этого сообщения.
    """
    # 1. Валидация имени файла (защита от path traversal)
    safe_filename = _safe_chat_storage_filename(filename)

    # 2. Получаем сообщение по ID
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")

    # 3. ПРЯМАЯ авторизация: user — участник переписки
    if current_user.id != message.sender_id and current_user.id != message.recipient_id:
        # Audit попытку несанкционированного доступа
        logger.warning(
            "UNAUTHORIZED_FILE_ACCESS user_id=%s message_id=%s filename=%s",
            current_user.id, message_id, safe_filename,
        )
        raise HTTPException(status_code=403, detail="Нет доступа к этому файлу")

    # 4. Проверяем, что filename действительно соответствует этому сообщению
    # Сообщение хранит URL в content (например: "/api/v1/messages/download/{filename}?name=...")
    # Проверяем, что safe_filename встречается в content
    if safe_filename not in (message.content or ""):
        raise HTTPException(
            status_code=400,
            detail="Файл не соответствует указанному сообщению"
        )

    # 5. Находим файл на диске
    try:
        file_path = _find_chat_upload_file(safe_filename)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "FILE_LOOKUP_FAILED message_id=%s filename=%s error=%s",
            message_id, safe_filename, exc,
        )
        raise HTTPException(status_code=404, detail="Файл не найден")

    # 6. Отдаём файл с security-headers
    return FileResponse(
        path=str(file_path),
        filename=name or file_path.name,
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


# Также нужно обновить формирование content при upload_file_message:
# (строки 587-602)

async def upload_file_message(
    self, *, recipient_id: int, file: UploadFile, current_user: User,
) -> MessageOut:
    recipient = self.validate_recipient(
        recipient_id=recipient_id, current_user=current_user,
    )
    content = await _read_upload_bounded(file, max_bytes=MAX_CHAT_UPLOAD_BYTES)
    original_filename = os.path.basename(file.filename or "file")
    safe_filename = _build_chat_storage_filename(
        user_id=current_user.id,
        original_filename=original_filename,
    )
    upload_dir = "uploads/chat"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as file_obj:
        file_obj.write(content)

    message_obj = self.repository.create_message(
        obj_in=MessageCreate(
            recipient_id=recipient_id,
            content=original_filename,  # временно
            message_type="document"
            if not (file.content_type or "").startswith("image")
            else "image",
        ),
        sender_id=current_user.id,
    )
    # ИЗМЕНЕНО: URL теперь содержит message_id, чтобы download-endpoint
    # мог выполнить прямую авторизацию
    message_obj.content = (
        f"/api/v1/messages/download/{message_obj.id}/{safe_filename}"
        f"?name={original_filename}"
    )
    # ... остальное без изменений
'''


# === 2. frontend/src/components/chat/ChatWindow.jsx ===
FRONTEND_PATCH = '''
// В ChatWindow.jsx, где отображается файловое вложение (строки 1019-1025):

// === До ===
// <a href={item.content} target="_blank" rel="noopener noreferrer" className="file-link">

// === После ===
// item.content теперь содержит URL вида /api/v1/messages/download/{message_id}/{filename}?name=...
// Это работает без изменений во фронтенде — достаточно обновить бэкенд.

// Однако стоит добавить проверку, что URL ведёт на наш домен:
const isInternalUrl = (url) => {
    try {
        const u = new URL(url, window.location.origin);
        return u.origin === window.location.origin;
    } catch {
        return false;
    }
};

// В рендере файла:
{item.message_type === "file" && (
    isInternalUrl(item.content) ? (
        <a href={item.content} target="_blank" rel="noopener noreferrer" className="file-link">
            <Paperclip size={16} />
            <span>{item.content.split("name=")[1] || "Файл"}</span>
        </a>
    ) : (
        <span className="file-link-disabled">Файл недоступен</span>
    )
)}
'''

if __name__ == "__main__":
    print("F-004 PATCH — Direct message_id-based file authorization")
    print("=" * 60)
    for name, content in [
        ("SERVICE_PATCH", SERVICE_PATCH),
        ("FRONTEND_PATCH", FRONTEND_PATCH),
    ]:
        print(f"\n--- {name} ---")
        print(content[:400] + "...")
