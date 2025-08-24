import React, { useState } from "react";
import { rescheduleVisit, rescheduleVisitTomorrow } from "../api/visits";

type Props = {
  visitId: number;
  onDone?: () => void; // перезагрузка карточки после переноса
};

export default function RescheduleDialog({ visitId, onDone }: Props) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>("");
  const [ok, setOk] = useState<string>("");

  async function submitDate() {
    if (!date) {
      setError("Выберите дату");
      return;
    }
    setBusy(true);
    setError("");
    setOk("");
    try {
      await rescheduleVisit(visitId, date);
      setOk("Перенесено");
      onDone?.();
      setOpen(false);
    } catch (e: any) {
      setError(e?.message || "Ошибка переноса");
    } finally {
      setBusy(false);
    }
  }

  async function submitTomorrow() {
    setBusy(true);
    setError("");
    setOk("");
    try {
      await rescheduleVisitTomorrow(visitId);
      setOk("Перенесено на завтра");
      onDone?.();
      setOpen(false);
    } catch (e: any) {
      setError(e?.message || "Ошибка переноса");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        className="px-3 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
        onClick={() => setOpen(true)}
      >
        Перенести
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-4 shadow-lg">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Перенести визит</h2>
              <button
                className="text-gray-500 hover:text-gray-700"
                onClick={() => setOpen(false)}
                aria-label="Закрыть"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <label className="block text-sm">
                Новая дата
                <input
                  type="date"
                  className="mt-1 w-full rounded-md border px-2 py-1"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </label>

              {error && (
                <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              )}
              {ok && (
                <div className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
                  {ok}
                </div>
              )}

              <div className="flex items-center justify-between gap-2 pt-2">
                <button
                  className="px-3 py-2 rounded-md border"
                  onClick={() => setOpen(false)}
                  disabled={busy}
                >
                  Отмена
                </button>
                <div className="flex gap-2">
                  <button
                    className="px-3 py-2 rounded-md bg-gray-100 hover:bg-gray-200"
                    onClick={submitTomorrow}
                    disabled={busy}
                    title="Перенести на следующий рабочий день"
                  >
                    На завтра
                  </button>
                  <button
                    className="px-3 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700"
                    onClick={submitDate}
                    disabled={busy}
                  >
                    {busy ? "Сохраняю..." : "Перенести на дату"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
