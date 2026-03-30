#!/usr/bin/env python3
"""
Простой запуск сервера для диагностики
"""

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Запуск сервера...")
    print("URL: http://127.0.0.1:18000")
    print("Docs: http://127.0.0.1:18000/docs")
    print("Нажмите Ctrl+C для остановки")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=18000,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n✅ Сервер остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
