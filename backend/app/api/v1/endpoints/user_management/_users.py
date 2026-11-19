"""Split from app.api.v1.endpoints.user_management.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.user_management._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.user_management._helpers import (
    _USER_MANAGEMENT_ROLE_PATTERN,
    _find_user_export_file,
    _safe_user_export_filename,
    _user_export_mime_type,
    router,
)  # noqa: F401
from app.schemas.clinic import ServiceUnavailableDetail
from app.schemas.user_management import UserPhoneScopeConflictDetail
from app.services.patient_phone_scope import (
    PatientPhoneScopeConflict,
)
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
    check_patient_scope,
    check_profile_bearer,
    enforce_phone_scope,
    lock_profile,
    lock_profile_users,
    prepare_phone_change,
)
from app.services.token_blacklist_service import revoke_account_sessions_locked


def _lock_admin_user_mutation_rows(
    db: Session,
    request: Request,
    current_user: User,
    *related_user_ids: int | None,
):
    """Lock the live admin and every user touched by one CRUD operation.

    Acquire one User row at a time in ascending ID order. Besides preventing
    cross-admin deadlocks, separate statements give a row that was updated
    while this request waited a fresh READ COMMITTED snapshot before the
    bearer and role checks run.
    """
    bearer = capture_profile_bearer(request, current_user)
    if not isinstance(bearer.jti, str) or not bearer.jti:
        raise ProfileBearerInvalid("Bearer session unavailable")

    user_ids = sorted(
        {current_user.id, *(value for value in related_user_ids if value is not None)}
    )
    locked_users: dict[int, User] = {}
    for user_id in user_ids:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update(key_share=True)
            .populate_existing()
            .first()
        )
        if user is not None:
            locked_users[user_id] = user

    actor = locked_users.get(current_user.id)
    if actor is None:
        raise ProfileBearerInvalid("Bearer session unavailable")
    check_profile_bearer(db, actor, bearer)
    # Preserve require_roles("Admin") semantics, including its case-insensitive
    # Admin role check and superuser bypass.
    actor_role = str(actor.role or "").strip().casefold()
    if actor_role != "admin" and not actor.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для управления пользователями",
        )
    return locked_users, bearer


def _before_commit_expiry_guard(bearer):
    """Return a commit hook and flag for a bearer expiring mid-operation."""
    state = {"expired": False}

    def check_expiry() -> None:
        try:
            check_bearer_expiry(bearer)
        except ProfileBearerInvalid:
            state["expired"] = True
            raise

    return check_expiry, state


def _raise_if_bearer_expired(state) -> None:
    if state["expired"]:
        raise HTTPException(status_code=401, detail="Bearer session unavailable")


@router.post(
    "/users",
    response_model=UserResponse,
    # Codex round-8 P2: the Doctor-onboarding branch returns 503 when the
    # specialty catalog is unavailable (missing/inactive rows after the
    # 0051 baseline seed). Generated consumers model the configured
    # failure via the same ServiceUnavailableDetail contract the
    # admin-doctor routes publish.
    responses={
        503: {
            "model": ServiceUnavailableDetail,
            "description": (
                "Каталог специальностей не настроен (миграции/seed 0051 не выполнены)"
            ),
        }
    },
)
async def create_user(
    user_data: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Создать нового пользователя"""
    try:
        _locked_users, bearer = _lock_admin_user_mutation_rows(
            db, request, current_user
        )
        before_commit, expiry_state = _before_commit_expiry_guard(bearer)

        # Canonical doctor onboarding (owner decision 2026-09-01): the medical
        # specialty catalog (migration 0051) is the runtime SSOT — the schema
        # layer checks only the payload shape; membership + active status are
        # enforced here, at the write boundary, BEFORE any row is created.
        if getattr(user_data, "role", None) == "Doctor":
            from app.services.medical_specialty_catalog import (
                MedicalSpecialtyCatalogError,
                MedicalSpecialtyCatalogService,
            )

            requested_specialty = (
                user_data.doctor_profile.specialty.strip()
                if user_data.doctor_profile is not None
                else ""
            )
            try:
                selectable = MedicalSpecialtyCatalogService(
                    db
                ).is_selectable_for_onboarding(requested_specialty)
            except MedicalSpecialtyCatalogError as catalog_error:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Каталог медицинских специальностей не настроен: "
                        "выполните миграции БД (baseline seed 0051)."
                    ),
                ) from catalog_error
            if not selectable:
                # Codex round-9 P2: the operation's declared 422 body is
                # HTTPValidationError (detail = array of {loc, msg, type}) — a
                # plain-string detail would break generated clients decoding
                # the documented schema, so return the standard shape.
                raise HTTPException(
                    status_code=422,
                    detail=[
                        {
                            "loc": ["body", "doctor_profile", "specialty"],
                            "msg": (
                                f"Специальность '{requested_specialty}' должна "
                                "быть активным кодом из каталога специальностей "
                                "(/admin/doctors/specialty-vocabulary)."
                            ),
                            "type": "value_error",
                        }
                    ],
                )

        service = get_user_management_service()
        success, message, user = service.create_user(
            db,
            user_data,
            current_user.id,
            before_commit=before_commit,
        )

        _raise_if_bearer_expired(expiry_state)

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # Получаем полный профиль пользователя
        profile_data = service.get_user_profile(db, user.id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка получения профиля пользователя",
            )

        return UserResponse(**profile_data)

    except ProfileBearerInvalid as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users", response_model=UserListResponse)
