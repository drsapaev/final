import asyncio
import httpx
import time
import sys

async def test_endpoint(client, endpoint):
    try:
        response = await client.get(f"http://127.0.0.1:8000{endpoint}")
        return response.status_code, float(response.elapsed.total_seconds()) if hasattr(response, 'elapsed') else 0.1
    except Exception as e:
        print(f"❌ Ошибка запроса к {endpoint}: {e}")
        return 500, 0

async def load_test():
    endpoints = [
        "/api/v1/health",
        "/api/v1/status"
    ]
    
    print(f"🚀 Тестируем {len(endpoints)} эндпоинтов")
    print(f"📊 Количество запросов: 10")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            
            tasks = []
            for _ in range(10):
                for endpoint in endpoints:
                    task = test_endpoint(client, endpoint)
                    tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            successful_requests = sum(1 for status, _ in results if status == 200)
            
            print(f"\n📊 РЕЗУЛЬТАТЫ:")
            print(f"⏱️  Общее время: {total_time:.2f} секунд")
            print(f"✅ Успешных запросов: {successful_requests}")
            print(f"📈 Успешность: {(successful_requests/len(results)*100):.1f}%")
            
            if successful_requests >= len(results) * 0.8:
                print(f"\n🎉 ТЕСТ ПРОЙДЕН: Хорошая производительность!")
                return True
            else:
                print(f"\n❌ ТЕСТ НЕ ПРОЙДЕН: Успешность {successful_requests/len(results)*100:.1f}% < 80%")
                return False
                
    except Exception as e:
        print(f"❌ Критическая ошибка при нагрузочном тестировании: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(load_test())
    sys.exit(0 if result else 1)
