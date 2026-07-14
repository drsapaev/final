"""
Тест MCP endpoints для МКБ-10 и анализов
"""
import requests
import json
import os

def test_mcp_endpoints():
    """Тестируем MCP endpoints"""
    print("🔍 Тестирование MCP endpoints...")

    base_url = "http://localhost:18000/api/v1"
    mcp_password = os.getenv("QA_MCP_PASSWORD")
    if not mcp_password:
        print("Set QA_MCP_PASSWORD before running this legacy MCP smoke script.")
        return

    # Сначала получаем токен
    print("🔐 Получение токена авторизации...")

    try:
        auth_response = requests.post(
            f"{base_url}/auth/minimal-login",
            json={"username": os.getenv("QA_MCP_USERNAME", "mcp_test"), "password": mcp_password},
            headers={"Content-Type": "application/json"}
        )

        if auth_response.status_code != 200:
            print(f"❌ Ошибка авторизации: {auth_response.status_code}")
            print(f"Response: {auth_response.text}")
            return

        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        print("✅ Токен получен")

    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return

    # Тест 1: МКБ-10 подсказки
    print(f"\n🔍 ТЕСТ 1: MCP МКБ-10 подсказки")

    icd10_data = {
        "symptoms": ["головная боль", "тошнота", "светобоязнь"],
        "diagnosis": "Мигрень",
        "max_suggestions": 5
    }

    try:
        response = requests.post(
            f"{base_url}/mcp/icd10/suggest",
            json=icd10_data,
            headers=headers
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

        if response.status_code == 200:
            result = response.json()
            if "suggested_codes" in result and len(result["suggested_codes"]) > 0:
                print("✅ MCP МКБ-10 работает корректно")
            else:
                print("❌ MCP МКБ-10 возвращает пустой результат")
        else:
            print(f"❌ Ошибка MCP МКБ-10: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка запроса МКБ-10: {e}")

    # Тест 2: Интерпретация анализов
    print(f"\n🔍 ТЕСТ 2: MCP интерпретация анализов")

    lab_data = {
        "results": [
            {
                "name": "Гемоглобин",
                "value": "120",
                "unit": "г/л",
                "reference": "120-160"
            },
            {
                "name": "Лейкоциты",
                "value": "15.2",
                "unit": "×10⁹/л",
                "reference": "4.0-9.0"
            },
            {
                "name": "СОЭ",
                "value": "25",
                "unit": "мм/ч",
                "reference": "2-15"
            }
        ],
        "patient_age": 45,
        "patient_gender": "female",
        "include_recommendations": True
    }

    try:
        response = requests.post(
            f"{base_url}/mcp/lab/interpret",
            json=lab_data,
            headers=headers
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

        if response.status_code == 200:
            result = response.json()
            if "summary" in result and result["summary"]:
                print("✅ MCP интерпретация анализов работает корректно")
            else:
                print("❌ MCP интерпретация анализов возвращает пустой результат")
        else:
            print(f"❌ Ошибка MCP интерпретации: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка запроса интерпретации: {e}")

    # Тест 3: Поиск МКБ-10
    print(f"\n🔍 ТЕСТ 3: MCP поиск МКБ-10")

    try:
        response = requests.get(
            f"{base_url}/mcp/icd10/search?query=мигрень&limit=5",
            headers=headers
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

        if response.status_code == 200:
            result = response.json()
            if "results" in result and len(result["results"]) > 0:
                print("✅ MCP поиск МКБ-10 работает корректно")
            else:
                print("❌ MCP поиск МКБ-10 возвращает пустой результат")
        else:
            print(f"❌ Ошибка MCP поиска: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка запроса поиска: {e}")

if __name__ == "__main__":
    test_mcp_endpoints()