def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: str | None = Query(
        None, pattern=_USER_MANAGEMENT_ROLE_PATTERN
        # Codex round-1 P2: reuse the shared vocabulary — the previous
        # hardcoded list rejected cardio/derma/dentist/Registrar/SuperAdmin/
        # Manager BEFORE UserSearchRequest was constructed, so ?role=cardio
        # answered 422 while the schema advertised it as valid.
        # READ surface — the filter vocabulary now equals the canonical
        # write vocabulary: E-4 (§4.1.27) dropped 'Receptionist' (window
        # closed) and M-2 (2026-09-05) dropped 'Manager' the same way,
        # after the ops deactivation of the single stored row
        # (smoke_manager, id=20). ?role=Manager now answers 422.
        # TODO(DB_ROLES): Replace regex with DB-driven validation in Phase 0.5
    ),
    status_filter: str | None = Query(
        None, pattern="^(active|inactive|suspended|pending|locked)$", alias="status"
    ),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить список пользователей"""
    try:
        # Создаем параметры поиска
        search_params = UserSearchRequest(
            page=page,
            per_page=per_page,
            role=role,
            status=status_filter,
            is_active=is_active,
            query=search,
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
            total_pages=(total + per_page - 1) // per_page,
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    # Phase 0 (PR #3320 round 2, P1): the systemic phone-scope invariant —
    # reactivating a Patient-user, changing role -> Patient, or pointing a
    # Patient-user at a phone that already backs another active patient
    # portal account is rejected BEFORE any state changes.
    responses={
        409: {
            "model": UserPhoneScopeConflictDetail,
            "description": (
                "Номер телефона уже используется другим активным аккаунтом "
                "пациента портала (инвариант phone-scope Phase 0)"
            ),
        }
    },
)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить пользователя"""
    try:
        _locked_users, bearer = _lock_admin_user_mutation_rows(
            db, request, current_user, user_id
        )
        before_commit, expiry_state = _before_commit_expiry_guard(bearer)

        service = get_user_management_service()
        success, message = service.update_user(
            db,
            user_id,
            user_data,
            current_user.id,
            before_commit=before_commit,
        )

        _raise_if_bearer_expired(expiry_state)

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # Получаем обновленный профиль
        profile_data = service.get_user_profile(db, user_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
            )

        return UserResponse(**profile_data)

    except PatientPhoneScopeConflict as exc:
        # Phase 0 phone-scope invariant (round-2 P1): controlled 409 — the
        # service rolled back, nothing changed, the other account keeps the
        # phone and the resolver predicate stays single-candidate.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
    except ProfileBearerInvalid as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/users/{user_id}", response_model=dict[str, Any])
