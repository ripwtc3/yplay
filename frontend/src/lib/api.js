import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

export function wsUrl(token) {
    // https -> wss, http -> ws
    const base = BACKEND_URL.replace(/^http/, "ws");
    return `${base}/api/ws?token=${encodeURIComponent(token)}`;
}
