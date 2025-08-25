// РџСЂРѕСЃС‚С‹Рµ РІСЂР°РїРїРµСЂС‹ РІРѕРєСЂСѓРі client.js РґР»СЏ РµРґРёРЅРѕРѕР±СЂР°Р·РёСЏ РёРјРїРѕСЂС‚Р°
import { login as _login, me as _me } from "./client";

export async function loginPassword({ username, password }) {
  return _login({ username, password });
}

export async function getProfile() {
  return _me();
}

