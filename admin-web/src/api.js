const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("govan_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
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
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    const data = await handle(res);
    localStorage.setItem("govan_token", data.access_token);
    localStorage.setItem("govan_user", JSON.stringify(data.user));
    return data.user;
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
    const res = await fetch(`${BASE_URL}${path}`, { headers: { ...authHeaders() } });
    return handle(res);
  },

  async getBootstrapStatus() {
    return this.get("/auth/bootstrap-status");
  },

  async getUsers() {
    return this.get("/users/");
  },

  async createUser(payload) {
    return this.post("/users/", payload);
  },

  async updateUser(userId, payload) {
    return this.patch(`/users/${userId}`, payload);
  },

  async getPassengerGuardians(passengerId) {
    return this.get(`/users/${passengerId}/guardians`);
  },

  async linkGuardian(passengerId, payload) {
    return this.post(`/users/${passengerId}/guardians`, payload);
  },

  async unlinkGuardian(passengerId, guardianId) {
    return this.del(`/users/${passengerId}/guardians/${guardianId}`);
  },

  async getOrganizations() {
    return this.get("/organizations/");
  },

  async createOrganization(payload) {
    return this.post("/organizations/", payload);
  },

  async updateOrganization(organizationId, payload) {
    return this.patch(`/organizations/${organizationId}`, payload);
  },

  async deleteOrganization(organizationId) {
    return this.del(`/organizations/${organizationId}`);
  },

  async getTripPath(tripId) {
    return this.get(`/trips/${tripId}/path`);
  },

  async getTripStops(tripId) {
    return this.get(`/trips/${tripId}/stops`);
  },

  async getReportSummary(filters) {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) {
        query.set(key, value);
      }
    });
    return this.get(`/reports/summary?${query.toString()}`);
  },

  async post(path, body) {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body || {}),
    });
    return handle(res);
  },

  async patch(path, body) {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body || {}),
    });
    return handle(res);
  },

  async del(path) {
    const res = await fetch(`${BASE_URL}${path}`, { method: "DELETE", headers: { ...authHeaders() } });
    return handle(res);
  },
};
