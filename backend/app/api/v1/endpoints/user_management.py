"""
API endpoints для управления пользователями
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles, require_staff
from app.models.user import User
from app.services.user_management_service import get_user_management_service, UserManagementService
from app.crud.user_management import (
    user_profile, user_preferences, user_notification_settings,
    user_role, user_permission, user_group,
    user_audit_log, user_extended
)
from app.schemas.user_management import (
    UserCreateRequest, UserUpdateRequest, UserResponse, UserListResponse,
    UserProfileResponse, UserProfileUpdate, UserPreferencesResponse, UserPreferencesUpdate,
    UserNotificationSettingsResponse, UserNotificationSettingsUpdate,
    UserRoleResponse, UserRoleCreate, UserRoleUpdate,
    UserGroupResponse, UserGroupCreate, UserGroupUpdate,
    UserGroupMemberResponse, UserGroupMemberCreate,
    UserAuditLogResponse, UserSearchRequest, UserBulkActionRequest,
    UserBulkActionResponse, UserStatsResponse, UserExportRequest, UserExportResponse
)

router = APIRouter()


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Создать нового пользователя"""
    try:
        service = get_user_management_service()
        success, message, user = service.create_user(db, user_data, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Получаем полный профиль пользователя
        profile_data = service.get_user_profile(db, user.id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка получения профиля пользователя"
            )
        
        return UserResponse(**profile_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания пользователя: {str(e)}"
        )


@router.get("/users", response_model=UserListResponse)
async def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, pattern="^(Admin|Doctor|Nurse|Receptionist|Patient)$"),
    status: Optional[str] = Query(None, pattern="^(active|inactive|suspended|pending|locked)$"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список пользователей"""
    try:
        # Создаем параметры поиска
        search_params = UserSearchRequest(
            page=page,
            per_page=per_page,
            role=role,
            status=status,
            is_active=is_active,
            query=search
        )
        
        service = get_user_management_service()
        users_data, total = service.search_users(db, search_params)
        
        # Конвертируем в ответы
        user_responses = []
        for user_data in users_data:
            user_responses.append(UserResponse(**user_data))
        
        return UserListResponse(
            users=user_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка пользователей: {str(e)}"
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Получить пользователя по ID"""
    try:
        service = get_user_management_service()
        profile_data = service.get_user_profile(db, user_id)
        
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        return UserResponse(**profile_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения пользователя: {str(e)}"
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить пользователя"""
    try:
        service = get_user_management_service()
        success, message = service.update_user(db, user_id, user_data, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Получаем обновленный профиль
        profile_data = service.get_user_profile(db, user_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        return UserResponse(**profile_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления пользователя: {str(e)}"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    transfer_to: Optional[int] = Query(None, description="ID пользователя для передачи данных"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Удалить пользователя"""
    try:
        service = get_user_management_service()
        success, message = service.delete_user(db, user_id, current_user.id, transfer_to)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {"success": True, "message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления пользователя: {str(e)}"
        )


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Получить профиль пользователя"""
    try:
        profile = user_profile.get_by_user_id(db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль пользователя не найден"
            )
        
        return UserProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            first_name=profile.first_name,
            last_name=profile.last_name,
            middle_name=profile.middle_name,
            phone=profile.phone,
            phone_verified=profile.phone_verified,
            email_verified=profile.email_verified,
            alternative_email=profile.alternative_email,
            date_of_birth=profile.date_of_birth,
            gender=profile.gender,
            nationality=profile.nationality,
            language=profile.language,
            timezone=profile.timezone,
            address_line1=profile.address_line1,
            address_line2=profile.address_line2,
            city=profile.city,
            state=profile.state,
            postal_code=profile.postal_code,
            country=profile.country,
            job_title=profile.job_title,
            department=profile.department,
            employee_id=profile.employee_id,
            hire_date=profile.hire_date,
            salary=profile.salary,
            avatar_url=profile.avatar_url,
            bio=profile.bio,
            website=profile.website,
            social_links=profile.social_links,
            status=profile.status,
            last_login=profile.last_login,
            last_activity=profile.last_activity,
            login_count=profile.login_count,
            failed_login_attempts=profile.failed_login_attempts,
            locked_until=profile.locked_until,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения профиля: {str(e)}"
        )


@router.put("/users/{user_id}/profile", response_model=UserProfileResponse)
async def update_user_profile(
    user_id: int,
    profile_data: UserProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Обновить профиль пользователя"""
    try:
        # Проверяем права доступа
        if current_user.id != user_id and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для обновления профиля"
            )
        
        profile = user_profile.get_by_user_id(db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль пользователя не найден"
            )
        
        # Обновляем профиль
        update_data = profile_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        
        db.commit()
        db.refresh(profile)
        
        return UserProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            first_name=profile.first_name,
            last_name=profile.last_name,
            middle_name=profile.middle_name,
            phone=profile.phone,
            phone_verified=profile.phone_verified,
            email_verified=profile.email_verified,
            alternative_email=profile.alternative_email,
            date_of_birth=profile.date_of_birth,
            gender=profile.gender,
            nationality=profile.nationality,
            language=profile.language,
            timezone=profile.timezone,
            address_line1=profile.address_line1,
            address_line2=profile.address_line2,
            city=profile.city,
            state=profile.state,
            postal_code=profile.postal_code,
            country=profile.country,
            job_title=profile.job_title,
            department=profile.department,
            employee_id=profile.employee_id,
            hire_date=profile.hire_date,
            salary=profile.salary,
            avatar_url=profile.avatar_url,
            bio=profile.bio,
            website=profile.website,
            social_links=profile.social_links,
            status=profile.status,
            last_login=profile.last_login,
            last_activity=profile.last_activity,
            login_count=profile.login_count,
            failed_login_attempts=profile.failed_login_attempts,
            locked_until=profile.locked_until,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления профиля: {str(e)}"
        )


