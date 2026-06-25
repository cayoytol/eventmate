'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { api } from '@/lib/api';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { getAccessToken, setTokens, clearTokens } from '@/lib/token';

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const { setSession, setReady, logout } = useAuthStore();

    useEffect(() => {
        const bootstrapAuth = async () => {
            const token = getAccessToken();
            if (token) {
                try {
                    // Set token temporarily in memory so request interceptor includes it
                    useAuthStore.getState().setAccessToken(token);

                    const profileRes = await api.get(ENDPOINTS.PROFILE_ME);
                    
                    // Successfully fetched profile, restore session
                    setSession({ token, user: profileRes.data });
                } catch (e) {
                    // Fetch failed, clear session and tokens
                    logout();
                    clearTokens();
                } finally {
                    setReady(true);
                }
            } else {
                // No access token in storage. Try HttpOnly cookie refresh once
                try {
                    const refreshRes = await api.post(ENDPOINTS.REFRESH, {});
                    const access = refreshRes.data?.access;
                    if (access) {
                        setTokens(access, null);
                        useAuthStore.getState().setAccessToken(access);
                        
                        const profileRes = await api.get(ENDPOINTS.PROFILE_ME);
                        setSession({ token: access, user: profileRes.data });
                    } else {
                        logout();
                        clearTokens();
                    }
                } catch (e) {
                    logout();
                    clearTokens();
                } finally {
                    setReady(true);
                }
            }
        };

        bootstrapAuth();
    }, [setSession, setReady, logout]);

    return <>{children}</>;
}
