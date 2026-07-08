// SEVER — API client. Live mode when VITE_API_URL is set at build time;
// otherwise the app falls back to built-in preview data.

import { authHeaders } from "./auth.js";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

export function isApiConfigured() {
  return Boolean(API_URL);
}

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}`);
  }
  return res.json();
}

export function fetchSubscriptions() {
  return request("/subscriptions");
}

// The UI says "negotiate"; the API calls it "haggle".
const MODE_MAP = { negotiate: "haggle" };

export function postAction(id, mode) {
  return request(`/subscriptions/${id}/action`, {
    method: "POST",
    body: JSON.stringify({ mode: MODE_MAP[mode] ?? mode }),
  });
}

export function postUndo(id) {
  return request(`/subscriptions/${id}/undo`, { method: "POST" });
}

export async function downloadExport() {
  const data = await request("/account/export");
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `sever-export-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function deleteAccount() {
  return request("/account", { method: "DELETE" });
}

// --- Bank connections (multi-bank) ---

export function fetchBanks() {
  return request("/banks");
}

export function createLinkToken() {
  return request("/banks/link-token", { method: "POST" });
}

export function exchangeBankToken(publicToken, institution) {
  return request("/banks/exchange", {
    method: "POST",
    body: JSON.stringify({ publicToken, institution }),
  });
}

export function syncBanks() {
  return request("/banks/sync", { method: "POST" });
}

export function disconnectBank(connectionId) {
  return request(`/banks/${connectionId}`, { method: "DELETE" });
}