@router.get("/users/{user_id}/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Получить настройки пользователя"""
    try:
        # Проверяем права доступа
        if current_user.id != user_id and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для просмотра настроек"
            )
        
        preferences = user_preferences.get_by_user_id(db, user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки пользователя не найдены"
            )
        
        return UserPreferencesResponse(
            id=preferences.id,
            user_id=preferences.user_id,
            profile_id=preferences.profile_id,
            theme=preferences.theme,
            language=preferences.language,
            timezone=preferences.timezone,
            date_format=preferences.date_format,
            time_format=preferences.time_format,
            email_notifications=preferences.email_notifications,
            sms_notifications=preferences.sms_notifications,
            push_notifications=preferences.push_notifications,
            desktop_notifications=preferences.desktop_notifications,
            working_hours_start=preferences.working_hours_start,
            working_hours_end=preferences.working_hours_end,
            working_days=preferences.working_days,
            break_duration=preferences.break_duration,
            dashboard_layout=preferences.dashboard_layout,
            sidebar_collapsed=preferences.sidebar_collapsed,
            compact_mode=preferences.compact_mode,
            show_tooltips=preferences.show_tooltips,
            session_timeout=preferences.session_timeout,
            require_2fa=preferences.require_2fa,
            auto_logout=preferences.auto_logout,
            created_at=preferences.created_at,
            updated_at=preferences.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек: {str(e)}"
        )


@router.put("/users/{user_id}/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    user_id: int,
    preferences_data: UserPreferencesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Обновить настройки пользователя"""
    try:
        # Проверяем права доступа
        if current_user.id != user_id and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для обновления настроек"
            )
        
        service = get_user_management_service()
        success, message = service.update_user_preferences(db, user_id, preferences_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Получаем обновленные настройки
        preferences = user_preferences.get_by_user_id(db, user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки пользователя не найдены"
            )
        
        return UserPreferencesResponse(
            id=preferences.id,
            user_id=preferences.user_id,
            profile_id=preferences.profile_id,
            theme=preferences.theme,
            language=preferences.language,
            timezone=preferences.timezone,
            date_format=preferences.date_format,
            time_format=preferences.time_format,
            email_notifications=preferences.email_notifications,
            sms_notifications=preferences.sms_notifications,
            push_notifications=preferences.push_notifications,
            desktop_notifications=preferences.desktop_notifications,
            working_hours_start=preferences.working_hours_start,
            working_hours_end=preferences.working_hours_end,
            working_days=preferences.working_days,
            break_duration=preferences.break_duration,
            dashboard_layout=preferences.dashboard_layout,
            sidebar_collapsed=preferences.sidebar_collapsed,
            compact_mode=preferences.compact_mode,
            show_tooltips=preferences.show_tooltips,
            session_timeout=preferences.session_timeout,
            require_2fa=preferences.require_2fa,
            auto_logout=preferences.auto_logout,
            created_at=preferences.created_at,
            updated_at=preferences.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления настроек: {str(e)}"
        )


@router.get("/users/{user_id}/notifications", response_model=UserNotificationSettingsResponse)
async def get_user_notification_settings(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Получить настройки уведомлений пользователя"""
    try:
        # Проверяем права доступа
        if current_user.id != user_id and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для просмотра настроек уведомлений"
            )
        
        settings = user_notification_settings.get_by_user_id(db, user_id)
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки уведомлений не найдены"
            )
        
        return UserNotificationSettingsResponse(
            id=settings.id,
            user_id=settings.user_id,
            profile_id=settings.profile_id,
            email_appointment_reminder=settings.email_appointment_reminder,
            email_appointment_cancellation=settings.email_appointment_cancellation,
            email_appointment_confirmation=settings.email_appointment_confirmation,
            email_payment_receipt=settings.email_payment_receipt,
            email_payment_reminder=settings.email_payment_reminder,
            email_system_updates=settings.email_system_updates,
            email_security_alerts=settings.email_security_alerts,
            email_newsletter=settings.email_newsletter,
            sms_appointment_reminder=settings.sms_appointment_reminder,
            sms_appointment_cancellation=settings.sms_appointment_cancellation,
            sms_appointment_confirmation=settings.sms_appointment_confirmation,
            sms_payment_receipt=settings.sms_payment_receipt,
            sms_emergency=settings.sms_emergency,
            push_appointment_reminder=settings.push_appointment_reminder,
            push_appointment_cancellation=settings.push_appointment_cancellation,
            push_appointment_confirmation=settings.push_appointment_confirmation,
            push_payment_receipt=settings.push_payment_receipt,
            push_system_updates=settings.push_system_updates,
            push_security_alerts=settings.push_security_alerts,
            reminder_time_before=settings.reminder_time_before,
            quiet_hours_start=settings.quiet_hours_start,
            quiet_hours_end=settings.quiet_hours_end,
            weekend_notifications=settings.weekend_notifications,
            created_at=settings.created_at,
            updated_at=settings.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек уведомлений: {str(e)}"
        )


