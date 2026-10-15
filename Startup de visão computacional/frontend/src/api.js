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

export async function download(path, { query } = {}) {
  const url = query ? `${path}?${new URLSearchParams(query)}` : path;
  let r;
  try {
    r = await fetch(url, { headers: { Accept: "application/pdf, application/json" }, credentials: "same-origin" });
  } catch {
    throw apiError(0, "network_error");
  }
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw apiError(r.status, data.error?.code || "server_error", data.error);
  }
  const name = /filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "")?.[1] || "certificado.pdf";
  const href = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement("a"), { href, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 10000);
  return name;
}

export function upload(path, form, onProgress, retried = false) {
  return getCsrf().then(
    (token) =>
      new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", path);
        xhr.setRequestHeader("Accept", "application/json");
        xhr.setRequestHeader("X-CSRFToken", token);
        xhr.withCredentials = true;
        xhr.upload.onprogress = (e) => e.lengthComputable && onProgress("upload", e.loaded / e.total);
        xhr.upload.onload = () => onProgress("sent", 1);
        xhr.onerror = () => reject(apiError(0, "network_error"));
        xhr.onload = () => {
          let data = {};
          try {
            data = JSON.parse(xhr.responseText);
          } catch {
            data = {};
          }
          if (xhr.status >= 200 && xhr.status < 300) return resolve(data);
          const code = data.error?.code || "server_error";
          if (code === "csrf_failed" && !retried) {
            csrfToken = null;
            return resolve(upload(path, form, onProgress, true));
          }
          reject(apiError(xhr.status, code, data.error));
        };
        xhr.send(form);
      }),
    () => Promise.reject(apiError(0, "network_error")),
  );
}
