// frontend/src/app/[locale]/(provider)/provider/requests/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { EventRequest } from "@/types/marketplace";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function ProviderRequestsFeed() {
    const locale = useLocale();
    const t = useTranslations("provider.requests");

    const [requests, setRequests] = useState<EventRequest[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchRequests = async () => {
            try {
                const { data } = await api.get(ENDPOINTS.REQUESTS);
                const list = Array.isArray(data) ? data : (data?.results ?? []);
                setRequests(list);
            } catch (err: any) {
                console.error("Failed to load requests:", err);
                setError("Failed to load requests");
            } finally {
                setIsLoading(false);
            }
        };

        fetchRequests();
    }, []);

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="max-w-4xl mx-auto py-6">
                <Card className="bg-red-50 border border-red-100 text-red-700 p-5 rounded-2xl font-semibold">{error}</Card>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* PageHeader section */}
            <div className="bg-white p-6 border border-slate-200 rounded-2xl shadow-xs">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    {t("title")}
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                    {t("subtitle")}
                </p>
            </div>

            {requests.length === 0 ? (
                <EmptyState
                    title={t("empty")}
                    description={locale === 'en' ? 'Check back later for new client requests matching your profile.' : 'Загляните позже, чтобы увидеть новые заявки от клиентов.'}
                />
            ) : (
                <div className="grid grid-cols-1 gap-4">
                    {requests.map((req) => (
                        <RequestOpportunityCard key={req.id} request={req} locale={locale} t={t} />
                    ))}
                </div>
            )}
        </div>
    );
}

function RequestOpportunityCard({ request, locale, t }: { request: EventRequest; locale: string; t: any }) {
    const tCommon = useTranslations("common");
    const categoryName = request.category
        ? (request.category[`name_${locale as 'ru' | 'en' | 'kz'}`] || request.category.name_en)
        : tCommon("notSpecified");
    
    const formatBudget = (min: number | null | undefined, max: number | null | undefined) => {
        if (!min && !max) return t("budgetNotSpecified");
        if (min && max) return `${min.toLocaleString()} - ${max.toLocaleString()} ₸`;
        if (min) return t("budgetFrom", { amount: min.toLocaleString() });
        if (max) return t("budgetTo", { amount: max.toLocaleString() });
        return t("budgetNotSpecified");
    };

    return (
        <Card className="hover:border-violet-200 hover:shadow-md transition-all duration-300 p-6 rounded-2xl border border-slate-200 bg-white" hoverable>
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
                <div>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-violet-50 text-violet-700 border border-violet-100">
                        {categoryName}
                    </span>
                    <h3 className="font-extrabold text-lg text-slate-900 mt-2.5 leading-snug tracking-tight">{request.title}</h3>
                </div>
                <div className="text-left sm:text-right shrink-0">
                    <div className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 bg-slate-50 border border-slate-100 rounded-lg px-2.5 py-1">
                        <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        <span>
                            {new Date(request.event_date).toLocaleDateString(locale, {
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                            })}
                        </span>
                    </div>
                    <div className="text-xs text-slate-500 font-semibold mt-1.5 flex items-center gap-1 sm:justify-end">
                        <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        <span>{request.city}</span>
                    </div>
                </div>
            </div>

            <p className="text-sm text-slate-500 line-clamp-2 leading-relaxed mb-4 font-medium">
                {request.description}
            </p>

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-4 border-t border-slate-100 mt-3">
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm font-medium">
                    <div className="flex items-center gap-1.5">
                        <span className="text-slate-500 font-medium">{t("budget")}:</span>
                        <span className="font-extrabold text-slate-900">
                            {formatBudget(request.budget_min, request.budget_max)}
                        </span>
                    </div>
                    {request.offers_count > 0 && (
                        <div className="inline-flex items-center text-xs font-bold text-slate-600 bg-slate-50 border border-slate-100 px-2.5 py-0.5 rounded-lg">
                            {request.offers_count} {t("offersCount")}
                        </div>
                    )}
                </div>

                <Link href={`/${locale}/provider/requests/${request.id}`} className="w-full sm:w-auto">
                    <Button variant="primary" size="sm" className="w-full sm:w-auto font-bold rounded-xl shadow-sm shadow-violet-100">
                        {t("createOffer")}
                    </Button>
                </Link>
            </div>
        </Card>
    );
}
