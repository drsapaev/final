"""
Расширенная API документация с примерами и описаниями
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.user import User
from typing import Dict, Any, List, Optional
import json

router = APIRouter()

@router.get("/documentation/endpoints")
async def get_detailed_endpoints_documentation(
    category: Optional[str] = Query(None, description="Категория эндпоинтов"),
    current_user: User = Depends(get_current_user)
):
    """Получить детальную документацию по эндпоинтам"""
    
    documentation = {
        "authentication": {
            "description": "Эндпоинты для аутентификации и авторизации",
            "endpoints": {
                "POST /api/v1/auth/login": {
                    "description": "Вход в систему",
                    "request_body": {
                        "type": "form-data",
                        "fields": {
                            "username": {"type": "string", "required": True, "example": "admin"},
                            "password": {"type": "string", "required": True, "example": "admin123"}
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Успешная аутентификация",
                            "example": {
                                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                                "token_type": "bearer"
                            }
                        },
                        "401": {
                            "description": "Неверные учетные данные",
                            "example": {"detail": "Incorrect username or password"}
                        }
                    }
                },
                "POST /api/v1/auth/refresh": {
                    "description": "Обновление токена доступа",
                    "request_body": {
                        "type": "json",
                        "fields": {
                            "refresh_token": {"type": "string", "required": True}
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Токен обновлен",
                            "example": {
                                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                                "token_type": "bearer"
                            }
                        }
                    }
                }
            }
        },
        "users": {
            "description": "Управление пользователями системы",
            "endpoints": {
                "GET /api/v1/users/": {
                    "description": "Получить список всех пользователей",
                    "authorization": "Admin only",
                    "query_parameters": {
                        "skip": {"type": "integer", "default": 0, "description": "Количество пропускаемых записей"},
                        "limit": {"type": "integer", "default": 100, "description": "Максимальное количество записей"},
                        "role": {"type": "string", "description": "Фильтр по роли"}
                    },
                    "responses": {
                        "200": {
                            "description": "Список пользователей",
                            "example": [
                                {
                                    "id": 1,
                                    "username": "admin",
                                    "email": "admin@clinic.com",
                                    "role": "Admin",
                                    "is_active": True,
                                    "created_at": "2025-01-29T10:00:00Z"
                                }
                            ]
                        }
                    }
                },
                "GET /api/v1/users/me": {
                    "description": "Получить информацию о текущем пользователе",
                    "authorization": "Authenticated users",
                    "responses": {
                        "200": {
                            "description": "Информация о пользователе",
                            "example": {
                                "id": 1,
                                "username": "admin",
                                "email": "admin@clinic.com",
                                "role": "Admin",
                                "is_active": True
                            }
                        }
                    }
                },
                "POST /api/v1/users/": {
                    "description": "Создать нового пользователя",
                    "authorization": "Admin only",
                    "request_body": {
                        "type": "json",
                        "fields": {
                            "username": {"type": "string", "required": True, "example": "doctor1"},
                            "email": {"type": "string", "required": True, "example": "doctor@clinic.com"},
                            "password": {"type": "string", "required": True, "example": "password123"},
                            "role": {"type": "string", "required": True, "example": "Doctor"},
                            "is_active": {"type": "boolean", "default": True}
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Пользователь создан",
                            "example": {
                                "id": 2,
                                "username": "doctor1",
                                "email": "doctor@clinic.com",
                                "role": "Doctor",
                                "is_active": True
                            }
                        }
                    }
                }
            }
        },
        "patients": {
            "description": "Управление пациентами",
            "endpoints": {
                "GET /api/v1/patients/": {
                    "description": "Получить список пациентов",
                    "authorization": "Authenticated users",
                    "query_parameters": {
                        "skip": {"type": "integer", "default": 0},
                        "limit": {"type": "integer", "default": 100},
                        "search": {"type": "string", "description": "Поиск по имени или телефону"}
                    },
                    "responses": {
                        "200": {
                            "description": "Список пациентов",
                            "example": [
                                {
                                    "id": 1,
                                    "full_name": "Иван Иванов",
                                    "phone": "+998901234567",
                                    "birth_date": "1990-01-01",
                                    "gender": "male",
                                    "created_at": "2025-01-29T10:00:00Z"
                                }
                            ]
                        }
                    }
                },
                "POST /api/v1/patients/": {
                    "description": "Создать нового пациента",
                    "authorization": "Authenticated users",
                    "request_body": {
                        "type": "json",
                        "fields": {
                            "full_name": {"type": "string", "required": True, "example": "Иван Иванов"},
                            "phone": {"type": "string", "required": True, "example": "+998901234567"},
                            "birth_date": {"type": "string", "required": True, "example": "1990-01-01"},
                            "gender": {"type": "string", "required": True, "example": "male"},
                            "address": {"type": "string", "example": "Ташкент, ул. Навои, 1"},
                            "notes": {"type": "string", "example": "Аллергия на пенициллин"}
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Пациент создан",
                            "example": {
                                "id": 1,
                                "full_name": "Иван Иванов",
                                "phone": "+998901234567",
                                "birth_date": "1990-01-01",
                                "gender": "male"
                            }
                        }
                    }
                }
            }
        },
        "visits": {
            "description": "Управление визитами пациентов",
            "endpoints": {
                "GET /api/v1/visits/": {
                    "description": "Получить список визитов",
                    "authorization": "Authenticated users",
                    "query_parameters": {
                        "skip": {"type": "integer", "default": 0},
                        "limit": {"type": "integer", "default": 100},
                        "patient_id": {"type": "integer", "description": "Фильтр по пациенту"},
                        "status": {"type": "string", "description": "Фильтр по статусу"}
                    },
                    "responses": {
                        "200": {
                            "description": "Список визитов",
                            "example": [
                                {
                                    "id": 1,
                                    "patient_id": 1,
                                    "service_id": 1,
                                    "payment_amount": 100000,
                                    "status": "completed",
                                    "notes": "Консультация",
                                    "created_at": "2025-01-29T10:00:00Z"
                                }
                            ]
                        }
                    }
                },
                "POST /api/v1/visits/": {
                    "description": "Создать новый визит",
                    "authorization": "Authenticated users",
                    "request_body": {
                        "type": "json",
                        "fields": {
                            "patient_id": {"type": "integer", "required": True, "example": 1},
                            "service_id": {"type": "integer", "required": True, "example": 1},
                            "payment_amount": {"type": "number", "required": True, "example": 100000},
                            "notes": {"type": "string", "example": "Консультация"},
                            "status": {"type": "string", "default": "scheduled", "example": "scheduled"}
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Визит создан",
                            "example": {
                                "id": 1,
                                "patient_id": 1,
                                "service_id": 1,
                                "payment_amount": 100000,
                                "status": "scheduled"
                            }
                        }
                    }
                }
            }
        },
        "payments": {
            "description": "Управление платежами",
            "endpoints": {
                "GET /api/v1/payments/": {
                    "description": "Получить список платежей",
                    "authorization": "Authenticated users",
                    "query_parameters": {
                        "skip": {"type": "integer", "default": 0},
                        "limit": {"type": "integer", "default": 100},
                        "visit_id": {"type": "integer", "description": "Фильтр по визиту"},
                        "provider": {"type": "string", "description": "Фильтр по провайдеру"}
                    },
                    "responses": {
                        "200": {
                            "description": "Список платежей",
                            "example": [
                                {
                                    "id": 1,
                                    "visit_id": 1,
                                    "amount": 100000,
                                    "provider": "payme",
                                    "status": "success",
                                    "transaction_id": "txn_123456",
                                    "created_at": "2025-01-29T10:00:00Z"
                                }
                            ]
                        }
                    }
                },
                "POST /api/v1/payments/": {
                    "description": "Создать новый платеж",
                    "authorization": "Authenticated users",
                    "request_body": {
                        "type": "json",
                        "fields": {
                            "visit_id": {"type": "integer", "required": True, "example": 1},
                            "amount": {"type": "number", "required": True, "example": 100000},
                            "provider": {"type": "string", "required": True, "example": "payme"},
                            "transaction_id": {"type": "string", "example": "txn_123456"},
                            "status": {"type": "string", "default": "pending", "example": "pending"}
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Платеж создан",
                            "example": {
                                "id": 1,
                                "visit_id": 1,
                                "amount": 100000,
                                "provider": "payme",
                                "status": "pending"
                            }
                        }
                    }
                }
            }
        },
        "analytics": {
            "description": "Аналитика и отчеты",
            "endpoints": {
                "GET /api/v1/analytics/payment-providers": {
                    "description": "Аналитика по провайдерам платежей",
                    "authorization": "Admin, Doctor, Nurse",
                    "query_parameters": {
                        "start_date": {"type": "string", "description": "Начальная дата (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "Конечная дата (YYYY-MM-DD)"}
                    },
                    "responses": {
                        "200": {
                            "description": "Аналитика по провайдерам",
                            "example": {
                                "total_transactions": 150,
                                "total_amount": 15000000,
                                "providers": {
                                    "payme": {
                                        "count": 100,
                                        "amount": 10000000,
                                        "success_rate": 95.5
                                    }
                                }
                            }
                        }
                    }
                },
                "GET /api/v1/analytics/revenue-breakdown": {
                    "description": "Детальная аналитика доходов",
                    "authorization": "Admin, Doctor, Nurse",
                    "query_parameters": {
                        "start_date": {"type": "string", "description": "Начальная дата (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "Конечная дата (YYYY-MM-DD)"},
                        "department": {"type": "string", "description": "Фильтр по отделению"}
                    },
                    "responses": {
                        "200": {
                            "description": "Детальная аналитика доходов",
                            "example": {
                                "total_revenue": 15000000,
                                "total_transactions": 150,
                                "average_transaction": 100000,
                                "provider_breakdown": {
                                    "payme": {
                                        "count": 100,
                                        "total_amount": 10000000,
                                        "average_amount": 100000
                                    }
                                },
                                "daily_revenue": [
                                    {"date": "2025-01-29", "amount": 5000000}
                                ]
                            }
                        }
                    }
                }
            }
        },
        "notifications": {
            "description": "Система уведомлений",
            "endpoints": {
                "GET /api/v1/notifications/templates": {
                    "description": "Получить шаблоны уведомлений",
                    "authorization": "Authenticated users",
                    "responses": {
                        "200": {
                            "description": "Список шаблонов",
                            "example": [
                                {
                                    "id": 1,
                                    "name": "appointment_reminder",
                                    "type": "appointment",
                                    "channel": "email",
                                    "subject": "Напоминание о записи",
                                    "content": "Уважаемый {{patient_name}}, напоминаем о записи на {{appointment_date}}"
                                }
                            ]
                        }
                    }
                },
                "POST /api/v1/notifications/send": {
                    "description": "Отправить уведомление",
                    "authorization": "Authenticated users",
                    "request_body": {
                        "type": "json",
                        "fields": {
                            "template_id": {"type": "integer", "required": True, "example": 1},
                            "recipient": {"type": "string", "required": True, "example": "user@example.com"},
                            "channel": {"type": "string", "required": True, "example": "email"},
                            "variables": {"type": "object", "example": {"patient_name": "Иван Иванов"}}
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Уведомление отправлено",
                            "example": {
                                "id": 1,
                                "status": "sent",
                                "sent_at": "2025-01-29T10:00:00Z"
                            }
                        }
                    }
                }
            }
        }
    }
    
    if category:
        if category in documentation:
            return {category: documentation[category]}
        else:
            raise HTTPException(status_code=404, detail=f"Категория '{category}' не найдена")
    
    return documentation

@router.get("/documentation/examples")
async def get_api_examples(
    endpoint: Optional[str] = Query(None, description="Конкретный эндпоинт"),
    current_user: User = Depends(get_current_user)
):
    """Получить примеры использования API"""
    
    examples = {
        "authentication_examples": {
            "login": {
                "curl": "curl -X POST 'http://localhost:8000/api/v1/auth/login' -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin&password=admin123'",
                "python": """
