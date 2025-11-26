"""
Простой HTTP сервер для тестирования MCP API
"""
import http.server
import socketserver
import webbrowser
import os
import sys
from pathlib import Path

def start_test_server():
    """Запуск простого HTTP сервера для тестирования MCP"""
    
    # Определяем порт
    PORT = 8080
    
    # Определяем директорию с HTML файлом
    current_dir = Path(__file__).parent
    html_file = current_dir / "mcp_test.html"
    
    if not html_file.exists():
        print(f"❌ Файл {html_file} не найден!")
        return
    
    # Меняем директорию на родительскую, чтобы сервер мог обслуживать HTML файл
    os.chdir(current_dir)
    
    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            # Добавляем CORS заголовки
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            super().end_headers()
        
        def do_OPTIONS(self):
            # Обрабатываем OPTIONS запросы для CORS
            self.send_response(200)
            self.end_headers()
    
    try:
        with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
            print(f"🚀 MCP Test Server запущен на http://localhost:{PORT}")
            print(f"📄 HTML тестер доступен по адресу: http://localhost:{PORT}/mcp_test.html")
            print(f"🔧 Backend API: http://localhost:8000")
            print(f"🌐 Frontend: http://localhost:5173")
            print("\n" + "="*60)
            print("📋 ИНСТРУКЦИИ ДЛЯ ТЕСТИРОВАНИЯ:")
            print("="*60)
            print("1. Откройте http://localhost:8080/mcp_test.html в браузере")
            print("2. Получите токен авторизации (admin/admin)")
            print("3. Протестируйте все MCP endpoints")
            print("4. Проверьте результаты в консоли браузера")
            print("="*60)
            
            # Автоматически открываем браузер
            webbrowser.open(f"http://localhost:{PORT}/mcp_test.html")
            
            print(f"\n⏳ Сервер работает... Нажмите Ctrl+C для остановки")
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print(f"\n🛑 Сервер остановлен")
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"❌ Порт {PORT} уже используется. Попробуйте другой порт.")
        else:
            print(f"❌ Ошибка запуска сервера: {e}")

if __name__ == "__main__":
    start_test_server()
