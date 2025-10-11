#!/usr/bin/env python3
"""
Прямой тест DeepSeek API
"""
import httpx
import asyncio
import os
from dotenv import load_dotenv

# Загружаем .env
load_dotenv("backend/.env")

async def test_deepseek_api():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    
    print("=" * 60)
    print("🔍 ТЕСТ DEEPSEEK API")
    print("=" * 60)
    print(f"\n🔑 API Key: {api_key[:20]}..." if api_key else "❌ API Key не найден")
    
    if not api_key:
        print("\n❌ DEEPSEEK_API_KEY не установлен!")
        return
    
    # Пробуем разные URL
    urls_to_test = [
        "https://api.deepseek.com/v1/chat/completions",
        "https://api.deepseek.com/chat/completions",
        "https://api.deepseek.ai/v1/chat/completions",
    ]
    
    for base_url in urls_to_test:
        print(f"\n🌐 Тестирование URL: {base_url}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": "Hello, test message"}
            ],
            "max_tokens": 100
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    base_url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                print(f"   Status Code: {response.status_code}")
                print(f"   Response Headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Успех! Ответ: {data.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:100]}")
                    return True
                elif response.status_code == 402:
                    print(f"   ❌ 402 Payment Required")
                    print(f"   Response: {response.text[:500]}")
                elif response.status_code == 401:
                    print(f"   ❌ 401 Unauthorized - Неверный API ключ")
                    print(f"   Response: {response.text[:500]}")
                else:
                    print(f"   ❌ Ошибка: {response.status_code}")
                    print(f"   Response: {response.text[:500]}")
                    
        except httpx.TimeoutException:
            print(f"   ❌ Timeout - URL недоступен")
        except Exception as e:
            print(f"   ❌ Ошибка: {str(e)}")
    
    print("\n" + "=" * 60)
    print("❌ Все попытки подключения к DeepSeek API не удались")
    print("=" * 60)
    print("\n💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
    print("1. DeepSeek временно приостановил бесплатные кредиты")
    print("2. Нужно пополнить баланс на https://platform.deepseek.com")
    print("3. API ключ неверный или не активирован")
    print("4. Требуется верификация аккаунта")
    print("\n💡 РЕШЕНИЕ:")
    print("✅ Используйте Gemini AI - бесплатный и работает отлично!")
    print("   Система уже настроена на Gemini как основной провайдер")
    
    return False

if __name__ == "__main__":
    asyncio.run(test_deepseek_api())

