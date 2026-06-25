// frontend/src/app/[locale]/(auth)/login/page.tsx
"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { useAuthStore } from "@/store/useAuthStore";
import { setTokens } from "@/lib/token";

type LoginResponse = { access: string };

export default function LoginPage() {
    const locale = useLocale();
    const t = useTranslations("auth");
    const router = useRouter();
    const searchParams = useSearchParams();

    const setSession = useAuthStore((s) => s.setSession);

    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [rememberMe, setRememberMe] = useState(false);

    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const next = searchParams.get("next");

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);

        try {
            console.log("[Login] Starting login request...");

            // 1) login (with timeout)
            const loginRes = await api.post<LoginResponse>(ENDPOINTS.LOGIN, {
                email,
                password,
                remember_me: rememberMe,
            }, { timeout: 10000 });

            console.log("[Login] Success, status:", loginRes.status);
            const access = loginRes.data?.access;
            if (!access) throw new Error("No access token in response");

            // set token immediately
            setTokens(access, null, rememberMe);
            useAuthStore.getState().setAccessToken(access);

            // 2) load profile (with timeout)
            console.log("[Login] Fetching profile...");
            const profileRes = await api.get(ENDPOINTS.PROFILE_ME, { timeout: 10000 });
            console.log("[Login] Profile fetched:", profileRes.status);

            // 3) set session atomically
            setSession({ token: access, user: profileRes.data });

            // 4) redirect
            // 4) redirect based on role
            const userRole = profileRes.data?.role; // Assuming role is in profile response
            let defaultRedirect = `/${locale}/dashboard/`; // Default fallback

            if (userRole === "provider") {
                defaultRedirect = `/${locale}/provider/`;
            } else {
                // For clients, go to requests request feed (Client Dashboard)
                // Note: /dashboard might redirect, but safe to be explicit
                defaultRedirect = `/${locale}/dashboard/requests/`;
            }

            const safeNext =
                next && next.startsWith(`/${locale}/`) ? next : defaultRedirect;
            router.replace(safeNext);
        } catch (err: any) {
            console.error("[Login] Failed:", err);

            // Log detailed error for debugging
            if (err.response) {
                console.error("[Login] Status:", err.response.status);
                console.error("[Login] Data:", err.response.data);
            }

            const msg =
                err?.response?.data?.detail ||
                err?.response?.data?.non_field_errors?.[0] ||
                err?.response?.data?.email?.[0] ||
                err?.response?.data?.password?.[0] ||
                t("errors.loginFailed");
            setError(msg);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="bg-white border rounded-2xl p-6 shadow-sm">
            <h1 className="text-xl font-semibold mb-1">{t("login.title")}</h1>
            <p className="text-sm text-neutral-500 mb-6">{t("login.subtitle")}</p>

            {error ? (
                <div className="mb-4 rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm">
                    {error}
                </div>
            ) : null}

            <form onSubmit={handleSubmit} className="space-y-3">
                <div className="space-y-1">
                    <label className="text-sm text-neutral-600">{t("login.email")}</label>
                    <input
                        className="w-full border rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-neutral-200"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder={t("login.emailPlaceholder")}
                        required
                        autoComplete="email"
                    />
                </div>

                <div className="space-y-1">
                    <label className="text-sm text-neutral-600">
                        {t("login.password")}
                    </label>
                    <input
                        className="w-full border rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-neutral-200"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder={t("login.passwordPlaceholder")}
                        required
                        autoComplete="current-password"
                    />
                </div>

                <label className="flex items-center gap-2 text-sm text-neutral-700 select-none">
                    <input
                        type="checkbox"
                        checked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                    />
                    {t("login.rememberMe")}
                </label>

                <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full rounded-xl bg-black text-white py-2.5 disabled:opacity-60"
                >
                    {isLoading ? t("login.loading") : t("login.submit")}
                </button>

                <div className="text-sm text-neutral-600 text-center pt-1">
                    {t("login.noAccount")}{" "}
                    <a className="underline" href={`/${locale}/register`}>
                        {t("login.goRegister")}
                    </a>
                </div>
            </form>
        </div>
    );
}
