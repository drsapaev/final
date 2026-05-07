# РџРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ (Backend/Frontend)

## Backend (`backend/.env`)
- `ENV` вЂ” РѕРєСЂСѓР¶РµРЅРёРµ: `dev|stage|prod`.
- `APP_NAME` / `APP_VERSION` вЂ” РјРµС‚Р°РґР°РЅРЅС‹Рµ РїСЂРёР»РѕР¶РµРЅРёСЏ.
- `API_V1_STR` вЂ” РїСЂРµС„РёРєСЃ API (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ `/api/v1`).
- `CORS_ALLOW_ALL` - local diagnostics only. Keep it `0` in `stage|prod`; configure explicit origins with `CORS_ORIGINS`.
- `CORS_ORIGINS` вЂ” CSV СЃРїРёСЃРѕРє РёСЃС‚РѕС‡РЅРёРєРѕРІ (РЅР°РїСЂРёРјРµСЂ, `http://localhost:5173,http://localhost:4173`).
- `DATABASE_URL` вЂ” СЃС‚СЂРѕРєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє PostgreSQL (Р»РѕРєР°Р»СЊРЅС‹Р№ РїСЂРёРјРµСЂ: `postgresql+psycopg://clinic:clinicpwd@localhost:5432/clinicdb`).
- `AUTH_SECRET` / `ACCESS_TOKEN_EXPIRE_MINUTES` / `AUTH_ALGORITHM` вЂ” РїР°СЂР°РјРµС‚СЂС‹ JWT.
- `CLINIC_LOGO_PATH` / `PDF_FOOTER_ENABLED` вЂ” РїРµС‡Р°С‚СЊ Рё PDF.
- `PRINTER_*` вЂ” РїР°СЂР°РјРµС‚СЂС‹ ESC/POS (С‚РёРї/СЃРµС‚СЊ/USB).
- `REQUIRE_LICENSE` вЂ” РІРєР»СЋС‡РёС‚СЊ Р»РёС†РµРЅР·РёРѕРЅРЅС‹Р№ СЂРµР¶РёРј.
- `LICENSE_ALLOW_HEALTH` вЂ” СЂР°Р·СЂРµС€РёС‚СЊ `/api/v1/health` РґРѕ Р°РєС‚РёРІР°С†РёРё.

## Frontend (`frontend/.env`)
- `VITE_APP_NAME` вЂ” РЅР°Р·РІР°РЅРёРµ РІ UI.
- `VITE_API_BASE` вЂ” Р±Р°Р·РѕРІС‹Р№ Р°РґСЂРµСЃ API (РЅР°РїСЂРёРјРµСЂ, `http://localhost:18000/api/v1`).

## Р‘С‹СЃС‚СЂС‹Р№ СЃС‚Р°СЂС‚ (Р»РѕРєР°Р»СЊРЅРѕ)
```bash
# Backend
cp backend/.env.example backend/.env
# РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё РѕС‚СЂРµРґР°РєС‚РёСЂСѓР№С‚Рµ Р·РЅР°С‡РµРЅРёСЏ
# uvicorn app.main:app --reload --port 18000  (РёР· РєР°С‚Р°Р»РѕРіР° backend)

# Frontend
cp frontend/.env.example frontend/.env
# npm install && npm run dev  (РёР· РєР°С‚Р°Р»РѕРіР° frontend)
