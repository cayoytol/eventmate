// frontend/src/app/[locale]/(dashboard)/requests/[id]/page.tsx
"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { offerAcceptUrl } from "@/lib/api/endpoints";
import { useAuthStore } from "@/store/useAuthStore";
import type { EventRequest, Offer } from "@/types/marketplace";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";

export default function RequestDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const locale = useLocale();
    const router = useRouter();
    const { user } = useAuthStore();
    const t = useTranslations("dashboard.requests");
    const tDetail = useTranslations("dashboard.requests.detail");
    const tOffer = useTranslations("dashboard.requests.offer");
    const tCommon = useTranslations("common");

    const [request, setRequest] = useState<EventRequest | null>(null);
    const [offers, setOffers] = useState<Offer[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isLoadingOffers, setIsLoadingOffers] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [acceptingOfferId, setAcceptingOfferId] = useState<number | null>(null);

    // Safe translation wrappers to prevent crashes on missing keys
    const safeT = (key: string, fallback?: string): string => {
        try {
            return t(key as any);
        } catch (error) {
            console.warn(`Missing translation: dashboard.requests.${key}`, error);
            return fallback || key;
        }
    };

    const safeTOffer = (key: string, fallback?: string): string => {
        try {
            return tOffer(key as any);
        } catch (error) {
            console.warn(`Missing translation: dashboard.requests.offer.${key}`, error);
            return fallback || key;
        }
    };

    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch request details
                const { data } = await api.get<EventRequest>(
                    `/requests/${id}/`
                );
                setRequest(data);

                // Fetch offers for this request
                setIsLoadingOffers(true);
                const { data: offersData } = await api.get<Offer[]>(
                    `/offers/by-request/${id}/`
                );
                setOffers(offersData);
            } catch (err: any) {
                setError(err?.response?.data?.detail || tDetail("errorLoading"));
            } finally {
                setIsLoading(false);
                setIsLoadingOffers(false);
            }
        };

        fetchData();
    }, [id, tDetail]);

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

    const getStatusLabel = (status: EventRequest["status"]) => {
        try {
            switch (status) {
                case "open":
                    return t("statusOpen");
                case "offers":
                    return t("statusOffers");
                case "confirmed":
                    return t("statusConfirmed");
                case "completed":
                    return t("statusCompleted");
                case "cancelled":
                    return t("statusCancelled");
                default:
                    return status;
            }
        } catch (error) {
            // Fallback: return raw status if translation missing
            console.warn(`Missing translation for status: ${status}`, error);
            return status;
        }
    };

    const formatDate = (dateStr: string | null | undefined) => {
        if (!dateStr) return '—';
        try {
            const date = new Date(dateStr);
            if (isNaN(date.getTime())) return '—';
            return date.toLocaleDateString(locale, {
                year: "numeric",
                month: "long",
                day: "numeric",
            });
        } catch {
            return '—';
        }
    };

    const formatBudget = (min: number | null | undefined, max: number | null | undefined) => {
        if (!min && !max) return 'N/A';
        if (min && max) return `${min.toLocaleString()} - ${max.toLocaleString()} ₸`;
        if (min) return t("budgetFrom", { amount: min.toLocaleString() });
        if (max) return t("budgetTo", { amount: max.toLocaleString() });
        return 'N/A';
    };

    const formatPrice = (price: number | null | undefined) => {
        if (price == null) return tCommon("notSpecified");
        return `${price.toLocaleString()} ₸`;
    };

    const handleAcceptOffer = async (offerId: number) => {
        const confirmed = window.confirm(tOffer("confirmAccept"));
        if (!confirmed) return;

        setAcceptingOfferId(offerId);

        try {
            const { data } = await api.post(offerAcceptUrl(offerId));

            // Show success message (можно использовать toast в будущем)
            alert(tOffer("acceptSuccess"));

            // Redirect to order if order_id returned
            if (data.order_id) {
                router.push(`/${locale}/dashboard/orders/${data.order_id}`);
            } else {
                router.push(`/${locale}/dashboard/orders`);
            }
        } catch (err: any) {
            const msg = err?.response?.data?.detail || tOffer("acceptError");
            alert(msg);
        } finally {
            setAcceptingOfferId(null);
        }
    };

    const canAcceptOffers = request?.status === "offers";

    if (isLoading) {
        return (
            <div className="max-w-5xl mx-auto">
                <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
                </div>
            </div>
        );
    }

    if (error || !request) {
        return (
            <div className="max-w-5xl mx-auto">
                <div className="rounded-2xl bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm mb-4">
                    {error || tDetail("errorLoading")}
                </div>
                <Link
                    href={`/${locale}/dashboard/requests`}
                    className="text-sm text-violet-600 font-semibold hover:text-violet-700 transition"
                >
                    {tDetail("backToList")}
                </Link>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            {/* Back link */}
            <div className="flex items-center">
                <Link
                    href={`/${locale}/dashboard/requests`}
                    className="group inline-flex items-center text-sm font-bold text-slate-500 hover:text-violet-600 transition duration-200"
                >
                    <svg className="mr-2 h-4 w-4 transform group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    {tDetail("backToList")}
                </Link>
            </div>

            {/* Request Details Card */}
            <Card className="border border-slate-200 p-6 sm:p-8 rounded-2xl shadow-xs">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6 pb-6 border-b border-slate-100">
                    <div>
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                            <span className="text-xs font-extrabold uppercase tracking-wider text-violet-700 bg-violet-50 px-2.5 py-1 rounded-full border border-violet-100">
                                {getCategoryName(request.category)}
                            </span>
                            <StatusBadge status={request.status} label={getStatusLabel(request.status)} />
                        </div>
                        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">{request.title}</h1>
                    </div>
                    <div className="text-left md:text-right">
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{tDetail("budget")}</div>
                        <div className="text-xl sm:text-2xl font-extrabold text-violet-600">
                            {formatBudget(request.budget_min, request.budget_max)}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6 mb-6">
                    <div>
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{tDetail("city")}</div>
                        <div className="font-semibold text-slate-800">{request.city}</div>
                    </div>
                    <div>
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{tDetail("eventDate")}</div>
                        <div className="font-semibold text-slate-800">{formatDate(request.event_date)}</div>
                    </div>
                    <div>
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{tDetail("createdAt")}</div>
                        <div className="font-semibold text-slate-800">{formatDate(request.created_at)}</div>
                    </div>
                    <div>
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{tDetail("status")}</div>
                        <div className="font-semibold text-slate-800">{getStatusLabel(request.status)}</div>
                    </div>
                </div>

                <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                    <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2">{tDetail("description")}</div>
                    <div className="text-slate-700 leading-relaxed whitespace-pre-wrap text-sm">
                        {request.description || <em className="text-slate-450 font-normal italic">{tDetail("noDescription")}</em>}
                    </div>
                </div>
            </Card>

            {/* Offers Section */}
            <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <h2 className="text-xl font-bold text-slate-900">{tDetail("offersTitle")}</h2>
                    <span className="text-xs font-bold text-violet-600 bg-violet-50 px-2.5 py-1 rounded-full border border-violet-100">
                        {offers.length}
                    </span>
                </div>

                {isLoadingOffers ? (
                    <div className="text-center py-12">
                        <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-violet-600 mx-auto mb-2"></div>
                        <span className="text-sm text-slate-500">{tDetail("loadingOffers")}</span>
                    </div>
                ) : offers.length === 0 ? (
                    <EmptyState
                        title={tDetail("noOffers")}
                        description={locale === 'en' ? 'No offers have been submitted for this request yet.' : locale === 'kz' ? 'Бұл өтінімге әлі ұсыныстар түскен жоқ.' : 'На эту заявку ещё не поступило предложений.'}
                    />
                ) : (
                    <div className="grid grid-cols-1 gap-4">
                        {offers.map((offer) => {
                            const providerName = offer.provider?.user?.first_name || offer.provider?.user?.email || tCommon("unknown");
                            const ratingNum = offer.provider?.rating_avg != null ? Number(offer.provider.rating_avg) : null;
                            const statusLabel = offer.status === "sent" ? tOffer("statusSent") : offer.status === "accepted" ? tOffer("statusAccepted") : offer.status;

                            return (
                                <Card key={offer.id} className="border border-slate-200 hover:border-violet-200 transition-all duration-300 p-6 rounded-2xl shadow-xs">
                                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-2">
                                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                                                    {tOffer("from")}
                                                </span>
                                                <StatusBadge status={offer.status} label={statusLabel} />
                                            </div>
                                            <div className="font-bold text-slate-900 text-lg">
                                                {providerName}
                                            </div>
                                            {ratingNum && !isNaN(ratingNum) && (
                                                <div className="flex items-center text-sm text-slate-600 gap-1.5">
                                                    <span className="text-amber-500">★</span>
                                                    <span className="font-semibold">{ratingNum.toFixed(1)}</span>
                                                </div>
                                            )}
                                        </div>

                                        <div className="sm:text-right space-y-1">
                                            <div className="text-2xl font-extrabold text-violet-600">
                                                {formatPrice(offer.price)}
                                            </div>
                                            <div className="text-xs text-slate-400 font-medium">
                                                {offer.delivery_date
                                                    ? `${tOffer("deliveryDate")}: ${formatDate(offer.delivery_date)}`
                                                    : `${tOffer("submitted")}: ${formatDate(offer.created_at)}`
                                                }
                                            </div>
                                        </div>
                                    </div>

                                    {offer.message && (
                                        <div className="mt-4 pt-4 border-t border-slate-100">
                                            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                                                {tOffer("message")}
                                            </div>
                                            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-100 p-4 rounded-xl leading-relaxed whitespace-pre-wrap">
                                                {offer.message}
                                            </div>
                                        </div>
                                    )}

                                    {/* Action button */}
                                    {(() => {
                                        const shouldShowAccept = canAcceptOffers && offer.status === "sent";
                                        return shouldShowAccept ? (
                                            <div className="mt-4 pt-4 border-t border-slate-100">
                                                <Button
                                                    onClick={() => handleAcceptOffer(offer.id)}
                                                    isLoading={acceptingOfferId === offer.id}
                                                    className="w-full sm:w-auto font-bold rounded-xl"
                                                >
                                                    {tOffer("accept")}
                                                </Button>
                                            </div>
                                        ) : null;
                                    })()}
                                </Card>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
