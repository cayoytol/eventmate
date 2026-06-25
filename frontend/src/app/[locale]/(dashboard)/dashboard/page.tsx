"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/routing";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { StatCard } from "@/components/ui/StatCard";
import { Card } from "@/components/ui/Card";

export default function DashboardPage() {
    const t = useTranslations("dashboard");
    const tNav = useTranslations("dashboard.navigation");

    const [stats, setStats] = useState({
        requests: 0,
        orders: 0,
        favorites: 0,
        unreadNotifications: 0
    });
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchDashboardStats = async () => {
            try {
                // Fetch requests, orders, favorites, and unread count concurrently
                const [reqRes, ordRes, favRes, notRes] = await Promise.all([
                    api.get("/requests/").catch(() => ({ data: [] })),
                    api.get("/orders/").catch(() => ({ data: [] })),
                    api.get("/favorites/").catch(() => ({ data: [] })),
                    api.get(ENDPOINTS.NOTIFICATIONS_UNREAD_COUNT).catch(() => ({ data: { unread_count: 0 } }))
                ]);

                const reqArray = Array.isArray(reqRes.data) ? reqRes.data : reqRes.data.results || [];
                const ordArray = Array.isArray(ordRes.data) ? ordRes.data : ordRes.data.results || [];
                const favArray = Array.isArray(favRes.data) ? favRes.data : favRes.data.results || [];
                const unreadVal = notRes.data?.unread_count || 0;

                setStats({
                    requests: reqArray.length,
                    orders: ordArray.length,
                    favorites: favArray.length,
                    unreadNotifications: unreadVal
                });
            } catch (err) {
                console.error("Failed to load dashboard stats:", err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchDashboardStats();
    }, []);

    return (
        <div className="space-y-8 max-w-6xl mx-auto">
            {/* PageHeader section */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-6 border border-slate-200 rounded-2xl shadow-xs">
                <div className="space-y-1">
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        {t("overview.welcome")}
                    </h1>
                    <p className="text-sm text-slate-500">
                        {t("overview.subtitle")}
                    </p>
                </div>
                <Link
                    href="/dashboard/requests/new"
                    className="inline-flex items-center justify-center gap-2 px-5 py-3 bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold rounded-xl shadow-md shadow-violet-100 transition duration-200 active:scale-95 shrink-0 self-start md:self-auto"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                    </svg>
                    <span>{t("overview.actions.createRequest")}</span>
                </Link>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                    title={t("overview.stats.requests")}
                    value={isLoading ? "..." : stats.requests}
                    description={t("overview.stats.requestsDesc")}
                    icon={
                        <svg className="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    }
                />
                <StatCard
                    title={t("overview.stats.orders")}
                    value={isLoading ? "..." : stats.orders}
                    description={t("overview.stats.ordersDesc")}
                    icon={
                        <svg className="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                        </svg>
                    }
                />
                <StatCard
                    title={t("overview.stats.favorites")}
                    value={isLoading ? "..." : stats.favorites}
                    description={t("overview.stats.favoritesDesc")}
                    icon={
                        <svg className="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                        </svg>
                    }
                />
                <StatCard
                    title={t("overview.stats.notifications")}
                    value={isLoading ? "..." : stats.unreadNotifications}
                    description={t("overview.stats.notificationsDesc")}
                    icon={
                        <svg className="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                        </svg>
                    }
                />
            </div>

            {/* Quick Actions Card */}
            <Card className="p-6 md:p-8 border border-slate-200 shadow-xs">
                <h3 className="text-lg font-extrabold text-slate-900 mb-6 flex items-center gap-2">
                    <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {t("overview.actions.title")}
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
                    <Link
                        href="/dashboard/requests/new"
                        className="flex flex-col items-center justify-center p-6 text-center border border-slate-200 bg-white rounded-2xl hover:bg-slate-50 hover:border-violet-200 hover:shadow-xs transition duration-200 group"
                    >
                        <div className="w-10 h-10 bg-violet-50 text-violet-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                            </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-800">{t("overview.actions.createRequest")}</span>
                    </Link>

                    <Link
                        href="/dashboard/orders"
                        className="flex flex-col items-center justify-center p-6 text-center border border-slate-200 bg-white rounded-2xl hover:bg-slate-50 hover:border-violet-200 hover:shadow-xs transition duration-200 group"
                    >
                        <div className="w-10 h-10 bg-violet-50 text-violet-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2" />
                            </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-800">{t("overview.actions.viewOrders")}</span>
                    </Link>

                    <Link
                        href="/dashboard/chats"
                        className="flex flex-col items-center justify-center p-6 text-center border border-slate-200 bg-white rounded-2xl hover:bg-slate-50 hover:border-violet-200 hover:shadow-xs transition duration-200 group"
                    >
                        <div className="w-10 h-10 bg-violet-50 text-violet-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01" />
                            </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-800">{t("overview.actions.openChats")}</span>
                    </Link>

                    <Link
                        href="/catalog"
                        className="flex flex-col items-center justify-center p-6 text-center border border-slate-200 bg-white rounded-2xl hover:bg-slate-50 hover:border-violet-200 hover:shadow-xs transition duration-200 group"
                    >
                        <div className="w-10 h-10 bg-violet-50 text-violet-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-800">{t("overview.actions.browseCatalog")}</span>
                    </Link>

                    <Link
                        href="/dashboard/favorites"
                        className="flex flex-col items-center justify-center p-6 text-center border border-slate-200 bg-white rounded-2xl hover:bg-slate-50 hover:border-violet-200 hover:shadow-xs transition duration-200 group"
                    >
                        <div className="w-10 h-10 bg-violet-50 text-violet-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                            </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-800">{tNav("favorites")}</span>
                    </Link>

                    <Link
                        href="/dashboard/notifications"
                        className="flex flex-col items-center justify-center p-6 text-center border border-slate-200 bg-white rounded-2xl hover:bg-slate-50 hover:border-violet-200 hover:shadow-xs transition duration-200 group"
                    >
                        <div className="w-10 h-10 bg-violet-50 text-violet-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-105 transition">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                            </svg>
                        </div>
                        <span className="text-sm font-bold text-slate-800">{tNav("notifications")}</span>
                    </Link>
                </div>
            </Card>
        </div>
    );
}
