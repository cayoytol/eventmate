// frontend/src/app/[locale]/(dashboard)/orders/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import type { OrderListItem, OrderStatus } from "@/types/orders";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function OrdersPage() {
    const locale = useLocale();
    const t = useTranslations("dashboard.orders");
    const tCommon = useTranslations("common");
    const tRequests = useTranslations("dashboard.requests");
    const tPayments = useTranslations("payments");

    const [orders, setOrders] = useState<OrderListItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchOrders = async () => {
        setIsLoading(true);
        setError(null);

        try {
            const { data } = await api.get<OrderListItem[]>("/orders/");
            // Sort by created_at descending (newest first)
            const sorted = [...data].sort(
                (a, b) =>
                    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setOrders(sorted);
        } catch (err: any) {
            setError(err?.response?.data?.detail || t("errorTitle"));
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const formatPrice = (priceStr: string) => {
        const price = parseFloat(priceStr);
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

    const getStatusLabel = (status: OrderStatus) => {
        return t(`status.${status}`);
    };

    if (isLoading) {
        return (
            <div className="max-w-6xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto space-y-6">
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
            </div>

            {error ? (
                <div className="rounded-2xl bg-red-50 border border-red-100 p-5">
                    <div className="font-semibold text-red-800 mb-1">{t("errorTitle")}</div>
                    <div className="text-sm text-red-600 mb-4">{error}</div>
                    <Button
                        onClick={fetchOrders}
                        variant="outline"
                        size="sm"
                    >
                        {t("retry")}
                    </Button>
                </div>
            ) : null}

            {!error && orders.length === 0 ? (
                <EmptyState
                    title={t("emptyTitle")}
                    description={t("emptyText")}
                    action={
                        <div className="mt-4">
                            <Link href={`/${locale}/dashboard/requests/new`}>
                                <Button>{tRequests("createNew")}</Button>
                            </Link>
                        </div>
                    }
                />
            ) : null}

            {!error && orders.length > 0 ? (
                <div className="grid grid-cols-1 gap-4">
                    {orders.map((order) => (
                        <Card
                            key={order.id}
                            className="border border-slate-200 hover:border-violet-200 transition-all duration-300 p-5 sm:p-6 rounded-2xl shadow-xs"
                            hoverable
                        >
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-100">
                                <div className="space-y-1.5">
                                    <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                                        {t("fields.orderId")} #{order.id}
                                    </div>
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <StatusBadge status={order.status} label={getStatusLabel(order.status)} />
                                        <span className={`inline-flex items-center px-2.5 py-0.5 text-xs font-bold rounded-full border ${
                                            order.payment_status === 'paid'
                                                ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                                                : 'bg-amber-50 text-amber-700 border-amber-100'
                                        }`}>
                                            {tPayments(order.payment_status === 'paid' ? 'paidSuccess' : 'requiredTitle')}
                                        </span>
                                    </div>
                                </div>
                                <div className="sm:text-right">
                                    <div className="text-2xl font-extrabold text-violet-600">
                                        {formatPrice(order.price_agreed)}
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4 py-4">
                                <div>
                                    <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">
                                        {t("fields.provider")}
                                    </div>
                                    <div className="text-sm font-semibold text-slate-800 truncate">
                                        {order.provider?.email ?? tCommon("unknown")}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">
                                        {t("fields.created")}
                                    </div>
                                    <div className="text-sm font-semibold text-slate-800">
                                        {formatDate(order.created_at)}
                                    </div>
                                </div>
                            </div>

                            <div className="flex justify-end pt-2">
                                <Link href={`/${locale}/dashboard/orders/${order.id}`}>
                                    <Button variant="outline" size="sm" className="font-bold rounded-xl">
                                        {t("view")}
                                    </Button>
                                </Link>
                            </div>
                        </Card>
                    ))}
                </div>
            ) : null}
        </div>
    );
}
