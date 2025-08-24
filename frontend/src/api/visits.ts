function authHeader(): HeadersInit {
  const token =
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(text || `${resp.status} ${resp.statusText}`);
  }
  // может быть пустой ответ — вернём {}
  const contentType = resp.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return {} as T;
  return (await resp.json()) as T;
}

export async function rescheduleVisit(visitId: number, newDateISO: string) {
  const url = `/api/v1/visits/${visitId}/reschedule?new_date=${encodeURIComponent(newDateISO)}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
  });
  return handle<any>(resp);
}

export async function rescheduleVisitTomorrow(visitId: number) {
  const url = `/api/v1/visits/${visitId}/reschedule/tomorrow`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
  });
  return handle<any>(resp);
}
