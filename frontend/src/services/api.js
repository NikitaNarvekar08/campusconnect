import axios from "axios";

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./tokens";

const baseURL = import.meta.env.VITE_API_URL;

const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// Attach the access token to every request.
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If several requests fail at once, they all wait for ONE refresh call.
let refreshPromise = null;

function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${baseURL}/auth/token/refresh/`, { refresh: getRefreshToken() })
      .then(({ data }) => {
        // the backend rotates refresh tokens, so store the new one too
        setTokens({ access: data.access, refresh: data.refresh });
        return data.access;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// On a 401, refresh the token once and retry the original request.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url = original?.url ?? "";
    const isAuthCall = url.includes("/auth/login/") || url.includes("/auth/token/refresh/");

    if (status === 401 && original && !original._retried && !isAuthCall && getRefreshToken()) {
      original._retried = true;
      try {
        const access = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch (refreshError) {
        clearTokens();
        window.dispatchEvent(new Event("auth:logout")); // the auth context listens for this
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default api;