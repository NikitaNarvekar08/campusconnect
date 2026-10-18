import axios from "axios";

// One shared Axios instance. In Phase 4 we'll attach JWT tokens here
// with interceptors so every request is authenticated automatically.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: { "Content-Type": "application/json" },
});

export default api;
