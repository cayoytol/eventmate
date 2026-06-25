"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { Order } from "@/types/marketplace";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function ProviderOrdersPage() {
    const locale = useLocale();
    const t = useTranslations("provider.orders");
    const tCommon = useTranslations("common");

    const [orders, setOrders] = useState<Order[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchOrders = async () => {
        setIsLoading(true);
        setError(null);
        try {
            // Backend auto-filters by user.role (provider/client)
            // OrderViewSet.get_queryset() handles role-based filtering on the backend
            const response = await api.get(ENDPOINTS.ORDERS);

            let results: Order[];
            if (Array.isArray(response.data)) {
                results = response.data;
            } else if (response.data?.results) {
                results = response.data.results;
            } else {
                results = [];
            }

            // Sort by created_at descending (newest first)
            const sorted = [...results].sort(
                (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );

            setOrders(sorted);
        } catch (err: any) {
            console.error("❌ Failed to load orders:", err);
            setError("Failed to load orders");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchOrders();
    }, []);

    const formatPrice = (priceStr: string) => {
        const price = parseFloat(priceStr || "0");
        const formatter = new Intl.NumberFormat(locale, {
            maximumFractionDigits: 0,
        });
        return `${formatter.format(price)} ₸`;
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        const formatter = new Intl.DateTimeFormat(locale, {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
        return formatter.format(date);
    };

    if (isLoading) {
        return (
            <div className="max-w-5xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-neutral-900 tracking-tight">{t("title")}</h1>
                <p className="text-sm text-neutral-500 mt-1">
                    {t("subtitle")}
                </p>
            </div>

            {error ? (
                <div className="rounded-2xl bg-red-50 border border-red-100 p-5">
                    <div className="font-semibold text-red-800 mb-1">Error Loading Orders</div>
                    <div className="text-sm text-red-600 mb-4">{error}</div>
                    <Button onClick={fetchOrders} variant="outline" size="sm">
                        Retry
                    </Button>
                </div>
            ) : null}

            {!error && orders.length === 0 ? (
                <EmptyState
                    title={t("empty")}
                    description={t("emptyDescription")}
                />
            ) : null}

            {!error && orders.length > 0 ? (
                <div className="grid grid-cols-1 gap-4">
                    {orders.map((order) => {
                        const price = order.price_agreed || '0';
                        const title = order.service_snapshot?.title || order.request?.title || 'Order';
                        const eventDate = order.service_snapshot?.event_date || order.event_date || order.request?.event_date;

                        return (
                            <Card
                                key={order.id}
                                className="border border-neutral-100 hover:border-violet-100 transition-all duration-300 p-5 sm:p-6"
                                hoverable
                            >
                                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-neutral-100">
                                    <div className="space-y-1">
                                        <div className="text-xs text-neutral-500 font-semibold uppercase tracking-wider">
                                            {t("orderId", { id: order.id }).replace("Order", "").trim() ? t("orderId", { id: order.id }) : `Order #${order.id}`}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <StatusBadge status={order.status} label={t(`statuses.${order.status}`)} />
                                            {order.payment_status !== 'paid' && (
                                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200/50">
                                                    {t("waitingPayment")}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="sm:text-right">
                                        <div className="text-2xl font-extrabold text-violet-600">
                                            {formatPrice(price)}
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 py-4">
                                    <div>
                                        <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">
                                            {t("serviceOrEvent")}
                                        </div>
                                        <div className="text-sm font-semibold text-neutral-800 truncate" title={title}>
                                            {title}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">
                                            {t("client")}
                                        </div>
                                        <div className="text-sm font-semibold text-neutral-800 truncate" title={order.client_email}>
                                            {order.client_email}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">
                                            {t("eventDate")}
                                        </div>
                                        <div className="text-sm font-semibold text-neutral-800">
                                            {eventDate ? formatDate(eventDate) : tCommon("notSpecified")}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex justify-end pt-2 border-t border-neutral-50 mt-2">
                                    <Link href={`/${locale}/provider/orders/${order.id}`}>
                                        <Button variant="outline" size="sm">
                                            {t("view")}
                                        </Button>
                                    </Link>
                                </div>
                            </Card>
                        );
                    })}
                </div>
            ) : null}
        </div>
    );
}
