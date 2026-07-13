import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? "https://vision.tokdou.com" : "/"),
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("vision_capital_ai_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("vision_capital_ai_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default client;
