"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS, orderUrl } from "@/lib/api/endpoints";
import { orderCheckInUrl, orderCompleteUrl, orderCancelUrl } from "@/lib/api/order-actions";
import type { Order } from "@/types/marketplace";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";

export default function OrderDetailPage(props: { params: Promise<{ id: string }> }) {
    const params = use(props.params);
    const { id } = params;

    const locale = useLocale();
    const t = useTranslations("provider.orders");
    const tCommon = useTranslations("common");
    const router = useRouter();

    const [order, setOrder] = useState<Order | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Action states
    const [token, setToken] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);

    // Cancel state
    const [isCancelling, setIsCancelling] = useState(false);
    const [cancelReason, setCancelReason] = useState("");

    // Review reply state
    const tReviews = useTranslations("reviews");
    const [replyText, setReplyText] = useState("");
    const [isSubmittingReply, setIsSubmittingReply] = useState(false);
    const [replyError, setReplyError] = useState<string | null>(null);

    const fetchOrder = async () => {
        try {
            const { data } = await api.get<Order>(orderUrl(id));
            setOrder(data);
        } catch (err: any) {
            console.error("Failed to load order:", err);
            setError("Failed to load order details");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchOrder();
    }, [id]);

    const handleAction = async (type: 'check-in' | 'complete') => {
        if (!token) return;
        setIsSubmitting(true);
        setActionError(null);
        setSuccessMsg(null);

        try {
            let url = "";
            let successText = "";

            if (type === 'check-in') {
                url = orderCheckInUrl(id);
                successText = t("successCheckIn");
            } else {
                url = orderCompleteUrl(id);
                successText = t("successComplete");
            }

            await api.post(url, { token });
            setSuccessMsg(successText);
            setToken("");
            await fetchOrder();
        } catch (err: any) {
            console.error("Action failed:", err);
            const rawError = err?.response?.data?.detail || "Action failed";

            // Production-ready error messages
            let userFriendlyMsg = rawError;
            if (rawError.includes("Invalid") || rawError.includes("expired")) {
                userFriendlyMsg = type === 'check-in'
                    ? t("invalidQrStart")
                    : t("invalidQrFinish");
            }

            setActionError(userFriendlyMsg);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleCancel = async () => {
        if (!window.confirm(t("cancelConfirm"))) return;
        setIsSubmitting(true);
        setActionError(null);

        try {
            await api.post(orderCancelUrl(id), { reason: cancelReason });
            setSuccessMsg(t("successCancel"));
            setIsCancelling(false);
            await fetchOrder();
        } catch (err: any) {
            console.error("Cancel failed:", err);
            const msg = err?.response?.data?.detail || "Cancel failed";
            setActionError(msg);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleReplySubmit = async () => {
        if (!order || !replyText.trim()) return;
        setIsSubmittingReply(true);
        setReplyError(null);

        try {
            await api.patch(ENDPOINTS.ORDER_REVIEW_REPLY(order.id), {
                provider_reply: replyText.trim(),
            });
            await fetchOrder();
        } catch (err: any) {
            setReplyError(err?.response?.data?.detail || "Failed to submit reply");
        } finally {
            setIsSubmittingReply(false);
        }
    };

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

    const formatDateTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const formatter = new Intl.DateTimeFormat(locale, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
        return formatter.format(date);
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    if (!order) {
        return (
            <div className="max-w-4xl mx-auto py-12">
                <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center font-medium">Order not found</div>
            </div>
        );
    }

    const isConfirmed = order.status === 'confirmed';
    const isInProgress = order.status === 'in_progress';
    const isCompleted = order.status === 'completed';
    const isCancelled = order.status === 'cancelled';

    const eventDate = order.service_snapshot?.event_date || order.event_date || order.request?.event_date;

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            <button
                onClick={() => router.back()}
                className="inline-flex items-center text-sm font-medium text-neutral-500 hover:text-violet-650 transition gap-1"
            >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
                {t("back")}
            </button>

            {/* Header / Summary Card */}
            <Card className="border border-neutral-100 p-6">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div className="space-y-3">
                        <div className="space-y-1">
                            <h1 className="text-xl sm:text-2xl font-extrabold text-neutral-900 tracking-tight">
                                {t("orderId", { id: order.id }).replace("Order", "").trim() ? t("orderId", { id: order.id }) : `Order #${order.id}`}
                            </h1>
                            <div className="flex flex-wrap items-center gap-2">
                                <StatusBadge status={order.status} label={t(`statuses.${order.status}`)} />
                                {order.payment_status !== 'paid' && (
                                    <span className="inline-flex items-center px-3 py-1 rounded-lg text-sm font-semibold bg-amber-50 text-amber-700 border border-amber-200/50">
                                        💳 {t("waitingPayment")}
                                    </span>
                                )}
                            </div>
                        </div>

                        {order.service_snapshot && (
                            <div className="pt-2 border-t border-neutral-100/60">
                                <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-0.5">{t("service")}</div>
                                <div className="font-bold text-neutral-800 text-base">{order.service_snapshot.title}</div>
                                {(order.service_snapshot.category_name || order.service_snapshot.city) && (
                                    <div className="text-xs text-neutral-550 mt-1">
                                        {[order.service_snapshot.category_name, order.service_snapshot.city]
                                            .filter(Boolean)
                                            .join(' • ')}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="sm:text-right shrink-0">
                        <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">{t("price")}</div>
                        <div className="text-3xl font-extrabold text-violet-650">
                            {formatPrice(order.price_agreed)}
                        </div>
                    </div>
                </div>
            </Card>

            {/* Order details grid */}
            <Card className="border border-neutral-100 p-6">
                <h2 className="text-lg font-bold text-neutral-800 mb-4 pb-2 border-b border-neutral-100">
                    {locale === 'en' ? 'Client & Event Information' : 'Информация о клиенте и событии'}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">{t("client")}</div>
                        <div className="text-sm font-semibold text-neutral-800 break-all">{order.client_email}</div>
                    </div>
                    <div>
                        <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">{t("eventDate")}</div>
                        <div className="text-sm font-semibold text-neutral-800">
                            {eventDate ? formatDate(eventDate) : tCommon("notSpecified")}
                        </div>
                    </div>
                    <div>
                        <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">{t("createdAt")}</div>
                        <div className="text-sm font-semibold text-neutral-800">{formatDateTime(order.created_at)}</div>
                    </div>
                    {order.checkin_at && (
                        <div>
                            <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">{t("startedAt")}</div>
                            <div className="text-sm font-semibold text-neutral-800">{formatDateTime(order.checkin_at)}</div>
                        </div>
                    )}
                    {order.completed_at && (
                        <div>
                            <div className="text-xs text-neutral-400 font-semibold uppercase tracking-wider mb-1">{t("completedAt")}</div>
                            <div className="text-sm font-semibold text-neutral-800">{formatDateTime(order.completed_at)}</div>
                        </div>
                    )}
                </div>
            </Card>

            {/* Actions Block */}
            {(isConfirmed || isInProgress) && (
                <Card className="border border-neutral-100 p-6 space-y-4">
                    <h2 className="text-lg font-bold text-neutral-850">{t("actions")}</h2>

                    {/* Payment Warning */}
                    {order.payment_status !== 'paid' && (
                        <div className="bg-amber-50 border border-amber-200 text-amber-850 p-4 rounded-2xl text-center space-y-2">
                            <div className="text-3xl">⏳</div>
                            <p className="font-bold text-sm">{t("waitingPayment")}</p>
                            <p className="text-xs text-amber-700">Actions will be available after payment is completed.</p>
                        </div>
                    )}

                    {successMsg && (
                        <div className="bg-green-50 border border-green-200 text-green-700 p-4 rounded-xl text-center text-sm font-bold">
                            {successMsg}
                        </div>
                    )}

                    {actionError && (
                        <div className="bg-red-50 border border-red-200 text-red-650 p-4 rounded-xl text-center text-sm">
                            {actionError}
                        </div>
                    )}

                    <div className="bg-violet-50/50 border border-violet-100 rounded-2xl p-4 flex gap-4 items-start">
                        <div className="text-3xl shrink-0 mt-0.5">📱</div>
                        <div className="space-y-1">
                            <p className="font-bold text-sm text-violet-900">
                                {isConfirmed ? t("qrStartInstruction") : t("qrFinishInstruction")}
                            </p>
                            <p className="text-xs text-violet-750 leading-relaxed">
                                {t("qrInstructionDetails", { action: isConfirmed ? t("showQrStart") : t("showQrFinish") })}
                                {" "}
                                {t("qrScanOrToken")}
                            </p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <Textarea
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            label={t("jwtPlaceholder")}
                            placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                            disabled={order.payment_status !== 'paid'}
                            rows={3}
                            className="font-mono text-xs disabled:bg-neutral-50 disabled:cursor-not-allowed"
                        />

                        <Button
                            onClick={() => handleAction(isConfirmed ? 'check-in' : 'complete')}
                            disabled={!token || isSubmitting || order.payment_status !== 'paid'}
                            isLoading={isSubmitting}
                            className={`w-full justify-center text-sm font-bold py-3 ${
                                isConfirmed ? 'bg-violet-600 hover:bg-violet-700' : 'bg-indigo-600 hover:bg-indigo-700'
                            }`}
                        >
                            {isConfirmed ? t("checkIn") : t("complete")}
                        </Button>
                    </div>
                </Card>
            )}

            {/* Cancel Block */}
            {isConfirmed && !successMsg && (
                <Card className="border border-neutral-100 p-6 text-center">
                    {!isCancelling ? (
                        <button
                            onClick={() => setIsCancelling(true)}
                            className="text-red-600 text-sm font-semibold hover:underline"
                        >
                            {t("cancel")}
                        </button>
                    ) : (
                        <div className="max-w-md mx-auto space-y-4 text-left">
                            <Textarea
                                label={t("reason")}
                                value={cancelReason}
                                onChange={(e) => setCancelReason(e.target.value)}
                                placeholder="Describe why you need to cancel this order..."
                                rows={3}
                            />
                            <div className="flex gap-3">
                                <Button
                                    onClick={() => setIsCancelling(false)}
                                    variant="outline"
                                    className="flex-1"
                                    size="sm"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    onClick={handleCancel}
                                    disabled={!cancelReason || isSubmitting}
                                    isLoading={isSubmitting}
                                    className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                                    size="sm"
                                >
                                    Confirm Cancel
                                </Button>
                            </div>
                        </div>
                    )}
                </Card>
            )}

            {/* Review Section */}
            {order.review && (
                <Card className="border border-neutral-100 p-6 space-y-4">
                    <h2 className="text-lg font-bold text-neutral-850">{tReviews("title", { fallback: "Client Review" })}</h2>

                    <div className="flex items-center gap-2">
                        <span className="font-extrabold text-lg text-amber-500">
                            ★ {order.review.rating}/5
                        </span>
                        <span className="text-xs text-neutral-500 font-medium">
                            {t("reviewByClient", { clientName: order.review.client_name })}
                        </span>
                    </div>

                    {order.review.text && (
                        <p className="text-neutral-700 bg-neutral-50 border border-neutral-100/50 p-4 rounded-2xl text-sm leading-relaxed">
                            {order.review.text}
                        </p>
                    )}

                    {order.review.provider_reply ? (
                        <div className="border-l-4 border-violet-500 pl-4 space-y-1">
                            <div className="text-xs font-semibold text-neutral-500">
                                {tReviews("providerReply", { fallback: "Your Response" })}
                            </div>
                            <p className="text-neutral-700 bg-violet-50/30 border border-violet-100/30 p-4 rounded-2xl text-sm leading-relaxed">
                                {order.review.provider_reply}
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-4 pt-4 border-t border-neutral-100/60">
                            <Textarea
                                label={tReviews("providerReply", { fallback: "Reply to review" })}
                                value={replyText}
                                onChange={(e) => setReplyText(e.target.value)}
                                rows={3}
                                placeholder={tReviews("replyPlaceholder", { fallback: "Write your response..." })}
                            />
                            {replyError && (
                                <div className="text-red-650 text-xs font-medium">{replyError}</div>
                            )}
                            <Button
                                onClick={handleReplySubmit}
                                disabled={isSubmittingReply || !replyText.trim()}
                                isLoading={isSubmittingReply}
                                size="sm"
                            >
                                {tReviews("replySubmit", { fallback: "Submit Reply" })}
                            </Button>
                        </div>
                    )}
                </Card>
            )}
        </div>
    );
}