import requests

response = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    data={'username': 'admin', 'password': 'admin123'}
)
token = response.json()['access_token']
                """,
                "javascript": """
const response = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'username=admin&password=admin123'
});
const data = await response.json();
const token = data.access_token;
                """
            }
        },
        "patient_examples": {
            "create_patient": {
                "curl": "curl -X POST 'http://localhost:8000/api/v1/patients/' -H 'Authorization: Bearer YOUR_TOKEN' -H 'Content-Type: application/json' -d '{\"full_name\": \"Иван Иванов\", \"phone\": \"+998901234567\", \"birth_date\": \"1990-01-01\", \"gender\": \"male\"}'",
                "python": """
import requests

headers = {'Authorization': f'Bearer {token}'}
data = {
    'full_name': 'Иван Иванов',
    'phone': '+998901234567',
    'birth_date': '1990-01-01',
    'gender': 'male'
}
response = requests.post(
    'http://localhost:8000/api/v1/patients/',
    headers=headers,
    json=data
)
                """,
                "javascript": """
const response = await fetch('http://localhost:8000/api/v1/patients/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        full_name: 'Иван Иванов',
        phone: '+998901234567',
        birth_date: '1990-01-01',
        gender: 'male'
    })
});
                """
            }
        },
        "visit_examples": {
            "create_visit": {
                "curl": "curl -X POST 'http://localhost:8000/api/v1/visits/' -H 'Authorization: Bearer YOUR_TOKEN' -H 'Content-Type: application/json' -d '{\"patient_id\": 1, \"service_id\": 1, \"payment_amount\": 100000, \"notes\": \"Консультация\"}'",
                "python": """
