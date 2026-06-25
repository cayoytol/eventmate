"use client";

import React, { useState, useEffect } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useAuthStore } from "@/store/useAuthStore";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { AvatarUploader } from "@/components/profile/AvatarUploader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function ProviderSettingsPage() {
    const tSettings = useTranslations("settingsPage");

    const user = useAuthStore((s) => s.user);
    const setUser = useAuthStore((s) => s.setUser);

    const [username, setUsername] = useState("");
    const [language, setLanguage] = useState<"ru" | "en" | "kz">("ru");
    const [isLoading, setIsLoading] = useState(false);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        if (user) {
            setUsername(user.username || "");
            setLanguage(user.language || "ru");
        }
    }, [user]);

    if (!user) return null;

    const handleProfileSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setSuccessMessage(null);
        setErrorMessage(null);

        try {
            const { data } = await api.patch(ENDPOINTS.PROFILE_ME, {
                username,
                language,
            });
            setUser(data);
            setSuccessMessage(tSettings("profileUpdated"));
        } catch (err: any) {
            console.error("Failed to update profile settings:", err);
            const detail = err.response?.data?.detail || tSettings("updateFailed");
            setErrorMessage(detail);
        } finally {
            setIsLoading(false);
        }
    };

    const handleAvatarUploadSuccess = (updatedUser: any) => {
        setUser(updatedUser);
    };

    const handleAvatarRemoveSuccess = () => {
        if (user) {
            setUser({
                ...user,
                avatar: undefined,
                avatar_url: null,
            });
        }
    };

    const initials = user.username ? user.username[0] : user.email[0];

    return (
        <div className="max-w-4xl mx-auto space-y-8 p-4">
            <div className="space-y-2">
                <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    {tSettings("title")}
                </h1>
                <p className="text-sm text-slate-500 leading-relaxed">
                    {tSettings("subtitle")}
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start">
                {/* Left side: Avatar Uploader */}
                <div className="md:col-span-1">
                    <AvatarUploader
                        currentAvatarUrl={user.avatar_url}
                        initials={initials}
                        onUploadSuccess={handleAvatarUploadSuccess}
                        onRemoveSuccess={handleAvatarRemoveSuccess}
                    />
                </div>

                {/* Right side: General settings form */}
                <div className="md:col-span-2">
                    <Card className="p-6 border border-slate-200 rounded-2xl shadow-xs">
                        <form onSubmit={handleProfileSubmit} className="space-y-6">
                            <h2 className="text-lg font-bold text-slate-800 tracking-tight">
                                {tSettings("generalSettings")}
                            </h2>

                            {successMessage && (
                                <div className="p-3 bg-emerald-50 text-emerald-700 border border-emerald-100 rounded-xl text-xs font-semibold text-center">
                                    {successMessage}
                                </div>
                            )}

                            {errorMessage && (
                                <div className="p-3 bg-rose-50 text-rose-700 border border-rose-100 rounded-xl text-xs font-semibold text-center">
                                    {errorMessage}
                                </div>
                            )}

                            <div className="space-y-2">
                                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide">
                                    {tSettings("username")}
                                </label>
                                <input
                                    type="text"
                                    required
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-violet-500/25 focus:border-violet-500 transition"
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide">
                                    {tSettings("emailReadonly")}
                                </label>
                                <input
                                    type="email"
                                    disabled
                                    value={user.email}
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-100 bg-slate-50 text-slate-400 text-sm cursor-not-allowed select-none"
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide">
                                    {tSettings("interfaceLanguage")}
                                </label>
                                <select
                                    value={language}
                                    onChange={(e) => setLanguage(e.target.value as any)}
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-violet-500/25 focus:border-violet-500 transition bg-white"
                                >
                                    <option value="ru">Русский (RU)</option>
                                    <option value="en">English (EN)</option>
                                    <option value="kz">Қазақша (KZ)</option>
                                </select>
                            </div>

                            <div className="pt-2">
                                <Button
                                    type="submit"
                                    disabled={isLoading}
                                    className="w-full bg-violet-600 hover:bg-violet-700 text-white rounded-xl py-3 font-bold transition active:scale-95 text-xs shadow-md shadow-violet-100"
                                >
                                    {isLoading ? tSettings("saving") : tSettings("saveSettings")}
                                </Button>
                            </div>
                        </form>
                    </Card>
                </div>
            </div>
        </div>
    );
}
