import { api } from "./client";

export async function getHealth() {
  const res = await api.get("/health");
  return res.data;
}

export async function getActivationStatus() {
  const res = await api.get("/activation/status");
  return res.data;
}