import requests

headers = {'Authorization': f'Bearer {token}'}
data = {
    'patient_id': 1,
    'service_id': 1,
    'payment_amount': 100000,
    'notes': 'Консультация'
}
response = requests.post(
    'http://localhost:8000/api/v1/visits/',
    headers=headers,
    json=data
)
                """,
                "javascript": """
const response = await fetch('http://localhost:8000/api/v1/visits/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        patient_id: 1,
        service_id: 1,
        payment_amount: 100000,
        notes: 'Консультация'
    })
});
                """
            }
        }
    }
    
    if endpoint:
        if endpoint in examples:
            return {endpoint: examples[endpoint]}
        else:
            raise HTTPException(status_code=404, detail=f"Примеры для эндпоинта '{endpoint}' не найдены")
    
    return examples

@router.get("/documentation/status-codes")
async def get_status_codes_documentation():
    """Получить документацию по кодам ответов"""
    
    status_codes = {
        "2xx_success": {
            "200": {
                "description": "OK - Запрос выполнен успешно",
                "example": "GET /api/v1/patients/ - получение списка пациентов"
            },
            "201": {
                "description": "Created - Ресурс создан успешно",
                "example": "POST /api/v1/patients/ - создание нового пациента"
            },
            "202": {
                "description": "Accepted - Запрос принят к обработке",
                "example": "POST /api/v1/notifications/send - отправка уведомления"
            }
        },
        "4xx_client_errors": {
            "400": {
                "description": "Bad Request - Неверный запрос",
                "example": "Отсутствуют обязательные поля в запросе"
            },
            "401": {
                "description": "Unauthorized - Не авторизован",
                "example": "Отсутствует или неверный токен авторизации"
            },
            "403": {
                "description": "Forbidden - Недостаточно прав",
                "example": "Пользователь не имеет прав для выполнения операции"
            },
            "404": {
                "description": "Not Found - Ресурс не найден",
                "example": "GET /api/v1/patients/999 - пациент с ID 999 не существует"
            },
            "422": {
                "description": "Unprocessable Entity - Ошибка валидации",
                "example": "Неверный формат данных в запросе"
            }
        },
        "5xx_server_errors": {
            "500": {
                "description": "Internal Server Error - Внутренняя ошибка сервера",
                "example": "Неожиданная ошибка в коде сервера"
            },
            "502": {
                "description": "Bad Gateway - Ошибка шлюза",
                "example": "Ошибка при обращении к внешнему сервису"
            },
            "503": {
                "description": "Service Unavailable - Сервис недоступен",
                "example": "Сервер временно недоступен для обслуживания"
            }
        }
    }
    
    return status_codes

@router.get("/documentation/authentication")
async def get_authentication_documentation():
    """Получить документацию по аутентификации"""
    
    auth_docs = {
        "overview": "API использует JWT (JSON Web Token) для аутентификации",
        "authentication_flow": {
            "step_1": "Отправьте POST запрос на /api/v1/auth/login с username и password",
            "step_2": "Получите access_token в ответе",
            "step_3": "Включайте токен в заголовок Authorization: Bearer <token> для всех защищенных запросов"
        },
        "token_format": {
            "header": "Authorization: Bearer <access_token>",
            "example": "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        },
        "token_expiration": {
            "access_token": "24 часа",
            "refresh_token": "7 дней"
        },
        "roles": {
            "Admin": "Полный доступ ко всем функциям системы",
            "Doctor": "Доступ к пациентам, визитам, аналитике",
            "Nurse": "Доступ к пациентам, визитам, аналитике",
            "Registrar": "Доступ к пациентам и визитам",
            "Cashier": "Доступ к платежам"
        },
        "security_notes": [
            "Всегда используйте HTTPS в продакшене",
            "Храните токены в безопасном месте",
            "Не передавайте токены в URL параметрах",
            "Регулярно обновляйте токены"
        ]
    }
    
    return auth_docs
