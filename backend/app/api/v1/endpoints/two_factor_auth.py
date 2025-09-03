from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import user as user_crud
from app.models.user import User
from app.services.two_factor_auth import two_factor_auth_service

router = APIRouter()


@router.post("/setup")
async def setup_2fa(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Настройка двухфакторной аутентификации"""
    # Проверяем, не настроена ли уже 2FA
    if two_factor_auth_service.is_2fa_enabled(current_user.two_factor_secret):
        raise HTTPException(status_code=400, detail="2FA уже настроена")

    # Настраиваем 2FA
    setup_data = two_factor_auth_service.setup_2fa(
        username=current_user.username, email=current_user.email
    )

    # Сохраняем секрет в базе данных
    user_crud.update(
        db,
        db_obj=current_user,
        obj_in={
            "two_factor_secret": setup_data["secret"],
            "two_factor_backup_codes": setup_data["hashed_backup_codes"],
        },
    )

    return {
        "message": "2FA настроена успешно",
        "qr_code": setup_data["qr_code"],
        "totp_uri": setup_data["totp_uri"],
        "backup_codes": setup_data["backup_codes"],
        "algorithm": setup_data["algorithm"],
        "digits": setup_data["digits"],
        "interval": setup_data["interval"],
        "issuer": setup_data["issuer"],
    }


@router.post("/verify-setup")
async def verify_2fa_setup(
    token: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Подтверждение настройки 2FA"""
    if not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="2FA не настроена")

    # Проверяем токен
    if two_factor_auth_service.verify_2fa_setup(current_user.two_factor_secret, token):
        # Активируем 2FA
        user_crud.update(db, db_obj=current_user, obj_in={"two_factor_enabled": True})

        return {"message": "2FA активирована успешно"}
    else:
        raise HTTPException(status_code=400, detail="Неверный токен")


@router.post("/disable")
async def disable_2fa(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Отключение двухфакторной аутентификации"""
    if not two_factor_auth_service.is_2fa_enabled(current_user.two_factor_secret):
        raise HTTPException(status_code=400, detail="2FA не настроена")

    # Отключаем 2FA
    user_crud.update(
        db,
        db_obj=current_user,
        obj_in={
            "two_factor_enabled": False,
            "two_factor_secret": None,
            "two_factor_backup_codes": [],
        },
    )

    return {"message": "2FA отключена успешно"}


@router.get("/status")
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    """Получение статуса 2FA"""
    if not current_user.two_factor_secret:
        return {"enabled": False}

    return two_factor_auth_service.get_2fa_info(current_user.two_factor_secret)


@router.post("/authenticate")
async def authenticate_with_2fa(
    token: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Аутентификация с 2FA"""
    if not two_factor_auth_service.is_2fa_enabled(current_user.two_factor_secret):
        raise HTTPException(status_code=400, detail="2FA не настроена")

    # Проверяем токен
    success, message, used_backup_code = two_factor_auth_service.authenticate_with_2fa(
        current_user.two_factor_secret,
        token,
        current_user.two_factor_backup_codes or [],
        current_user.used_backup_codes or [],
    )

    if success:
        # Если использован резервный код, помечаем его как использованный
        if used_backup_code:
            used_codes = current_user.used_backup_codes or []
            used_codes.append(used_backup_code)

            user_crud.update(
                db, db_obj=current_user, obj_in={"used_backup_codes": used_codes}
            )

        return {"message": message, "authenticated": True}
    else:
        raise HTTPException(status_code=400, detail=message)


@router.post("/generate-backup-codes")
async def generate_new_backup_codes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Генерация новых резервных кодов"""
    if not two_factor_auth_service.is_2fa_enabled(current_user.two_factor_secret):
        raise HTTPException(status_code=400, detail="2FA не настроена")

    # Генерируем новые резервные коды
    backup_codes, hashed_codes = two_factor_auth_service.generate_backup_codes()

    # Сохраняем в базе данных
    user_crud.update(
        db,
        db_obj=current_user,
        obj_in={
            "two_factor_backup_codes": hashed_codes,
            "used_backup_codes": [],  # Сбрасываем использованные коды
        },
    )

    return {
        "message": "Новые резервные коды сгенерированы",
        "backup_codes": backup_codes,
    }


@router.get("/backup-codes-remaining")
async def get_remaining_backup_codes(current_user: User = Depends(get_current_user)):
    """Получение количества оставшихся резервных кодов"""
    if not current_user.two_factor_backup_codes:
        return {"remaining": 0}

    used_count = len(current_user.used_backup_codes or [])
    total_count = len(current_user.two_factor_backup_codes)
    remaining = total_count - used_count

    return {"total": total_count, "used": used_count, "remaining": remaining}


@router.post("/test-token")
async def test_2fa_token(current_user: User = Depends(require_roles(["admin"]))):
    """Тестирование 2FA токена (только для админов)"""
    if not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="2FA не настроена")

    # Получаем текущий токен
    current_token = two_factor_auth_service.get_current_totp(
        current_user.two_factor_secret
    )

    # Получаем оставшееся время
    remaining_time = two_factor_auth_service.get_remaining_time()

    return {
        "current_token": current_token,
        "remaining_time": remaining_time,
        "interval": two_factor_auth_service.interval,
        "algorithm": two_factor_auth_service.algorithm,
        "digits": two_factor_auth_service.digits,
    }


@router.post("/login-with-2fa")
async def login_with_2fa(
    username: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Вход в систему с 2FA"""
    # Сначала проверяем логин и пароль
    user = user_crud.authenticate(db, username=username, password=password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные")

    # Проверяем, включена ли 2FA
    if not two_factor_auth_service.is_2fa_enabled(user.two_factor_secret):
        raise HTTPException(
            status_code=400, detail="2FA не настроена для этого пользователя"
        )

    # Проверяем 2FA токен
    success, message, used_backup_code = two_factor_auth_service.authenticate_with_2fa(
        user.two_factor_secret,
        token,
        user.two_factor_backup_codes or [],
        user.used_backup_codes or [],
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Если использован резервный код, помечаем его как использованный
    if used_backup_code:
        used_codes = user.used_backup_codes or []
        used_codes.append(used_backup_code)

        user_crud.update(db, db_obj=user, obj_in={"used_backup_codes": used_codes})

    # Генерируем JWT токен
    from app.core.security import create_access_token

    access_token = create_access_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "roles": user.roles,
        },
    }
