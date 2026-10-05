import { reactive } from "vue";
import { api } from "./api.js";

export const auth = reactive({ user: null, checked: false });

export async function loadUser() {
  try {
    auth.user = (await api("/api/auth/me")).user;
  } catch {
    auth.user = null;
  }
  auth.checked = true;
}

export async function login(username, password) {
  auth.user = (await api("/api/auth/login", { method: "POST", body: { username, password } })).user;
}

export async function logout() {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } finally {
    auth.user = null;
  }
}
