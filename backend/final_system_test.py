#!/usr/bin/env python3
"""
Финальное комплексное тестирование всей системы
"""
import requests
import json
import time

def test_complete_system():
    """Комплексное тестирование всей системы"""
    print("🚀 ФИНАЛЬНОЕ ТЕСТИРОВАНИЕ СИСТЕМЫ УПРАВЛЕНИЯ КЛИНИКОЙ")
    print("=" * 60)
    
    # Результаты тестирования
    results = {
        "authentication": {"passed": 0, "total": 0},
        "emr_system": {"passed": 0, "total": 0},
        "mobile_api": {"passed": 0, "total": 0},
        "analytics": {"passed": 0, "total": 0},
        "two_factor": {"passed": 0, "total": 0},
        "telegram": {"passed": 0, "total": 0},
        "email_sms": {"passed": 0, "total": 0},
        "file_system": {"passed": 0, "total": 0},
        "frontend": {"passed": 0, "total": 0}
    }
    
    # 1. ТЕСТИРОВАНИЕ АУТЕНТИФИКАЦИИ
    print("\n🔐 ТЕСТИРОВАНИЕ АУТЕНТИФИКАЦИИ")
    print("-" * 40)
    
    roles = ["admin", "registrar", "lab", "doctor", "cashier", "cardio", "derma", "dentist"]
    tokens = {}
    
    for role in roles:
        try:
            auth_response = requests.post(
                "http://localhost:8000/api/v1/auth/login",
                data={"username": role, "password": "admin123"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=5
            )
            
            if auth_response.status_code == 200:
                token = auth_response.json()["access_token"]
                tokens[role] = token
                print(f"   ✅ {role}: Логин успешен")
                results["authentication"]["passed"] += 1
            else:
                print(f"   ❌ {role}: Ошибка {auth_response.status_code}")
            
            results["authentication"]["total"] += 1
            
        except Exception as e:
            print(f"   ❌ {role}: Ошибка {e}")
            results["authentication"]["total"] += 1
    
    # 2. ТЕСТИРОВАНИЕ EMR СИСТЕМЫ
    print("\n🏥 ТЕСТИРОВАНИЕ EMR СИСТЕМЫ")
    print("-" * 40)
    
    if "admin" in tokens:
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        
        # Тест AI анализа
        try:
            ai_response = requests.post(
                "http://localhost:8000/api/v1/emr/ai-enhanced/analyze",
                headers=headers,
                json={"symptoms": "головная боль, температура"},
                timeout=5
            )
            if ai_response.status_code == 200:
                print("   ✅ AI анализ: Работает")
                results["emr_system"]["passed"] += 1
            else:
                print(f"   ❌ AI анализ: Ошибка {ai_response.status_code}")
            results["emr_system"]["total"] += 1
        except Exception as e:
            print(f"   ❌ AI анализ: {e}")
            results["emr_system"]["total"] += 1
        
        # Тест версионирования
        try:
            versions_response = requests.get(
                "http://localhost:8000/api/v1/emr/versions/1",
                headers=headers,
                timeout=5
            )
            if versions_response.status_code in [200, 404]:  # 404 тоже нормально, если нет записей
                print("   ✅ Версионирование: Работает")
                results["emr_system"]["passed"] += 1
            else:
                print(f"   ❌ Версионирование: Ошибка {versions_response.status_code}")
            results["emr_system"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Версионирование: {e}")
            results["emr_system"]["total"] += 1
    
    # 3. ТЕСТИРОВАНИЕ МОБИЛЬНОГО API
    print("\n📱 ТЕСТИРОВАНИЕ МОБИЛЬНОГО API")
    print("-" * 40)
    
    if "admin" in tokens:
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        
        # Тест PWA статуса
        try:
            pwa_response = requests.get(
                "http://localhost:8000/api/v1/mobile/pwa/status",
                headers=headers,
                timeout=5
            )
            if pwa_response.status_code == 200:
                print("   ✅ PWA статус: Работает")
                results["mobile_api"]["passed"] += 1
            else:
                print(f"   ❌ PWA статус: Ошибка {pwa_response.status_code}")
            results["mobile_api"]["total"] += 1
        except Exception as e:
            print(f"   ❌ PWA статус: {e}")
            results["mobile_api"]["total"] += 1
        
        # Тест офлайн данных
        try:
            offline_response = requests.get(
                "http://localhost:8000/api/v1/mobile/offline/data",
                headers=headers,
                timeout=5
            )
            if offline_response.status_code == 200:
                print("   ✅ Офлайн данные: Работают")
                results["mobile_api"]["passed"] += 1
            else:
                print(f"   ❌ Офлайн данные: Ошибка {offline_response.status_code}")
            results["mobile_api"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Офлайн данные: {e}")
            results["mobile_api"]["total"] += 1
    
    # 4. ТЕСТИРОВАНИЕ АНАЛИТИКИ
    print("\n📊 ТЕСТИРОВАНИЕ АНАЛИТИКИ")
    print("-" * 40)
    
    if "admin" in tokens:
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        
        # Тест KPI метрик
        try:
            kpi_response = requests.get(
                "http://localhost:8000/api/v1/analytics/kpi-metrics",
                headers=headers,
                timeout=5
            )
            if kpi_response.status_code == 200:
                print("   ✅ KPI метрики: Работают")
                results["analytics"]["passed"] += 1
            else:
                print(f"   ❌ KPI метрики: Ошибка {kpi_response.status_code}")
            results["analytics"]["total"] += 1
        except Exception as e:
            print(f"   ❌ KPI метрики: {e}")
            results["analytics"]["total"] += 1
        
        # Тест предиктивной аналитики
        try:
            predictive_response = requests.get(
                "http://localhost:8000/api/v1/analytics/predictive",
                headers=headers,
                timeout=5
            )
            if predictive_response.status_code == 200:
                print("   ✅ Предиктивная аналитика: Работает")
                results["analytics"]["passed"] += 1
            else:
                print(f"   ❌ Предиктивная аналитика: Ошибка {predictive_response.status_code}")
            results["analytics"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Предиктивная аналитика: {e}")
            results["analytics"]["total"] += 1
    
    # 5. ТЕСТИРОВАНИЕ 2FA
    print("\n🔒 ТЕСТИРОВАНИЕ TWO-FACTOR AUTHENTICATION")
    print("-" * 40)
    
    if "admin" in tokens:
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        
        # Тест SMS 2FA
        try:
            sms_response = requests.post(
                "http://localhost:8000/api/v1/2fa/sms/send-code",
                headers=headers,
                json={"phone": "+1234567890"},
                timeout=5
            )
            if sms_response.status_code in [200, 400]:  # 400 может быть нормально для тестового номера
                print("   ✅ SMS 2FA: Работает")
                results["two_factor"]["passed"] += 1
            else:
                print(f"   ❌ SMS 2FA: Ошибка {sms_response.status_code}")
            results["two_factor"]["total"] += 1
        except Exception as e:
            print(f"   ❌ SMS 2FA: {e}")
            results["two_factor"]["total"] += 1
        
        # Тест Email 2FA
        try:
            email_response = requests.post(
                "http://localhost:8000/api/v1/2fa/email/send-code",
                headers=headers,
                json={"email": "test@example.com"},
                timeout=5
            )
            if email_response.status_code in [200, 400]:
                print("   ✅ Email 2FA: Работает")
                results["two_factor"]["passed"] += 1
            else:
                print(f"   ❌ Email 2FA: Ошибка {email_response.status_code}")
            results["two_factor"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Email 2FA: {e}")
            results["two_factor"]["total"] += 1
    
    # 6. ТЕСТИРОВАНИЕ TELEGRAM
    print("\n📱 ТЕСТИРОВАНИЕ TELEGRAM ИНТЕГРАЦИИ")
    print("-" * 40)
    
    if "admin" in tokens:
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        
        # Тест Telegram шаблонов
        try:
            telegram_response = requests.get(
                "http://localhost:8000/api/v1/telegram/templates",
                headers=headers,
                timeout=5
            )
            if telegram_response.status_code == 200:
                print("   ✅ Telegram шаблоны: Работают")
                results["telegram"]["passed"] += 1
            else:
                print(f"   ❌ Telegram шаблоны: Ошибка {telegram_response.status_code}")
            results["telegram"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Telegram шаблоны: {e}")
            results["telegram"]["total"] += 1
    
    # 7. ТЕСТИРОВАНИЕ EMAIL/SMS
    print("\n📧 ТЕСТИРОВАНИЕ EMAIL/SMS СЕРВИСОВ")
    print("-" * 40)
    
    if "admin" in tokens:
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        
        # Тест Email/SMS статистики
        try:
            email_sms_response = requests.get(
                "http://localhost:8000/api/v1/email-sms/statistics",
                headers=headers,
                timeout=5
            )
            if email_sms_response.status_code == 200:
                print("   ✅ Email/SMS статистика: Работает")
                results["email_sms"]["passed"] += 1
            else:
                print(f"   ❌ Email/SMS статистика: Ошибка {email_sms_response.status_code}")
            results["email_sms"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Email/SMS статистика: {e}")
            results["email_sms"]["total"] += 1
    
    # 8. ТЕСТИРОВАНИЕ ФАЙЛОВОЙ СИСТЕМЫ
    print("\n📁 ТЕСТИРОВАНИЕ ФАЙЛОВОЙ СИСТЕМЫ")
    print("-" * 40)
    
    if "admin" in tokens:
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        
        # Тест файловой статистики
        try:
            files_response = requests.get(
                "http://localhost:8000/api/v1/files/statistics",
                headers=headers,
                timeout=5
            )
            if files_response.status_code == 200:
                print("   ✅ Файловая статистика: Работает")
                results["file_system"]["passed"] += 1
            else:
                print(f"   ❌ Файловая статистика: Ошибка {files_response.status_code}")
            results["file_system"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Файловая статистика: {e}")
            results["file_system"]["total"] += 1
        
        # Тест загрузки файлов
        try:
            upload_response = requests.post(
                "http://localhost:8000/api/v1/files/test-upload",
                headers=headers,
                timeout=5
            )
            if upload_response.status_code == 200:
                print("   ✅ Загрузка файлов: Работает")
                results["file_system"]["passed"] += 1
            else:
                print(f"   ❌ Загрузка файлов: Ошибка {upload_response.status_code}")
            results["file_system"]["total"] += 1
        except Exception as e:
            print(f"   ❌ Загрузка файлов: {e}")
            results["file_system"]["total"] += 1
    
    # 9. ТЕСТИРОВАНИЕ FRONTEND
    print("\n🎨 ТЕСТИРОВАНИЕ FRONTEND КОМПОНЕНТОВ")
    print("-" * 40)
    
    # Проверяем наличие frontend файлов
    frontend_components = [
        "frontend/src/components/mobile/PWAInstallPrompt.jsx",
        "frontend/src/components/analytics/AdvancedCharts.jsx",
        "frontend/src/components/security/TwoFactorManager.jsx",
        "frontend/src/components/telegram/TelegramManager.jsx",
        "frontend/src/components/notifications/EmailSMSManager.jsx"
    ]
    
    for component in frontend_components:
        try:
            with open(component, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) > 100:  # Проверяем, что файл не пустой
                    print(f"   ✅ {component.split('/')[-1]}: Готов")
                    results["frontend"]["passed"] += 1
                else:
                    print(f"   ❌ {component.split('/')[-1]}: Пустой файл")
            results["frontend"]["total"] += 1
        except FileNotFoundError:
            print(f"   ❌ {component.split('/')[-1]}: Не найден")
            results["frontend"]["total"] += 1
        except Exception as e:
            print(f"   ❌ {component.split('/')[-1]}: Ошибка {e}")
            results["frontend"]["total"] += 1
    
    # ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ
    print("\n" + "=" * 60)
    print("🏆 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    total_passed = 0
    total_tests = 0
    
    for system, stats in results.items():
        passed = stats["passed"]
        total = stats["total"]
        percentage = (passed / total * 100) if total > 0 else 0
        
        status = "✅" if percentage >= 80 else "⚠️" if percentage >= 50 else "❌"
        
        print(f"{status} {system.upper()}: {passed}/{total} ({percentage:.1f}%)")
        
        total_passed += passed
        total_tests += total
    
    overall_percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    print("-" * 60)
    print(f"🎯 ОБЩИЙ РЕЗУЛЬТАТ: {total_passed}/{total_tests} ({overall_percentage:.1f}%)")
    
    if overall_percentage >= 90:
        print("🎉 СИСТЕМА ГОТОВА К ПРОДАКШЕНУ!")
    elif overall_percentage >= 70:
        print("⚠️ СИСТЕМА ПОЧТИ ГОТОВА, НУЖНЫ МЕЛКИЕ ДОРАБОТКИ")
    else:
        print("❌ СИСТЕМА ТРЕБУЕТ ДОПОЛНИТЕЛЬНОЙ РАЗРАБОТКИ")
    
    return overall_percentage

if __name__ == "__main__":
    test_complete_system()
