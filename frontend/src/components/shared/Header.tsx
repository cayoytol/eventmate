// frontend/src/components/shared/Header.tsx
"use client";

import { Link, usePathname, useRouter } from "@/routing";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { useEffect, useState } from "react";

export default function Header() {
    const locale = useLocale();
    const t = useTranslations("common");
    const pathname = usePathname();
    const router = useRouter();

    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const user = useAuthStore((s) => s.user);
    const logoutStore = useAuthStore((s) => s.logout);

    const [unreadCount, setUnreadCount] = useState(0);

    const fetchUnreadCount = async () => {
        if (!isAuthenticated) return;
        try {
            const { data } = await api.get<{ unread_count: number }>(ENDPOINTS.NOTIFICATIONS_UNREAD_COUNT);
            setUnreadCount(data.unread_count || 0);
        } catch (err) {
            console.error("Failed to fetch unread count:", err);
        }
    };

    useEffect(() => {
        if (isAuthenticated) {
            fetchUnreadCount();

            // Set up polling every 15 seconds
            const interval = setInterval(fetchUnreadCount, 15000);

            // Listen to page updates (e.g. read/read-all)
            window.addEventListener("notificationReadUpdate", fetchUnreadCount);

            return () => {
                clearInterval(interval);
                window.removeEventListener("notificationReadUpdate", fetchUnreadCount);
            };
        } else {
            setUnreadCount(0);
        }
    }, [isAuthenticated]);

    const handleLogout = async () => {
        try {
            await api.post(ENDPOINTS.LOGOUT);
        } catch {
            // ignore
        } finally {
            logoutStore();
            window.location.href = `/${locale}/login`;
        }
    };

    const handleLocaleChange = (newLocale: "ru" | "en" | "kz") => {
        const searchParamsStr = typeof window !== "undefined" ? window.location.search : "";
        router.replace(pathname + searchParamsStr, { locale: newLocale });
    };

    return (
        <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-neutral-100 shadow-sm">
            <div className="mx-auto max-w-5xl px-4 py-3 flex flex-wrap items-center justify-between gap-4">
                {/* Brand and primary links */}
                <div className="flex items-center gap-6">
                    <Link href="/" className="flex items-center gap-2 group">
                        <span className="w-8 h-8 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center text-white font-black text-sm shadow-md shadow-violet-100 group-hover:scale-105 transition duration-200">
                            С
                        </span>
                        <span className="font-black text-xl tracking-tight text-neutral-900 group-hover:text-violet-600 transition duration-200">
                            {t("brand") || "Сфера"}
                        </span>
                    </Link>

                    <Link 
                        href="/catalog" 
                        className="text-sm font-semibold text-neutral-600 hover:text-violet-600 transition"
                    >
                        {t("catalog") || "Каталог"}
                    </Link>
                </div>

                {/* Controls and user block */}
                <div className="flex items-center gap-3">
                    {/* Language switcher */}
                    <div className="flex items-center gap-0.5 bg-neutral-100 p-0.5 rounded-xl border border-neutral-200">
                        {(["ru", "en", "kz"] as const).map((l) => (
                            <button
                                key={l}
                                onClick={() => handleLocaleChange(l)}
                                className={`px-2.5 py-1 text-[10px] font-bold rounded-lg transition-all ${
                                    locale === l
                                        ? "bg-white text-violet-600 shadow-xs"
                                        : "text-neutral-500 hover:text-neutral-950"
                                }`}
                            >
                                {l.toUpperCase()}
                            </button>
                        ))}
                    </div>

                    {isAuthenticated ? (
                        <>
                            {/* Favorites (Clients only) */}
                            {user?.role === "client" && (
                                <Link
                                    href="/dashboard/favorites"
                                    className="p-2 text-neutral-500 hover:text-violet-600 hover:bg-violet-50 transition rounded-xl flex items-center justify-center"
                                    aria-label="Favorites"
                                    title={t("favorites") || "Favorites"}
                                >
                                    <svg className="w-5 h-5 stroke-current" fill="none" viewBox="0 0 24 24" strokeWidth="2.2">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                                    </svg>
                                </Link>
                            )}

                            {/* Notifications */}
                            <Link
                                href={user?.role === "provider" ? "/provider/notifications" : "/dashboard/notifications"}
                                className="relative p-2 text-neutral-500 hover:text-violet-600 hover:bg-violet-50 transition rounded-xl flex items-center justify-center"
                                aria-label="Notifications"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.2">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                                </svg>
                                {unreadCount > 0 && (
                                    <span className="absolute -top-0.5 -right-0.5 bg-violet-600 text-white text-[9px] font-black h-4 w-4 rounded-full flex items-center justify-center border border-white">
                                        {unreadCount}
                                    </span>
                                )}
                            </Link>

                            {/* User Avatar & Email */}
                            <Link 
                                href={user?.role === "provider" ? "/provider/settings/" : "/dashboard/"} 
                                className="flex items-center gap-2 group hover:opacity-90 transition select-none"
                            >
                                <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 font-extrabold text-sm flex items-center justify-center border border-neutral-200 overflow-hidden shrink-0">
                                    {user?.avatar_url ? (
                                        <img 
                                            src={user.avatar_url} 
                                            alt={user.username || user.email} 
                                            className="w-full h-full object-cover"
                                            onError={(e) => {
                                                e.currentTarget.style.display = 'none';
                                                const parent = e.currentTarget.parentElement;
                                                if (parent && !parent.querySelector('.fallback-initials')) {
                                                    const fallbackSpan = document.createElement('span');
                                                    fallbackSpan.className = 'fallback-initials';
                                                    fallbackSpan.innerText = (user.username?.[0] || user.email[0]).toUpperCase();
                                                    parent.appendChild(fallbackSpan);
                                                }
                                            }}
                                        />
                                    ) : (
                                        <span>{(user?.username?.[0] || user?.email?.[0] || "").toUpperCase()}</span>
                                    )}
                                </div>
                                <span className="hidden md:inline text-xs font-medium text-neutral-500 max-w-[120px] truncate group-hover:text-violet-600 transition">
                                    {user?.username || user?.email}
                                </span>
                            </Link>

                            {/* Role-based Dashboard link */}
                            {user?.role === "admin" ? (
                                <Link
                                    href="/admin/reports"
                                    className="text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200 px-3.5 py-2 rounded-xl hover:bg-amber-100 transition active:scale-95"
                                >
                                    {t("admin") || "Админ"}
                                </Link>
                            ) : (
                                <Link
                                    href={user?.role === "provider" ? "/provider" : "/dashboard"}
                                    className="text-xs font-bold bg-violet-50 text-violet-700 border border-violet-100 px-3.5 py-2 rounded-xl hover:bg-violet-100 transition active:scale-95"
                                >
                                    {t("dashboard") || "Кабинет"}
                                </Link>
                            )}

                            {/* Logout */}
                            <button
                                onClick={handleLogout}
                                className="text-xs font-semibold border border-neutral-200 text-neutral-500 rounded-xl px-3 py-2 hover:bg-neutral-50 hover:text-neutral-900 transition active:scale-95"
                            >
                                {t("logout")}
                            </button>
                        </>
                    ) : (
                        <>
                            <Link
                                href="/login"
                                className="text-xs font-bold text-neutral-600 hover:text-neutral-900 px-3 py-2 transition"
                            >
                                {t("login")}
                            </Link>
                            <Link
                                href="/register"
                                className="text-xs font-bold bg-violet-600 text-white px-4 py-2 rounded-xl hover:bg-violet-700 transition active:scale-95 shadow-sm shadow-violet-100"
                            >
                                {t("register")}
                            </Link>
                        </>
                    )}
                </div>
            </div>
        </header>
    );
}
