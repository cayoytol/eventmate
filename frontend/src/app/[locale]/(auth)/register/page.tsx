// frontend/src/app/[locale]/(auth)/register/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";

type Role = "client" | "provider";

export default function RegisterPage() {
    const locale = useLocale();
    const t = useTranslations("auth");
    const router = useRouter();

    const [role, setRole] = useState<Role>("client");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");

    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (password !== confirm) {
            setError(t("errors.passwordMismatch"));
            return;
        }

        setIsLoading(true);
        try {
            await api.post(ENDPOINTS.REGISTER, { email, password, role });

            // MVP: after register → go login
            router.replace(`/${locale}/login`);
        } catch (err: any) {
            if (process.env.NODE_ENV === "development") {
                console.error("[Register Error]", err?.response?.data || err);
            }

            const data = err?.response?.data;
            const msg =
                data?.email?.[0] ||
                data?.password?.[0] ||
                data?.role?.[0] ||
                data?.detail ||
                data?.non_field_errors?.[0] ||
                t("errors.registerFailed");
            setError(msg);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="bg-white border rounded-2xl p-6 shadow-sm">
            <h1 className="text-xl font-semibold mb-1">{t("register.title")}</h1>
            <p className="text-sm text-neutral-500 mb-6">{t("register.subtitle")}</p>

            {error ? (
                <div className="mb-4 rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm">
                    {error}
                </div>
            ) : null}

            <form onSubmit={handleSubmit} className="space-y-3">
                <div className="space-y-2">
                    <div className="text-sm text-neutral-600">{t("register.role")}</div>
                    <div className="flex gap-3">
                        <label className="flex items-center gap-2 text-sm">
                            <input
                                type="radio"
                                name="role"
                                value="client"
                                checked={role === "client"}
                                onChange={() => setRole("client")}
                            />
                            {t("register.roleClient")}
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                            <input
                                type="radio"
                                name="role"
                                value="provider"
                                checked={role === "provider"}
                                onChange={() => setRole("provider")}
                            />
                            {t("register.roleProvider")}
                        </label>
                    </div>
                </div>

                <div className="space-y-1">
                    <label className="text-sm text-neutral-600">
                        {t("register.email")}
                    </label>
                    <input
                        className="w-full border rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-neutral-200"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder={t("register.emailPlaceholder")}
                        required
                        autoComplete="email"
                    />
                </div>

                <div className="space-y-1">
                    <label className="text-sm text-neutral-600">
                        {t("register.password")}
                    </label>
                    <input
                        className="w-full border rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-neutral-200"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder={t("register.passwordPlaceholder")}
                        required
                        autoComplete="new-password"
                        minLength={8}
                    />
                </div>

                <div className="space-y-1">
                    <label className="text-sm text-neutral-600">
                        {t("register.confirm")}
                    </label>
                    <input
                        className="w-full border rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-neutral-200"
                        type="password"
                        value={confirm}
                        onChange={(e) => setConfirm(e.target.value)}
                        placeholder={t("register.confirmPlaceholder")}
                        required
                        autoComplete="new-password"
                        minLength={8}
                    />
                </div>

                <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full rounded-xl bg-black text-white py-2.5 disabled:opacity-60"
                >
                    {isLoading ? t("register.loading") : t("register.submit")}
                </button>

                <div className="text-sm text-neutral-600 text-center pt-1">
                    {t("register.haveAccount")}{" "}
                    <a className="underline" href={`/${locale}/login`}>
                        {t("register.goLogin")}
                    </a>
                </div>
            </form>
        </div>
    );
}
