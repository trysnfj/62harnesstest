import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export async function listModels() {
  const { data } = await api.get("/models");
  return data.models || [];
}

export async function getConfig() {
  const { data } = await api.get("/config");
  return data;
}

export async function listChats() {
  const { data } = await api.get("/chats");
  return data;
}

export async function createChat() {
  const { data } = await api.post("/chats", { title: "New chat" });
  return data;
}

export async function deleteChat(id) {
  await api.delete(`/chats/${id}`);
}

export async function getMessages(chatId) {
  const { data } = await api.get(`/chats/${chatId}/messages`);
  return data;
}

export async function listDocuments(chatId) {
  const { data } = await api.get("/documents", { params: chatId ? { chat_id: chatId } : {} });
  return data;
}

export async function uploadDocument(file, chatId) {
  const form = new FormData();
  form.append("file", file);
  if (chatId) form.append("chat_id", chatId);
  const { data } = await api.post("/documents", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deleteDocument(id) {
  await api.delete(`/documents/${id}`);
}

export async function getStats() {
  const { data } = await api.get("/stats");
  return data;
}

/**
 * Stream the harness pipeline. Calls onEvent(evt) for every SSE event.
 */
export async function streamChat(payload, onEvent, signal) {
  const res = await fetch(`${API}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.body) throw new Error("No stream body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const jsonStr = line.slice(5).trim();
      if (!jsonStr) continue;
      try {
        onEvent(JSON.parse(jsonStr));
      } catch (e) {
        /* ignore parse errors on partial */
      }
    }
  }
}
