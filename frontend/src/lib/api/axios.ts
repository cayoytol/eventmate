import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from "@/store/useAuthStore";
import { getAccessToken, setTokens, setAccessToken, clearTokens } from '@/lib/token';

let rawApiUrl = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";
if (rawApiUrl.endsWith("/")) {
  rawApiUrl = rawApiUrl.slice(0, -1);
}
const API_URL = rawApiUrl;

// Locale helpers for redirect
const SUPPORTED_LOCALES = ["ru", "en", "kz"] as const;
type Locale = (typeof SUPPORTED_LOCALES)[number];

const getLocaleFromPath = (): Locale | null => {
  if (typeof window === "undefined") return null;
  const seg = window.location.pathname.split("/")[1];
  return (SUPPORTED_LOCALES as readonly string[]).includes(seg) ? (seg as Locale) : null;
};

const getLocaleFromCookie = (): Locale | null => {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)NEXT_LOCALE=([^;]+)/);
  const val = match?.[1];
  return val && (SUPPORTED_LOCALES as readonly string[]).includes(val) ? (val as Locale) : null;
};

const getActiveLocale = (): Locale => {
  return getLocaleFromPath() ?? getLocaleFromCookie() ?? "ru";
};

const redirectToLogin = () => {
  if (typeof window === "undefined") return;
  const locale = getActiveLocale();
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/${locale}/login?next=${next}`;
};

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

if (process.env.NODE_ENV === 'development') {
  console.debug("[API] baseURL:", api.defaults.baseURL);
}

// Track if refresh is in progress to prevent race conditions
let isRefreshing = false;
let refreshSubscribers: ((token: string | null) => void)[] = [];

const subscribeTokenRefresh = (cb: (token: string | null) => void) => {
  refreshSubscribers.push(cb);
};

const onRefreshed = (token: string | null) => {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
};

// Request interceptor: attach access token
api.interceptors.request.use((config) => {
  // Auto-fix missing trailing slashes ONLY for auth endpoints
  if (config.url && config.url.startsWith('/auth/') && !config.url.includes('?')) {
    if (!config.url.endsWith('/')) {
      config.url = config.url + '/';
      if (process.env.NODE_ENV === 'development') {
        console.warn(`🔧 Auto-fixed trailing slash: ${config.url}`);
      }
    }
  }

  // Debug logging for development
  if (process.env.NODE_ENV === 'development') {
    console.log('🔍 Axios Request:', {
      baseURL: config.baseURL,
      url: config.url,
      fullURL: `${config.baseURL}${config.url}`,
      method: config.method?.toUpperCase()
    });

    // Warn about missing trailing slash (Django APPEND_SLASH requirement)
    if (config.url && !config.url.endsWith('/') && !config.url.includes('?')) {
      console.warn(`⚠️ URL without trailing slash: ${config.url}`);
      console.warn('   Django requires trailing slashes. This may cause 500 errors for POST requests.');
    }
  }

  const token = getAccessToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  } else if (config.headers) {
    delete config.headers.Authorization;
  }

  const locale = getActiveLocale();
  if (config.headers) {
    config.headers['Accept-Language'] = locale;
  }

  // Strip leading slash if present to prevent Axios from resolving relative to domain root
  if (config.url && config.url.startsWith('/') && !config.url.startsWith('http://') && !config.url.startsWith('https://')) {
    config.url = config.url.substring(1);
  }

  return config;
});

// Response interceptor: auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Prevent infinite loops on auth endpoints
    if (originalRequest.url && (originalRequest.url.startsWith('/auth/') || originalRequest.url.startsWith('auth/'))) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // If refresh is already in progress, queue this request
        return new Promise((resolve, reject) => {
          subscribeTokenRefresh((token) => {
            if (!token) {
              reject(error);
              return;
            }
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Use api instance to go through request interceptor (auto-fix + debug logging)
        const { data } = await api.post("/auth/refresh/", {});

        const { access } = data;
        useAuthStore.getState().setAccessToken(access);
        setAccessToken(access);

        isRefreshing = false;
        onRefreshed(access);

        // Retry original request with new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access}`;
        }
        return api(originalRequest);
      } catch (refreshError) {
        isRefreshing = false;
        onRefreshed(null);

        // Refresh failed - logout user and redirect to login
        useAuthStore.getState().logout();
        clearTokens();
        redirectToLogin();

        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
