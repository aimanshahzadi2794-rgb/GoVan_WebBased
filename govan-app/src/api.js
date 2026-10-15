const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("govan_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(url, options) {
  try {
    const response = await fetch(url, options);
    window.dispatchEvent(new CustomEvent("travelease:connection", {
      detail: { online: true },
    }));
    return response;
  } catch (error) {
    window.dispatchEvent(new CustomEvent("travelease:connection", {
      detail: { online: false },
    }));
    throw error;
  }
}

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (e) {
      // response had no JSON body; keep statusText
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  async login(email, password) {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const res = await request(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    const data = await handle(res);
    localStorage.setItem("govan_token", data.access_token);
    localStorage.setItem("govan_user", JSON.stringify(data.user));
    return data.user;
  },

  async register(payload) {
    const res = await request(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handle(res);
  },

  async forgotPassword(email) {
    const res = await request(`${BASE_URL}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    return handle(res);
  },

  async resetPassword(token, password) {
    const res = await request(`${BASE_URL}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password }),
    });
    return handle(res);
  },

  logout() {
    localStorage.removeItem("govan_token");
    localStorage.removeItem("govan_user");
  },

  currentUser() {
    const raw = localStorage.getItem("govan_user");
    return raw ? JSON.parse(raw) : null;
  },

  async get(path) {
    const res = await request(`${BASE_URL}${path}`, { headers: { ...authHeaders() } });
    return handle(res);
  },

  async getGuardianPassengers() {
    return this.get("/guardian/passengers");
  },

  async getActiveTripsForMe(passengerId) {
    const query = passengerId ? `?passenger_id=${encodeURIComponent(passengerId)}` : "";
    return this.get(`/trips/active-for-me${query}`);
  },

  async post(path, body) {
    const res = await request(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body || {}),
    });
    return handle(res);
  },

  async patch(path, body) {
    const res = await request(`${BASE_URL}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body || {}),
    });
    return handle(res);
  },

  async del(path) {
    const res = await request(`${BASE_URL}${path}`, { method: "DELETE", headers: { ...authHeaders() } });
    return handle(res);
  },
};
