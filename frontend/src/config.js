// Same-origin (empty) when not set in production (e.g. Railway single service)
const API_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "http://localhost:8000" : "");
const WS_URL =
  import.meta.env.VITE_WS_URL ||
  (import.meta.env.DEV ? "ws://localhost:8000" : "");

export const config = {
  API_URL,
  WS_URL,
  API_BASE: API_URL, // Convenience alias
};

export default config;