async def delete_user(
    user_id: int,
    request: Request,
    transfer_to: int | None = Query(
        None, description="ID пользователя для передачи данных"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Удалить пользователя"""
    try:
        _locked_users, bearer = _lock_admin_user_mutation_rows(
            db, request, current_user, user_id, transfer_to
        )
        before_commit, expiry_state = _before_commit_expiry_guard(bearer)

        service = get_user_management_service()
        success, message = service.delete_user(
            db,
            user_id,
            current_user.id,
            transfer_to,
            before_commit=before_commit,
        )

        _raise_if_bearer_expired(expiry_state)

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return {"success": True, "message": message}

    except ProfileBearerInvalid as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Получить профиль пользователя.

    ADM-AUDIT-28 P0-1: ownership check — non-Admin staff can only see
    their own profile. Раньше любой Nurse/Receptionist мог читать
    salary, address, DOB любого пользователя.
    """
    from app.services.authorization.staff import staff_authorization_service
    if not staff_authorization_service.can_manage_users(current_user, target_user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к профилю другого пользователя",
        )
    try:
        profile = user_profile.get_by_user_id(db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль пользователя не найден",
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
            updated_at=profile.updated_at,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/users/{user_id}/profile",
    response_model=UserProfileResponse,
    # Phase 0 (PR #3320 round 2, P1): same systemic phone-scope invariant
    # for the staff-side profile surface — a phone change may not aim a
    # Patient-user at a phone that already backs another active patient
    # portal account.
    responses={
        409: {
            "model": UserPhoneScopeConflictDetail,
            "description": (
                "Номер телефона уже используется другим активным аккаунтом "
                "пациента портала (инвариант phone-scope Phase 0)"
            ),
        }
    },
)
def update_user_profile(
    user_id: int,
    profile_data: UserProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Обновить профиль пользователя"""
    try:
        bearer_context = capture_profile_bearer(request, current_user)
        actor, target_user = lock_profile_users(db, current_user.id, user_id)
        check_profile_bearer(db, actor, bearer_context)
        # Re-evaluate staff authorization with the live locked principal.
        from app.services.authorization.staff import staff_authorization_service
        if not staff_authorization_service.can_manage_users(actor, target_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для обновления профиля",
            )

        # Round-4 P1 (review, concurrency): same serialization contract as
        # update_user / bulk — the candidate-defining state (users.role,
        # user_profiles.phone, user_profiles.phone_verified) is read under
        # FOR UPDATE before any guard decision is computed from it. The
        # locked instances double as the records mutated below (identity
        # map), so no unlocked re-read can re-enter between guard and
        # mutation. Global lock order: users row -> user_profiles row ->
        # phone advisory lock.
        profile = lock_profile(db, user_id)
        if target_user is None or profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль пользователя не найден",
            )

        # Обновляем профиль
        update_data = profile_data.dict(exclude_unset=True)

        # Phase 0 phone-scope invariant (round-2 P1): the staff-side profile
        # surface is another path that can re-aim a verified phone. A
        # Patient-user may not be pointed at a phone that already backs
        # another ACTIVE patient portal account (409), and ANY changed phone
        # loses its verified flag — possession is not proven for an entered
        # number (same convention as the self-service phone change).
        phone_changed = prepare_phone_change(db, profile, update_data)
        check_patient_scope(db, actor, bearer_context)
        if phone_changed:
            enforce_phone_scope(db, target_user, update_data)
            revoke_account_sessions_locked(db, target_user, revoke_password_resets=True)
            profile.phone_verified = False

        profile = UserManagementApiService(db).apply_profile_update(
            profile=profile,
            update_data=update_data,
            before_commit=lambda: check_bearer_expiry(bearer_context),
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
            updated_at=profile.updated_at,
        )

    except ProfileBearerInvalid as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from exc
    except PatientPhoneScopeConflict as exc:
        db.rollback()  # release the phone-scope advisory lock; nothing changed
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/{user_id}/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Получить настройки пользователя"""
    try:
        # Проверяем права доступа
        from app.services.authorization.staff import staff_authorization_service
        if not staff_authorization_service.can_manage_users(current_user, target_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для просмотра настроек",
            )

        preferences = user_preferences.get_by_user_id(db, user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки пользователя не найдены",
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
            updated_at=preferences.updated_at,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/users/{user_id}/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    user_id: int,
    preferences_data: UserPreferencesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Обновить настройки пользователя"""
    try:
        # Проверяем права доступа
        from app.services.authorization.staff import staff_authorization_service
        if not staff_authorization_service.can_manage_users(current_user, target_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для обновления настроек",
            )

        service = get_user_management_service()
        success, message = service.update_user_preferences(
            db, user_id, preferences_data
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # Получаем обновленные настройки
        preferences = user_preferences.get_by_user_id(db, user_id)
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки пользователя не найдены",
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
            updated_at=preferences.updated_at,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/users/{user_id}/notifications", response_model=UserNotificationSettingsResponse
)
async def get_user_notification_settings(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Получить настройки уведомлений пользователя"""
    try:
        # Проверяем права доступа
        from app.services.authorization.staff import staff_authorization_service
        if not staff_authorization_service.can_manage_users(current_user, target_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для просмотра настроек уведомлений",
            )

        settings = user_notification_settings.get_by_user_id(db, user_id)
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки уведомлений не найдены",
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
            updated_at=settings.updated_at,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/users/{user_id}/notifications", response_model=UserNotificationSettingsResponse
)
async def update_user_notification_settings(
    user_id: int,
    settings_data: UserNotificationSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Обновить настройки уведомлений пользователя"""
    try:
        # Проверяем права доступа
        from app.services.authorization.staff import staff_authorization_service
        if not staff_authorization_service.can_manage_users(current_user, target_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для обновления настроек уведомлений",
            )

        service = get_user_management_service()
        success, message = service.update_notification_settings(
            db, user_id, settings_data
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # Получаем обновленные настройки
        settings = user_notification_settings.get_by_user_id(db, user_id)
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки уведомлений не найдены",
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
            updated_at=settings.updated_at,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/{user_id}/activity", response_model=list[UserAuditLogResponse])
async def get_user_activity(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Получить активность пользователя"""
    try:
        # Проверяем права доступа
        from app.services.authorization.staff import staff_authorization_service
        if not staff_authorization_service.can_manage_users(current_user, target_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для просмотра активности",
            )

        activities = user_audit_log.get_by_user_id(db, user_id, limit)

        activity_responses = []
        for activity in activities:
            activity_responses.append(
                UserAuditLogResponse(
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
                    created_at=activity.created_at,
                )
            )

        return activity_responses

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/stats", response_model=UserStatsResponse)
async def get_user_stats(
    db: Session = Depends(get_db), current_user: User = Depends(require_staff)
):
    """Получить статистику пользователей"""
    try:
        from app.api.v1.endpoints import user_management

        service = user_management.get_user_management_service()
        stats = service.get_user_stats(db)

        return UserStatsResponse(**stats)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/users/bulk-action", response_model=UserBulkActionResponse)
async def bulk_action_users(
    action_data: UserBulkActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Выполнить массовые действия с пользователями"""
    try:
        service = get_user_management_service()
        success, message, result = service.bulk_action_users(
            db, action_data, current_user.id
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return UserBulkActionResponse(
            success=True,
            message=message,
            processed_count=result["processed_count"],
            failed_count=result["failed_count"],
            failed_users=result["failed_users"],
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/export/files", response_model=dict[str, Any])
async def list_export_files(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
current_user: User = Depends(require_roles("Admin"))):
    """Получить список файлов экспорта"""
    try:
        export_dir = USER_EXPORT_DIR
        if not export_dir.exists():
            return {"success": True, "message": "Нет файлов экспорта", "files": []}

        export_root = export_dir.resolve()
        files = []
        for file_path in export_dir.iterdir():
            resolved_path = file_path.resolve()
            if resolved_path.parent != export_root or not resolved_path.is_file():
                continue
            try:
                _safe_user_export_filename(file_path.name)
            except HTTPException:
                continue
            stat = resolved_path.stat()
            files.append(
                {
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        # Сортируем по дате создания (новые первыми)
        files.sort(key=lambda x: x["created_at"], reverse=True)

        return {
            "success": True,
            "message": f"Найдено {len(files)} файлов экспорта",
            "files": files,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/export/download/{filename}", response_model=dict[str, Any])
async def download_export_file(
    filename: str, current_user: User = Depends(require_roles("Admin"))
):
    """Скачать файл экспорта"""
    try:
        from fastapi.responses import FileResponse

        file_path = _find_user_export_file(filename)
        mime_type = _user_export_mime_type(file_path.name)

        return FileResponse(
            path=str(file_path), filename=file_path.name, media_type=mime_type
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/users/export/files/{filename}", response_model=dict[str, Any])
async def delete_export_file(
    filename: str, current_user: User = Depends(require_roles("Admin"))
):
    """Удалить файл экспорта"""
    try:
        file_path = _find_user_export_file(filename)

        file_path.unlink()

        return {
            "success": True,
            "message": f"Файл {file_path.name} успешно удален",
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/health", response_model=dict[str, Any])
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
            "user_statistics",
        ],
        # REC-1 (Receptionist deprecation) + Codex re-review P2 (PR #3025):
        # 'Receptionist' replaced by the canonical 'Registrar' — the module
        # vocabulary now matches the write contract (create/update accept
        # Registrar; deprecated spelling frozen out of writes).
        "supported_roles": ["Admin", "Doctor", "Registrar", "Patient"],
        "supported_statuses": ["active", "inactive", "suspended", "pending", "locked"],
        "export_formats": ["csv", "excel", "json", "pdf"],
    }


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Получить пользователя по ID.

    ADM-AUDIT-28 P0-2: ownership check — non-Admin staff can only see
    their own user record.
    """
    from app.services.authorization.staff import staff_authorization_service
    if not staff_authorization_service.can_manage_users(current_user, target_user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к данным другого пользователя",
        )
    try:
        from app.api.v1.endpoints import user_management

        service = user_management.get_user_management_service()
        profile_data = service.get_user_profile(db, user_id)

        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
            )

        return UserResponse(**profile_data)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