@router.put("/users/{user_id}/notifications", response_model=UserNotificationSettingsResponse)
async def update_user_notification_settings(
    user_id: int,
    settings_data: UserNotificationSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Обновить настройки уведомлений пользователя"""
    try:
        # Проверяем права доступа
        if current_user.id != user_id and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для обновления настроек уведомлений"
            )
        
        service = get_user_management_service()
        success, message = service.update_notification_settings(db, user_id, settings_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Получаем обновленные настройки
        settings = user_notification_settings.get_by_user_id(db, user_id)
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки уведомлений не найдены"
            )
        
        return UserNotificationSettingsResponse(
            id=settings.id,
            user_id=settings.user_id,
            profile_id=settings.profile_id,
            email_appointment_reminder=settings.email_appointment_reminder,
            email_appointment_cancellation=settings.email_appointment_cancellation,
            email_appointment_confirmation=settings.email_appointment_confirmation,
            email_payment_receipt=settings.email_payment_receipt,
            email_payment_reminder=settings.email_payment_reminder,
            email_system_updates=settings.email_system_updates,
            email_security_alerts=settings.email_security_alerts,
            email_newsletter=settings.email_newsletter,
            sms_appointment_reminder=settings.sms_appointment_reminder,
            sms_appointment_cancellation=settings.sms_appointment_cancellation,
            sms_appointment_confirmation=settings.sms_appointment_confirmation,
            sms_payment_receipt=settings.sms_payment_receipt,
            sms_emergency=settings.sms_emergency,
            push_appointment_reminder=settings.push_appointment_reminder,
            push_appointment_cancellation=settings.push_appointment_cancellation,
            push_appointment_confirmation=settings.push_appointment_confirmation,
            push_payment_receipt=settings.push_payment_receipt,
            push_system_updates=settings.push_system_updates,
            push_security_alerts=settings.push_security_alerts,
            reminder_time_before=settings.reminder_time_before,
            quiet_hours_start=settings.quiet_hours_start,
            quiet_hours_end=settings.quiet_hours_end,
            weekend_notifications=settings.weekend_notifications,
            created_at=settings.created_at,
            updated_at=settings.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления настроек уведомлений: {str(e)}"
        )


@router.get("/users/{user_id}/activity", response_model=List[UserAuditLogResponse])
async def get_user_activity(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Получить активность пользователя"""
    try:
        # Проверяем права доступа
        if current_user.id != user_id and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для просмотра активности"
            )
        
        activities = user_audit_log.get_by_user_id(db, user_id, limit)
        
        activity_responses = []
        for activity in activities:
            activity_responses.append(UserAuditLogResponse(
                id=activity.id,
                user_id=activity.user_id,
                action=activity.action,
                resource_type=activity.resource_type,
                resource_id=activity.resource_id,
                description=activity.description,
                old_values=activity.old_values,
                new_values=activity.new_values,
                ip_address=activity.ip_address,
                user_agent=activity.user_agent,
                session_id=activity.session_id,
                created_at=activity.created_at
            ))
        
        return activity_responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения активности: {str(e)}"
        )


@router.get("/users/stats", response_model=UserStatsResponse)
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    """Получить статистику пользователей"""
    try:
        service = get_user_management_service()
        stats = service.get_user_stats(db)
        
        return UserStatsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )


