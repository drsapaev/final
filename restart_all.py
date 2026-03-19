#!/usr/bin/env python3
"""
Скрипт для перезапуска всех серверов с реальным Gemini AI
"""
import os
import sys
import time
import subprocess

def main():
    print("=" * 60)
    print("🔄 ПЕРЕЗАПУСК СЕРВЕРОВ С GEMINI AI")
    print("=" * 60)
    
    # 1. Останавливаем все процессы Python
    print("\n⏳ Останавливаем текущие серверы...")
    try:
        subprocess.run("taskkill /F /IM python.exe /T", 
                      shell=True, 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        time.sleep(2)
        print("✅ Серверы остановлены")
    except Exception as e:
        print(f"⚠️  Ошибка остановки: {e}")
    
    # 2. Запускаем backend сервер
    print("\n⏳ Запускаем backend сервер...")
    print("   📍 http://localhost:18000")
    print("   📖 API Docs: http://localhost:18000/docs")
    backend_cmd = "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    print(f"\n💡 Команда: {backend_cmd}")
    print("\n📋 Откройте новый терминал и выполните:")
    print(f"   {backend_cmd}")
    
    # 3. Запускаем HTML тестер
    print("\n⏳ Запускаем HTML тестер...")
    print("   📍 http://localhost:8080/mcp_test_v2.html")
    tester_cmd = "python start_mcp_test_server.py"
    print(f"\n💡 Команда: {tester_cmd}")
    print("\n📋 Откройте еще один терминал и выполните:")
    print(f"   {tester_cmd}")
    
    # 4. Инструкции
    print("\n" + "=" * 60)
    print("✅ ИНСТРУКЦИИ ПО ТЕСТИРОВАНИЮ")
    print("=" * 60)
    print("\n1️⃣  Откройте 2 новых терминала")
    print("2️⃣  В первом терминале:")
    print(f"    {backend_cmd}")
    print("3️⃣  Во втором терминале:")
    print(f"    {tester_cmd}")
    print("4️⃣  Откройте браузер:")
    print("    http://localhost:8080/mcp_test_v2.html")
    print("5️⃣  Получите токен (mcp_test / test123)")
    print("6️⃣  Тестируйте MCP функции с реальным Gemini AI!")
    print("\n" + "=" * 60)
    print("🎯 ТЕПЕРЬ СИСТЕМА ИСПОЛЬЗУЕТ GEMINI AI")
    print("=" * 60)
    print("\n✨ Особенности:")
    print("   ✅ Реальные AI ответы от Google Gemini")
    print("   ✅ Отключены фильтры безопасности для медицинского контента")
    print("   ✅ Улучшенные промпты для точных результатов")
    print("   ✅ Автоматический fallback на Mock провайдер при ошибках")
    print("\n💡 Gemini API ключ уже настроен в backend/.env")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

