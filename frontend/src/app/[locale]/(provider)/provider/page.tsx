"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { useAuthStore } from "@/store/useAuthStore";
import { StatCard } from "@/components/ui/StatCard";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

interface StatsData {
    activeServices: number;
    openRequests: number;
    activeOrders: number;
    currentPlan: string;
}

export default function ProviderDashboardPage() {
    const locale = useLocale();
    const t = useTranslations("dashboard.providerOverview");
    const user = useAuthStore((s) => s.user);

    const [stats, setStats] = useState<StatsData>({
        activeServices: 0,
        openRequests: 0,
        activeOrders: 0,
        currentPlan: "",
    });
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;
        const abortController = new AbortController();

        const fetchStats = async () => {
            setIsLoading(true);
            try {
                const [servicesRes, requestsRes, ordersRes, billingRes] = await Promise.all([
                    api.get(ENDPOINTS.SERVICES, { params: { provider: "me" }, signal: abortController.signal }).catch(() => ({ data: [] })),
                    api.get(ENDPOINTS.REQUESTS, { signal: abortController.signal }).catch(() => ({ data: [] })),
                    api.get(ENDPOINTS.ORDERS, { signal: abortController.signal }).catch(() => ({ data: [] })),
                    api.get(ENDPOINTS.BILLING_SUBSCRIPTION_CURRENT, { signal: abortController.signal }).catch(() => ({ data: null })),
                ]);

                if (!isMounted) return;

                // 1. Active Services count
                const servicesData = servicesRes.data;
                const servicesList = Array.isArray(servicesData) ? servicesData : (servicesData?.results ?? []);
                
                // 2. Open Requests count
                const requestsData = requestsRes.data;
                const requestsList = Array.isArray(requestsData) ? requestsData : (requestsData?.results ?? []);
                const openCount = requestsList.filter((r: any) => r.status === "open").length;

                // 3. Active Orders count (confirmed or in_progress)
                const ordersData = ordersRes.data;
                const ordersList = Array.isArray(ordersData) ? ordersData : (ordersData?.results ?? []);
                const activeCount = ordersList.filter((o: any) => o.status === "confirmed" || o.status === "in_progress").length;

                // 4. Current Subscription Plan name
                const currentPlanObj = billingRes.data?.current_plan;
                const planName = currentPlanObj
                    ? (currentPlanObj[`name_${locale as "ru" | "en" | "kz"}`] || currentPlanObj.name_en || currentPlanObj.name)
                    : "";

                setStats({
                    activeServices: servicesList.length,
                    openRequests: openCount,
                    activeOrders: activeCount,
                    currentPlan: planName || (locale === "en" ? "Free Plan" : locale === "kz" ? "Тегін тариф" : "Бесплатный тариф"),
                });
            } catch (err) {
                console.error("[ProviderDashboardPage] Failed to fetch dashboard stats:", err);
            } finally {
                if (isMounted) {
                    setIsLoading(false);
                }
            }
        };

        if (user) {
            fetchStats();
        }

        return () => {
            isMounted = false;
            abortController.abort();
        };
    }, [user, locale]);

    return (
        <div className="max-w-6xl mx-auto space-y-8">
            {/* Welcome Heading Banner */}
            <div className="bg-white p-6 md:p-8 border border-slate-200 rounded-2xl shadow-xs relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/5 rounded-full blur-2xl pointer-events-none"></div>
                <div className="space-y-2">
                    <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        {t("welcome")}
                    </h1>
                    <p className="text-sm text-slate-500 leading-relaxed max-w-2xl">
                        {t("subtitle")}
                    </p>
                </div>
            </div>

            {/* Stat Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                    title={t("stats.activeServices")}
                    value={isLoading ? "..." : stats.activeServices}
                    description={t("stats.activeServicesDesc")}
                    icon={
                        <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2" />
                        </svg>
                    }
                />
                <StatCard
                    title={t("stats.openRequests")}
                    value={isLoading ? "..." : stats.openRequests}
                    description={t("stats.openRequestsDesc")}
                    icon={
                        <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                    }
                />
                <StatCard
                    title={t("stats.activeOrders")}
                    value={isLoading ? "..." : stats.activeOrders}
                    description={t("stats.activeOrdersDesc")}
                    icon={
                        <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    }
                />
                <StatCard
                    title={t("stats.currentPlan")}
                    value={isLoading ? "..." : stats.currentPlan}
                    description={t("stats.currentPlanDesc")}
                    icon={
                        <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                        </svg>
                    }
                />
            </div>

            {/* Quick Actions Block */}
            <div className="space-y-4">
                <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">
                    {t("actions.title")}
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                    {/* Create Service */}
                    <Link href={`/${locale}/provider/services/new/`} className="block">
                        <Card className="hover:border-violet-300 hover:shadow-md transition duration-200 p-5 flex flex-col items-center text-center h-full justify-center group" hoverable>
                            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center mb-3 group-hover:scale-105 transition">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-800 tracking-tight">{t("actions.createService")}</span>
                        </Card>
                    </Link>

                    {/* Find Requests */}
                    <Link href={`/${locale}/provider/requests/`} className="block">
                        <Card className="hover:border-violet-300 hover:shadow-md transition duration-200 p-5 flex flex-col items-center text-center h-full justify-center group" hoverable>
                            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center mb-3 group-hover:scale-105 transition">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-800 tracking-tight">{t("actions.browseRequests")}</span>
                        </Card>
                    </Link>

                    {/* My Orders */}
                    <Link href={`/${locale}/provider/orders/`} className="block">
                        <Card className="hover:border-violet-300 hover:shadow-md transition duration-200 p-5 flex flex-col items-center text-center h-full justify-center group" hoverable>
                            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center mb-3 group-hover:scale-105 transition">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-800 tracking-tight">{t("actions.viewOrders")}</span>
                        </Card>
                    </Link>

                    {/* My Chats */}
                    <Link href={`/${locale}/provider/chats/`} className="block">
                        <Card className="hover:border-violet-300 hover:shadow-md transition duration-200 p-5 flex flex-col items-center text-center h-full justify-center group" hoverable>
                            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center mb-3 group-hover:scale-105 transition">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-800 tracking-tight">{t("actions.openChats")}</span>
                        </Card>
                    </Link>

                    {/* Manage Subscription/Billing */}
                    <Link href={`/${locale}/provider/billing/`} className="block">
                        <Card className="hover:border-violet-300 hover:shadow-md transition duration-200 p-5 flex flex-col items-center text-center h-full justify-center group" hoverable>
                            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center mb-3 group-hover:scale-105 transition">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                                </svg>
                            </div>
                            <span className="text-sm font-bold text-slate-800 tracking-tight">{t("actions.billing")}</span>
                        </Card>
                    </Link>
                </div>
            </div>
        </div>
    );
}