@router.post("/users/bulk-action", response_model=UserBulkActionResponse)
async def bulk_action_users(
    action_data: UserBulkActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Выполнить массовые действия с пользователями"""
    try:
        service = get_user_management_service()
        success, message, result = service.bulk_action_users(db, action_data, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return UserBulkActionResponse(
            success=True,
            message=message,
            processed_count=result["processed_count"],
            failed_count=result["failed_count"],
            failed_users=result["failed_users"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка массового действия: {str(e)}"
        )


@router.post("/users/export", response_model=UserExportResponse)
async def export_users(
    export_data: UserExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Экспорт пользователей"""
    try:
        service = get_user_management_service()
        
        # Получаем пользователей для экспорта
        users_query = db.query(User)
        
        # Применяем фильтры если есть
        if export_data.filters:
            if export_data.filters.username:
                users_query = users_query.filter(User.username.contains(export_data.filters.username))
            if export_data.filters.email:
                users_query = users_query.filter(User.email.contains(export_data.filters.email))
            if export_data.filters.role:
                users_query = users_query.filter(User.role == export_data.filters.role)
            if export_data.filters.is_active is not None:
                users_query = users_query.filter(User.is_active == export_data.filters.is_active)
            if export_data.filters.created_from:
                users_query = users_query.filter(User.created_at >= export_data.filters.created_from)
            if export_data.filters.created_to:
                users_query = users_query.filter(User.created_at <= export_data.filters.created_to)
        
        users = users_query.all()
        
        if not users:
            return UserExportResponse(
                success=False,
                message="Нет пользователей для экспорта",
                record_count=0
            )
        
        # Запускаем экспорт в фоновом режиме
        background_tasks.add_task(
            service.export_users_background,
            users,
            export_data,
            current_user.id,
            db
        )
        
        return UserExportResponse(
            success=True,
            message=f"Экспорт {len(users)} пользователей запущен в фоновом режиме",
            record_count=len(users)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка экспорта: {str(e)}"
        )


@router.get("/users/export/files")
async def list_export_files(
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить список файлов экспорта"""
    try:
        from pathlib import Path
        import os
        
        export_dir = Path("exports/users")
        if not export_dir.exists():
            return {
                "success": True,
                "message": "Нет файлов экспорта",
                "files": []
            }
        
        files = []
        for file_path in export_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        # Сортируем по дате создания (новые первыми)
        files.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "success": True,
            "message": f"Найдено {len(files)} файлов экспорта",
            "files": files
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения файлов экспорта: {str(e)}"
        )


@router.get("/users/export/download/{filename}")
async def download_export_file(
    filename: str,
    current_user: User = Depends(require_roles("Admin"))
):
    """Скачать файл экспорта"""
    try:
        from pathlib import Path
        from fastapi.responses import FileResponse
        import os
        
        # Проверяем безопасность пути
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недопустимое имя файла"
            )
        
        export_dir = Path("exports/users")
        file_path = export_dir / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден"
            )
        
        # Определяем MIME тип
        mime_type = "application/octet-stream"
        if filename.endswith('.csv'):
            mime_type = "text/csv"
        elif filename.endswith('.json'):
            mime_type = "application/json"
        elif filename.endswith('.xlsx'):
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif filename.endswith('.pdf'):
            mime_type = "application/pdf"
        elif filename.endswith('.txt'):
            mime_type = "text/plain"
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка скачивания файла: {str(e)}"
        )


@router.delete("/users/export/files/{filename}")
async def delete_export_file(
    filename: str,
    current_user: User = Depends(require_roles("Admin"))
):
    """Удалить файл экспорта"""
    try:
        from pathlib import Path
        
        # Проверяем безопасность пути
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недопустимое имя файла"
            )
        
        export_dir = Path("exports/users")
        file_path = export_dir / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден"
            )
        
        file_path.unlink()
        
        return {
            "success": True,
            "message": f"Файл {filename} успешно удален"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления файла: {str(e)}"
        )


@router.get("/users/health")
async def user_management_health_check():
    """Проверка здоровья сервиса управления пользователями"""
    return {
        "status": "ok",
        "service": "user_management",
        "features": [
            "user_profiles",
            "user_preferences",
            "notification_settings",
            "user_roles",
            "user_groups",
            "audit_logging",
            "bulk_actions",
            "user_search",
            "user_statistics"
        ],
        "supported_roles": ["Admin", "Doctor", "Nurse", "Receptionist", "Patient"],
        "supported_statuses": ["active", "inactive", "suspended", "pending", "locked"],
        "export_formats": ["csv", "excel", "json", "pdf"]
    }

