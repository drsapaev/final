"""
API Documentation endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.user import User
from typing import Dict, Any
import json

router = APIRouter()

@router.get("/api-docs", response_class=HTMLResponse)
async def get_api_docs():
    """Полная документация API с примерами"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Clinic Management System - API Documentation</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .endpoint { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            .method { font-weight: bold; color: #007bff; }
            .path { font-family: monospace; background: #f8f9fa; padding: 5px; }
            .description { margin: 10px 0; }
            .example { background: #f8f9fa; padding: 10px; border-radius: 3px; font-family: monospace; }
            h1, h2 { color: #333; }
            .auth { color: #dc3545; font-weight: bold; }
            .public { color: #28a745; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🏥 Clinic Management System - API Documentation</h1>
        
        <h2>📋 Аутентификация</h2>
        <div class="endpoint">
            <div class="method">POST</div>
            <div class="path">/api/v1/auth/login</div>
            <div class="description">Вход в систему</div>
            <div class="example">
                {
                    "username": "admin",
                    "password": "admin123"
                }
            </div>
        </div>

        <h2>👥 Пользователи</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/users/me</div>
            <div class="description">Получить информацию о текущем пользователе</div>
            <div class="auth">Требуется аутентификация</div>
        </div>

        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/users/</div>
            <div class="description">Получить список всех пользователей</div>
            <div class="auth">Требуется роль: Admin</div>
        </div>

        <h2>👤 Пациенты</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/patients/</div>
            <div class="description">Получить список пациентов</div>
            <div class="auth">Требуется аутентификация</div>
        </div>

        <div class="endpoint">
            <div class="method">POST</div>
            <div class="path">/api/v1/patients/</div>
            <div class="description">Создать нового пациента</div>
            <div class="example">
                {
                    "full_name": "Иван Иванов",
                    "phone": "+998901234567",
                    "birth_date": "1990-01-01",
                    "gender": "male"
                }
            </div>
        </div>

        <h2>🏥 Визиты</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/visits/</div>
            <div class="description">Получить список визитов</div>
            <div class="auth">Требуется аутентификация</div>
        </div>

        <div class="endpoint">
            <div class="method">POST</div>
            <div class="path">/api/v1/visits/</div>
            <div class="description">Создать новый визит</div>
            <div class="example">
                {
                    "patient_id": 1,
                    "service_id": 1,
                    "payment_amount": 100000,
                    "notes": "Консультация"
                }
            </div>
        </div>

        <h2>💳 Платежи</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/payments/</div>
            <div class="description">Получить список платежей</div>
            <div class="auth">Требуется аутентификация</div>
        </div>

        <div class="endpoint">
            <div class="method">POST</div>
            <div class="path">/api/v1/payments/</div>
            <div class="description">Создать новый платеж</div>
            <div class="example">
                {
                    "visit_id": 1,
                    "amount": 100000,
                    "provider": "payme",
                    "transaction_id": "txn_123456"
                }
            </div>
        </div>

        <h2>📊 Аналитика</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/analytics/payment-providers</div>
            <div class="description">Аналитика по провайдерам платежей</div>
            <div class="auth">Требуется роль: Admin, Doctor, Nurse</div>
        </div>

        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/analytics/appointment-flow</div>
            <div class="description">Аналитика потока записей</div>
            <div class="auth">Требуется роль: Admin, Doctor, Nurse</div>
        </div>

        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/analytics/revenue-breakdown</div>
            <div class="description">Детальная аналитика доходов</div>
            <div class="auth">Требуется роль: Admin, Doctor, Nurse</div>
        </div>

        <h2>🔔 Уведомления</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/notifications/templates</div>
            <div class="description">Получить шаблоны уведомлений</div>
            <div class="auth">Требуется аутентификация</div>
        </div>

        <div class="endpoint">
            <div class="method">POST</div>
            <div class="path">/api/v1/notifications/send</div>
            <div class="description">Отправить уведомление</div>
            <div class="example">
                {
                    "template_id": 1,
                    "recipient": "user@example.com",
                    "channel": "email",
                    "variables": {
                        "patient_name": "Иван Иванов",
                        "appointment_date": "2025-01-30"
                    }
                }
            </div>
        </div>

        <h2>⚙️ Настройки</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/settings/</div>
            <div class="description">Получить настройки системы</div>
            <div class="auth">Требуется роль: Admin</div>
        </div>

        <div class="endpoint">
            <div class="method">PUT</div>
            <div class="path">/api/v1/settings/</div>
            <div class="description">Обновить настройки системы</div>
            <div class="auth">Требуется роль: Admin</div>
        </div>

        <h2>🔐 Роли и права доступа</h2>
        <ul>
            <li><strong>Admin</strong> - полный доступ ко всем функциям</li>
            <li><strong>Doctor</strong> - доступ к пациентам, визитам, аналитике</li>
            <li><strong>Nurse</strong> - доступ к пациентам, визитам, аналитике</li>
            <li><strong>Registrar</strong> - доступ к пациентам и визитам</li>
            <li><strong>Cashier</strong> - доступ к платежам</li>
        </ul>

        <h2>📝 Коды ответов</h2>
        <ul>
            <li><strong>200</strong> - Успешный запрос</li>
            <li><strong>201</strong> - Ресурс создан</li>
            <li><strong>400</strong> - Неверный запрос</li>
            <li><strong>401</strong> - Не авторизован</li>
            <li><strong>403</strong> - Недостаточно прав</li>
            <li><strong>404</strong> - Ресурс не найден</li>
            <li><strong>422</strong> - Ошибка валидации</li>
            <li><strong>500</strong> - Внутренняя ошибка сервера</li>
        </ul>

        <h2>🔗 Полезные ссылки</h2>
        <ul>
            <li><a href="/docs">Swagger UI</a> - Интерактивная документация</li>
            <li><a href="/redoc">ReDoc</a> - Альтернативная документация</li>
            <li><a href="/api/v1/health">Health Check</a> - Проверка состояния API</li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/api-schema")
async def get_api_schema():
    """Получить JSON схему API"""
    schema = {
        "openapi": "3.0.0",
        "info": {
            "title": "Clinic Management System API",
            "description": "API для системы управления клиникой",
            "version": "1.0.0",
            "contact": {
                "name": "Clinic Management Team",
                "email": "admin@clinic.com"
            }
        },
        "servers": [
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ],
        "paths": {
            "/api/v1/auth/login": {
                "post": {
                    "summary": "Вход в систему",
                    "description": "Аутентификация пользователя",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "password": {"type": "string"}
                                    },
                                    "required": ["username", "password"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Успешная аутентификация",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "access_token": {"type": "string"},
                                            "token_type": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/v1/users/me": {
                "get": {
                    "summary": "Получить информацию о текущем пользователе",
                    "description": "Возвращает данные текущего авторизованного пользователя",
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Информация о пользователе",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "username": {"type": "string"},
                                            "email": {"type": "string"},
                                            "role": {"type": "string"},
                                            "is_active": {"type": "boolean"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        }
    }
    return schema

@router.get("/endpoints-summary")
async def get_endpoints_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить краткое описание всех эндпоинтов"""
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    summary = {
        "total_endpoints": 45,
        "categories": {
            "authentication": {
                "count": 3,
                "endpoints": ["/auth/login", "/auth/refresh", "/auth/logout"]
            },
            "users": {
                "count": 8,
                "endpoints": ["/users/", "/users/me", "/users/{id}", "/users/{id}/activate"]
            },
            "patients": {
                "count": 6,
                "endpoints": ["/patients/", "/patients/{id}", "/patients/search"]
            },
            "visits": {
                "count": 7,
                "endpoints": ["/visits/", "/visits/{id}", "/visits/patient/{patient_id}"]
            },
            "payments": {
                "count": 5,
                "endpoints": ["/payments/", "/payments/{id}", "/payments/webhook"]
            },
            "analytics": {
                "count": 3,
                "endpoints": ["/analytics/payment-providers", "/analytics/appointment-flow", "/analytics/revenue-breakdown"]
            },
            "notifications": {
                "count": 10,
                "endpoints": ["/notifications/templates", "/notifications/send", "/notifications/history"]
            },
            "settings": {
                "count": 3,
                "endpoints": ["/settings/", "/settings/{id}"]
            }
        },
        "authentication_required": 42,
        "public_endpoints": 3,
        "admin_only": 15,
        "doctor_nurse_access": 20
    }
    
    return summary
