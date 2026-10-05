let csrfToken = null;

function apiError(status, code, info) {
  return Object.assign(new Error(code), { status, code, info });
}

async function getCsrf() {
  if (!csrfToken) {
    const r = await fetch("/api/auth/csrf", { credentials: "same-origin" });
    csrfToken = (await r.json()).csrf_token;
  }
  return csrfToken;
}

export async function api(path, { method = "GET", body, query, retried = false } = {}) {
  const url = query ? `${path}?${new URLSearchParams(query)}` : path;
  const headers = { Accept: "application/json" };
  let payload = body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let r;
  try {
    if (method !== "GET") headers["X-CSRFToken"] = await getCsrf();
    r = await fetch(url, { method, body: payload, headers, credentials: "same-origin" });
  } catch {
    throw apiError(0, "network_error");
  }
  const data = await r.json().catch(() => ({}));
  if (data.csrf_token) csrfToken = data.csrf_token;
  if (r.ok) return data;
  const code = data.error?.code || "server_error";
  if (code === "csrf_failed" && !retried) {
    csrfToken = null;
    return api(path, { method, body, query, retried: true });
  }
  throw apiError(r.status, code, data.error);
}
