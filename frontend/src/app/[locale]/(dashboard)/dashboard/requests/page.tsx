// frontend/src/app/[locale]/(dashboard)/dashboard/requests/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/routing";
import { api } from "@/lib/api";
import type { EventRequest, PaginatedResponse } from "@/types/marketplace";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";

export default function RequestsPage() {
    const locale = useLocale();
    const t = useTranslations("dashboard.requests");

    const [requests, setRequests] = useState<EventRequest[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchRequests = async () => {
            try {
                const { data } = await api.get<PaginatedResponse<EventRequest> | EventRequest[]>(
                    "/requests/"
                );
                const requestsArray = Array.isArray(data) ? data : (data?.results || []);
                setRequests(requestsArray);
            } catch (err: any) {
                console.error("Failed to load requests:", err);
                setError(err?.response?.data?.detail || "Failed to load requests");
                setRequests([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchRequests();
    }, []);

    const getStatusLabel = (status: EventRequest["status"]) => {
        switch (status) {
            case "open":
                return t("statusOpen");
            case "offers":
                return t("statusOffers");
            case "confirmed":
                return t("statusAccepted");
            case "completed":
                return t("statusCompleted");
            case "cancelled":
                return t("statusCancelled");
            default:
                return status;
        }
    };

    const getCategoryName = (category: EventRequest["category"]) => {
        switch (locale) {
            case "en":
                return category.name_en;
            case "kz":
                return category.name_kz;
            default:
                return category.name_ru;
        }
    };

    const formatBudget = (min: number | null, max: number | null) => {
        if (!min && !max) return "N/A";
        if (min && max) return `${min.toLocaleString()} - ${max.toLocaleString()} ₸`;
        if (min) return t("budgetFrom", { amount: min.toLocaleString() });
        if (max) return t("budgetTo", { amount: max.toLocaleString() });
        return "N/A";
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString(locale, {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
    };

    if (isLoading) {
        return (
            <div className="space-y-6 max-w-5xl mx-auto">
                <div className="flex items-center justify-between pb-4 border-b border-slate-200">
                    <div className="h-8 w-48 bg-neutral-200 rounded-lg animate-pulse" />
                    <div className="h-10 w-36 bg-neutral-200 rounded-lg animate-pulse" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="p-6 border border-slate-200 bg-white rounded-3xl space-y-4">
                            <Skeleton className="h-5 w-24 rounded-full" />
                            <Skeleton className="h-7 w-3/4" />
                            <Skeleton className="h-4 w-1/2" />
                            <Skeleton className="h-10 w-full rounded-xl" />
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-6xl mx-auto">
            {/* PageHeader section */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-6 border border-slate-200 rounded-2xl shadow-xs">
                <div className="space-y-1">
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        {t("title")}
                    </h1>
                    <p className="text-sm text-slate-500">
                        {t("subtitle")}
                    </p>
                </div>
                <Link
                    href="/dashboard/requests/new"
                    className="inline-flex items-center justify-center gap-2 px-5 py-3 bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold rounded-xl shadow-md shadow-violet-100 transition duration-200 active:scale-95 shrink-0 self-start sm:self-auto"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                    </svg>
                    <span>{t("createNew")}</span>
                </Link>
            </div>

            {error ? (
                <div className="rounded-2xl bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 text-sm font-medium">
                    {error}
                </div>
            ) : null}

            {requests.length === 0 ? (
                <EmptyState
                    title={t("empty")}
                    description={t("emptyDescription")}
                    action={
                        <Link
                            href="/dashboard/requests/new"
                            className="inline-flex items-center gap-2 px-5 py-2.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl text-sm font-bold shadow-md shadow-violet-100 transition active:scale-95"
                        >
                            {t("createNew")}
                        </Link>
                    }
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {requests.map((request) => (
                        <Card key={request.id} hoverable className="flex flex-col justify-between border border-slate-200 p-6 rounded-2xl shadow-xs">
                            <div className="space-y-4">
                                {/* Category and Status row */}
                                <div className="flex items-center justify-between gap-3">
                                    <span className="inline-block px-2.5 py-0.5 text-[10px] font-extrabold uppercase bg-violet-50 text-violet-700 border border-violet-100 rounded-full">
                                        {getCategoryName(request.category)}
                                    </span>
                                    <StatusBadge
                                        status={request.status}
                                        label={getStatusLabel(request.status)}
                                    />
                                </div>

                                {/* Title */}
                                <h3 className="text-lg font-bold text-slate-900 line-clamp-1 leading-snug">
                                    {request.title}
                                </h3>

                                {/* Info rows */}
                                <div className="space-y-2 text-xs text-slate-500 border-t border-slate-100 pt-3">
                                    <div className="flex items-center gap-2">
                                        <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                        </svg>
                                        <span>{request.city}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                        </svg>
                                        <span>{formatDate(request.event_date)}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        <span className="font-semibold text-slate-700">
                                            {formatBudget(request.budget_min, request.budget_max)}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Bottom row / Actions */}
                            <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between">
                                <span className="text-xs font-bold text-slate-500 bg-slate-50 border border-slate-100 px-2.5 py-1 rounded-lg">
                                    {t("offers")}: <span className="text-slate-900 font-extrabold">{request.offers_count}</span>
                                </span>
                                <Link
                                    href={`/dashboard/requests/${request.id}`}
                                    className="inline-flex items-center justify-center rounded-xl bg-violet-50 text-violet-600 border border-violet-100 px-4 py-2 text-xs font-bold transition hover:bg-violet-100 active:scale-95 shadow-3xs"
                                >
                                    {t("viewDetails")}
                                </Link>
                            </div>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
