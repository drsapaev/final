#!/usr/bin/env python3
"""
Интеграционное тестирование API endpoints
Тестирует основные функции: password-reset, phone-verification, queue-reorder, AI, FCM, Telegram
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Any, List

class APIIntegrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.auth_token = None
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_endpoint(self, method: str, endpoint: str, data: Dict = None, 
                          headers: Dict = None, expected_status: int = 200,
                          test_name: str = None) -> Dict[str, Any]:
        """Тестирует один endpoint"""
        url = f"{self.base_url}{endpoint}"
        
        if headers is None:
            headers = {}
            
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
            
        start_time = time.time()
        
        try:
            async with self.session.request(method, url, json=data, headers=headers) as response:
                response_time = time.time() - start_time
                response_data = None
                
                try:
                    response_data = await response.json()
                except:
                    response_data = await response.text()
                
                result = {
                    'test_name': test_name or f"{method} {endpoint}",
                    'endpoint': endpoint,
                    'method': method,
                    'status_code': response.status,
                    'expected_status': expected_status,
                    'response_time': round(response_time, 3),
                    'success': response.status == expected_status,
                    'response_data': response_data,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.test_results.append(result)
                return result
                
        except Exception as e:
            result = {
                'test_name': test_name or f"{method} {endpoint}",
                'endpoint': endpoint,
                'method': method,
                'status_code': 0,
                'expected_status': expected_status,
                'response_time': time.time() - start_time,
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
            self.test_results.append(result)
            return result

    async def authenticate(self):
        """Получает токен авторизации для тестов"""
        print("🔐 Попытка авторизации...")
        
        # Пробуем создать тестового пользователя
        test_user = {
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        # Регистрация (может не сработать если пользователь уже существует)
        await self.test_endpoint("POST", "/api/v1/auth/register", test_user, 
                                expected_status=201, test_name="Регистрация тестового пользователя")
        
        # Авторизация
        login_data = {
            "username": test_user["email"],
            "password": test_user["password"]
        }
        
        result = await self.test_endpoint("POST", "/api/v1/auth/login", login_data,
                                        test_name="Авторизация")
        
        if result['success'] and isinstance(result['response_data'], dict):
            self.auth_token = result['response_data'].get('access_token')
            if self.auth_token:
                print(f"✅ Авторизация успешна, токен получен")
            else:
                print("⚠️ Авторизация прошла, но токен не получен")
        else:
            print("❌ Ошибка авторизации")

    async def test_password_reset(self):
        """Тестирует функционал сброса пароля"""
        print("\n📧 Тестирование сброса пароля...")
        
        # Инициация сброса по email
        await self.test_endpoint("POST", "/api/v1/password-reset/initiate", 
                                {"email": "test@example.com", "method": "email"},
                                test_name="Инициация сброса пароля по email")
        
        # Инициация сброса по телефону
        await self.test_endpoint("POST", "/api/v1/password-reset/initiate",
                                {"phone": "+998901234567", "method": "phone"},
                                test_name="Инициация сброса пароля по телефону")
        
        # Проверка статуса сброса
        await self.test_endpoint("GET", "/api/v1/password-reset/status/test@example.com",
                                test_name="Проверка статуса сброса пароля")

    async def test_phone_verification(self):
        """Тестирует верификацию телефона"""
        print("\n📱 Тестирование верификации телефона...")
        
        # Отправка кода верификации
        await self.test_endpoint("POST", "/api/v1/phone-verification/send-code",
                                {"phone": "+998901234567", "purpose": "registration"},
                                test_name="Отправка кода верификации")
        
        # Проверка кода (с неверным кодом)
        await self.test_endpoint("POST", "/api/v1/phone-verification/verify-code",
                                {"phone": "+998901234567", "code": "123456"},
                                expected_status=400,
                                test_name="Проверка неверного кода")
        
        # Статистика верификации
        await self.test_endpoint("GET", "/api/v1/phone-verification/stats",
                                test_name="Статистика верификации телефона")

    async def test_queue_reorder(self):
        """Тестирует изменение порядка очереди"""
        print("\n🔄 Тестирование изменения порядка очереди...")
        
        # Получение статуса очереди
        await self.test_endpoint("GET", "/api/v1/queue-reorder/status/by-specialist/1",
                                test_name="Получение статуса очереди по специалисту")
        
        # Попытка изменения порядка (может не сработать без реальных данных)
        await self.test_endpoint("POST", "/api/v1/queue-reorder/move-entry",
                                {"queue_id": 1, "entry_id": 1, "new_position": 2},
                                expected_status=404,  # Ожидаем 404 если нет данных
                                test_name="Изменение позиции в очереди")

    async def test_ai_functions(self):
        """Тестирует AI функции"""
        print("\n🤖 Тестирование AI функций...")
        
        # Диагностика симптомов
        symptoms_data = {
            "symptoms": ["головная боль", "температура", "слабость"],
            "patient_age": 30,
            "patient_gender": "female"
        }
        await self.test_endpoint("POST", "/api/v1/ai/diagnose-symptoms", symptoms_data,
                                test_name="AI диагностика симптомов")
        
        # Анализ медицинского изображения (без файла - ожидаем ошибку)
        await self.test_endpoint("POST", "/api/v1/ai/analyze-medical-image",
                                {"image_type": "xray", "description": "chest xray"},
                                expected_status=422,
                                test_name="AI анализ изображения (без файла)")
        
        # Проверка лекарственных взаимодействий
        drugs_data = {
            "medications": ["аспирин", "парацетамол"],
            "patient_age": 30,
            "patient_conditions": ["гипертония"]
        }
        await self.test_endpoint("POST", "/api/v1/ai/check-drug-interactions", drugs_data,
                                test_name="AI проверка взаимодействий лекарств")

    async def test_fcm_notifications(self):
        """Тестирует FCM уведомления"""
        print("\n🔔 Тестирование FCM уведомлений...")
        
        # Отправка уведомления
        notification_data = {
            "token": "test_fcm_token",
            "title": "Тестовое уведомление",
            "body": "Это тестовое push уведомление",
            "data": {"test": "true"}
        }
        await self.test_endpoint("POST", "/api/v1/fcm/send-notification", notification_data,
                                test_name="Отправка FCM уведомления")
        
        # Подписка на топик
        await self.test_endpoint("POST", "/api/v1/fcm/subscribe-to-topic",
                                {"token": "test_fcm_token", "topic": "test_topic"},
                                test_name="Подписка на FCM топик")
        
        # Статистика FCM
        await self.test_endpoint("GET", "/api/v1/fcm/stats",
                                test_name="Статистика FCM")

    async def test_telegram_bot(self):
        """Тестирует Telegram бот"""
        print("\n📱 Тестирование Telegram бота...")
        
        # Отправка уведомления
        telegram_data = {
            "chat_id": "123456789",
            "message": "Тестовое сообщение от бота",
            "parse_mode": "HTML"
        }
        await self.test_endpoint("POST", "/api/v1/telegram-bot/send-notification", telegram_data,
                                test_name="Отправка Telegram уведомления")
        
        # Настройки бота
        await self.test_endpoint("GET", "/api/v1/telegram-bot/settings",
                                test_name="Получение настроек Telegram бота")
        
        # Статистика бота
        await self.test_endpoint("GET", "/api/v1/telegram-bot/stats",
                                test_name="Статистика Telegram бота")

    async def test_health_endpoints(self):
        """Тестирует основные health endpoints"""
        print("\n❤️ Тестирование health endpoints...")
        
        await self.test_endpoint("GET", "/health", test_name="Health check")
        await self.test_endpoint("GET", "/api/v1/health", test_name="API Health check")
        await self.test_endpoint("GET", "/docs", test_name="API Documentation")

    async def run_all_tests(self):
        """Запускает все тесты"""
        print("🚀 Начинаем интеграционное тестирование API endpoints...\n")
        
        # Базовые проверки
        await self.test_health_endpoints()
        
        # Авторизация
        await self.authenticate()
        
        # Основные тесты
        await self.test_password_reset()
        await self.test_phone_verification()
        await self.test_queue_reorder()
        await self.test_ai_functions()
        await self.test_fcm_notifications()
        await self.test_telegram_bot()
        
        # Генерация отчета
        self.generate_report()

    def generate_report(self):
        """Генерирует отчет о тестировании"""
        print("\n" + "="*80)
        print("📊 ОТЧЕТ О ИНТЕГРАЦИОННОМ ТЕСТИРОВАНИИ")
        print("="*80)
        
        total_tests = len(self.test_results)
        successful_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - successful_tests
        
        print(f"Всего тестов: {total_tests}")
        print(f"Успешных: {successful_tests}")
        print(f"Неудачных: {failed_tests}")
        print(f"Процент успеха: {(successful_tests/total_tests)*100:.1f}%")
        
        avg_response_time = sum(r['response_time'] for r in self.test_results) / total_tests
        print(f"Среднее время ответа: {avg_response_time:.3f}s")
        
        print("\n📋 Детальные результаты:")
        print("-" * 80)
        
        for result in self.test_results:
            status_icon = "✅" if result['success'] else "❌"
            print(f"{status_icon} {result['test_name']}")
            print(f"   {result['method']} {result['endpoint']}")
            print(f"   Статус: {result['status_code']} (ожидался {result['expected_status']})")
            print(f"   Время: {result['response_time']}s")
            
            if not result['success']:
                if 'error' in result:
                    print(f"   Ошибка: {result['error']}")
                elif 'response_data' in result:
                    print(f"   Ответ: {result['response_data']}")
            print()
        
        # Сохранение отчета в файл
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'failed_tests': failed_tests,
                'success_rate': (successful_tests/total_tests)*100,
                'avg_response_time': avg_response_time
            },
            'results': self.test_results
        }
        
        with open('integration_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"📄 Подробный отчет сохранен в: integration_test_report.json")
        
        if failed_tests > 0:
            print(f"\n⚠️ Обнаружены проблемы в {failed_tests} тестах. Требуется внимание!")
        else:
            print(f"\n🎉 Все тесты прошли успешно!")

async def main():
    """Основная функция"""
    async with APIIntegrationTester() as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())

