import React, { useEffect, useState } from "react";
import RoleGate from "../components/RoleGate.jsx";
import { getApiBase } from "../api/client.js";
import { getHealth, getActivationStatus } from "../api/index.js";

export default function Health() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [act, setAct] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let mounted = true;
    async function load() {
      setErr("");
      setLoading(true);
      try {
        const [h, a] = await Promise.all([getHealth(), getActivationStatus()]);
        if (!mounted) return;
        setHealth(h);
        setAct(a);
      } catch (e) {
        if (!mounted) return;
        setErr(e?.data?.detail || e?.message || "Ошибка загрузки");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, []);

  return (
    <div>
      <main className="p-4 max-w-5xl mx-auto">
        <h1 className="text-2xl font-semibold mb-2">Состояние приложения</h1>
        <div className="text-sm text-gray-600 mb-4">
          API base: <code>{getApiBase()}</code>
        </div>

        {err && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2 mb-4">
            {err}
          </div>
        )}

        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Health</h2>
          {loading ? (
            <div>Проверка состояния сервера…</div>
          ) : health ? (
            <pre className="text-sm bg-gray-50 border border-gray-200 rounded p-3 overflow-auto">
              {typeof health === "string" ? health : JSON.stringify(health, null, 2)}
            </pre>
          ) : (
            <div className="text-sm text-gray-700">
              Спец-эндпоинт health не обнаружен в OpenAPI. Это нормально.
            </div>
          )}
        </section>

        <RoleGate roles={["Admin"]}>
          <section>
            <h2 className="text-lg font-medium mb-2">Статус активации</h2>
            {loading ? (
              <div>Загрузка статуса…</div>
            ) : act ? (
              <pre className="text-sm bg-gray-50 border border-gray-200 rounded p-3 overflow-auto">
                {typeof act === "string" ? act : JSON.stringify(act, null, 2)}
              </pre>
            ) : (
              <div className="text-sm text-gray-700">
                Эндпоинт статуса активации отсутствует в OpenAPI. Всё в порядке.
              </div>
            )}
          </section>
        </RoleGate>
      </main>
    </div>
  );
}

