"""
Пошаговая инструкция для получения Google Gemini API ключа
"""
import webbrowser

def get_gemini_api_key():
    """Инструкция по получению Gemini API ключа"""
    print("🔑 ПОШАГОВАЯ ИНСТРУКЦИЯ ПОЛУЧЕНИЯ GEMINI API КЛЮЧА")
    print("=" * 60)
    
    print("\n📋 ШАГ 1: Перейдите на сайт Google AI Studio")
    print("   URL: https://makersuite.google.com/app/apikey")
    print("   (Откроется автоматически)")
    
    # Открываем браузер
    try:
        webbrowser.open("https://makersuite.google.com/app/apikey")
        print("   ✅ Браузер открыт")
    except:
        print("   ⚠️ Не удалось открыть браузер автоматически")
        print("   📝 Откройте ссылку вручную: https://makersuite.google.com/app/apikey")
    
    print("\n📋 ШАГ 2: Войдите в Google аккаунт")
    print("   • Используйте любой Google аккаунт")
    print("   • Если нет аккаунта - создайте бесплатный")
    
    print("\n📋 ШАГ 3: Создайте API ключ")
    print("   • Нажмите 'Create API Key'")
    print("   • Выберите проект (или создайте новый)")
    print("   • Скопируйте созданный ключ")
    
    print("\n📋 ШАГ 4: Настройте ключ в проекте")
    print("   • Создайте файл backend/.env")
    print("   • Добавьте строку: GEMINI_API_KEY=ваш_ключ_здесь")
    print("   • Перезапустите backend сервер")
    
    print("\n💡 ПРЕИМУЩЕСТВА GEMINI:")
    print("   ✅ Бесплатный (до 15 запросов в минуту)")
    print("   ✅ Хорошее качество для медицинских задач")
    print("   ✅ Поддержка русского языка")
    print("   ✅ Быстрая обработка")
    
    print("\n⚠️ ВАЖНО:")
    print("   • Не делитесь API ключом публично")
    print("   • Добавьте backend/.env в .gitignore")
    print("   • Ключ начинается с 'AIza...'")
    
    print("\n🎯 СЛЕДУЮЩИЕ ШАГИ:")
    print("   1. Получите API ключ по ссылке выше")
    print("   2. Создайте файл backend/.env с ключом")
    print("   3. Запустите скрипт настройки")
    print("   4. Перезапустите backend сервер")
    print("   5. Протестируйте MCP с реальными результатами!")

if __name__ == "__main__":
    get_gemini_api_key()
