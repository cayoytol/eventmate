const ACCESS_TOKEN_KEY = 'eventmate_access_token';
const REFRESH_TOKEN_KEY = 'eventmate_refresh_token';
const REMEMBER_ME_KEY = 'eventmate_remember_me';

export const getAccessToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(ACCESS_TOKEN_KEY) ?? localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const getRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(REFRESH_TOKEN_KEY) ?? localStorage.getItem(REFRESH_TOKEN_KEY);
};

export const getRememberMe = (): boolean => {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem(REMEMBER_ME_KEY) === 'true' || localStorage.getItem(REMEMBER_ME_KEY) === 'true';
};

export const setTokens = (access: string | null, refresh: string | null, rememberMe?: boolean) => {
  if (typeof window === 'undefined') return;

  const shouldRemember = rememberMe !== undefined ? rememberMe : getRememberMe();

  if (shouldRemember) {
    localStorage.setItem(REMEMBER_ME_KEY, 'true');
    sessionStorage.removeItem(REMEMBER_ME_KEY);
  } else {
    sessionStorage.setItem(REMEMBER_ME_KEY, 'true');
    localStorage.removeItem(REMEMBER_ME_KEY);
  }

  const storage = shouldRemember ? localStorage : sessionStorage;
  const oppositeStorage = shouldRemember ? sessionStorage : localStorage;

  if (access) {
    storage.setItem(ACCESS_TOKEN_KEY, access);
    oppositeStorage.removeItem(ACCESS_TOKEN_KEY);
  } else {
    storage.removeItem(ACCESS_TOKEN_KEY);
    oppositeStorage.removeItem(ACCESS_TOKEN_KEY);
  }

  if (refresh) {
    storage.setItem(REFRESH_TOKEN_KEY, refresh);
    oppositeStorage.removeItem(REFRESH_TOKEN_KEY);
  } else {
    storage.removeItem(REFRESH_TOKEN_KEY);
    oppositeStorage.removeItem(REFRESH_TOKEN_KEY);
  }
};

export const setAccessToken = (access: string | null) => {
  if (typeof window === 'undefined') return;

  const inLocalStorage = localStorage.getItem(ACCESS_TOKEN_KEY) !== null;
  const inSessionStorage = sessionStorage.getItem(ACCESS_TOKEN_KEY) !== null;

  if (access) {
    if (inLocalStorage) {
      localStorage.setItem(ACCESS_TOKEN_KEY, access);
    } else if (inSessionStorage) {
      sessionStorage.setItem(ACCESS_TOKEN_KEY, access);
    } else {
      const shouldRemember = getRememberMe();
      const storage = shouldRemember ? localStorage : sessionStorage;
      storage.setItem(ACCESS_TOKEN_KEY, access);
    }
  } else {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  }
};

export const clearTokens = () => {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(REMEMBER_ME_KEY);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(REMEMBER_ME_KEY);
};

export const hasStoredAuth = (): boolean => {
  return !!getAccessToken();
};
