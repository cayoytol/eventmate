import { create } from 'zustand';
import type { User } from '../types/auth';
import { clearTokens } from '@/lib/token';

interface AuthState {
  user: User | null;
  accessToken: string | null;

  // derived flags (stored, but always kept consistent)
  isAuthenticated: boolean;
  isReady: boolean;

  setAccessToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  setReady: (ready: boolean) => void;

  // helper to set both at once (optional but very useful)
  setSession: (payload: { token: string | null; user: User | null }) => void;

  logout: () => void;
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isReady: false,

  setAccessToken: (token) => {
    const user = get().user;
    set({
      accessToken: token,
      isAuthenticated: !!token && !!user,
    });
  },

  setUser: (user) => {
    const token = get().accessToken;
    set({
      user,
      isAuthenticated: !!token && !!user,
    });
  },

  setSession: ({ token, user }) => {
    set({
      accessToken: token,
      user,
      isAuthenticated: !!token && !!user,
    });
  },

  setReady: (ready) => set({ isReady: ready }),

  logout: () => {
    clearTokens();
    set({
      user: null,
      accessToken: null,
      isAuthenticated: false,
    });
  },
}));
