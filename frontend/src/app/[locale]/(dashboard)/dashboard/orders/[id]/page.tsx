// frontend/src/app/[locale]/(dashboard)/orders/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { ENDPOINTS, orderUrl, orderQrCodeUrl, paymentCreateUrl, paymentStatusUrl } from "@/lib/api/endpoints";
import { orderMockPayUrl } from "@/lib/api/order-actions";
import type { OrderDetail, OrderStatus, QrCodeResponse, PaymentStatus } from "@/types/orders";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import { useAuthStore } from "@/store/useAuthStore";

// Dynamic import для QR generation
import QRCode from "qrcode";

export default function OrderDetailPage() {
    const params = useParams();
    const id = String(params.id);
    const locale = useLocale();
    const router = useRouter();
    const t = useTranslations("dashboard.orderDetail");
    const tStatus = useTranslations("dashboard.orders.status");
    const tPayments = useTranslations("payments");
    const tReviews = useTranslations("reviews");
    const tCommon = useTranslations("common");
    const { isAuthenticated } = useAuthStore();

    useEffect(() => {
        if (!isAuthenticated) {
            setOrder(null);
            setQrData(null);
            setQrImageUrl(null);
            setProviderTokenInput("");
            setVerificationSuccess(null);
            setVerificationError(null);
        }
    }, [isAuthenticated]);

    const [order, setOrder] = useState<OrderDetail | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Review state
    const [reviewRating, setReviewRating] = useState(0);
    const [reviewText, setReviewText] = useState("");
    const [isSubmittingReview, setIsSubmittingReview] = useState(false);
    const [reviewError, setReviewError] = useState<string | null>(null);

    // QR state
    const [qrData, setQrData] = useState<QrCodeResponse | null>(null);
    const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);
    const [isGeneratingQr, setIsGeneratingQr] = useState(false);
    const [copySuccess, setCopySuccess] = useState(false);
    const [timeLeft, setTimeLeft] = useState<number | null>(null);

    // Provider QR scanner manual state
    const [providerTokenInput, setProviderTokenInput] = useState("");
    const [isVerifyingToken, setIsVerifyingToken] = useState(false);
    const [verificationError, setVerificationError] = useState<string | null>(null);
    const [verificationSuccess, setVerificationSuccess] = useState<string | null>(null);

    useEffect(() => {
        if (!qrData?.expires_at) {
            setTimeLeft(null);
            return;
        }

        const expiresTime = new Date(qrData.expires_at).getTime();
        if (isNaN(expiresTime)) {
            setTimeLeft(null);
            return;
        }

        const updateTimer = () => {
            const now = Date.now();
            const diff = Math.max(0, Math.floor((expiresTime - now) / 1000));
            setTimeLeft(diff);

            if (diff <= 0) {
                setQrData(null);
                setQrImageUrl(null);
            }
        };

        updateTimer();
        const interval = setInterval(updateTimer, 1000);
        return () => clearInterval(interval);
    }, [qrData]);

    useEffect(() => {
        // Clear QR code state when order capabilities / status change to prevent stale display
        setQrData(null);
        setQrImageUrl(null);
        setVerificationError(null);
        setVerificationSuccess(null);
    }, [order?.status, order?.qr_capabilities]);

    useEffect(() => {
        return () => {
            setQrData(null);
            setQrImageUrl(null);
        };
    }, []);

    // Payment state
    const [isPaying, setIsPaying] = useState(false);
    const [paymentSuccess, setPaymentSuccess] = useState(false);

    // New payment transaction states
    const [latestTx, setLatestTx] = useState<any | null>(null);
    const [activeTx, setActiveTx] = useState<any | null>(null);
    const [isFetchingStatus, setIsFetchingStatus] = useState(false);
    const [statusError, setStatusError] = useState<string | null>(null);
    const [activeProvider, setActiveProvider] = useState<string>("mock");
    const [providerMode, setProviderMode] = useState<string>("sandbox");
    const [providerAvailable, setProviderAvailable] = useState<boolean>(true);
    const [isCapturing, setIsCapturing] = useState(false);
    const [paymentQrUrl, setPaymentQrUrl] = useState<string | null>(null);
    const [pollingCount, setPollingCount] = useState(0);

    // Read search parameters for callback checking
    const searchParams = useSearchParams();
    const queryStatus = searchParams?.get("status");
    const queryTxId = searchParams?.get("transaction_id");
    const queryToken = searchParams?.get("token");

    useEffect(() => {
        if (activeTx?.status === "pending" && activeTx.checkout_url && activeProvider === "paypal") {
            QRCode.toDataURL(activeTx.checkout_url, { width: 200, margin: 2 })
                .then(url => setPaymentQrUrl(url))
                .catch(err => console.error("Failed to generate payment QR code", err));
        } else {
            setPaymentQrUrl(null);
        }
    }, [activeTx, activeProvider]);

    const refreshPaymentStatus = async () => {
        setIsFetchingStatus(true);
        setStatusError(null);
        try {
            const { data } = await api.get<any>(paymentStatusUrl(id));
            setLatestTx(data.latest_transaction);
            setActiveTx(data.active_transaction);
            if (data.active_provider) {
                setActiveProvider(data.active_provider);
            }
            if (data.provider_mode) {
                setProviderMode(data.provider_mode);
            }
            if (data.provider_available !== undefined) {
                setProviderAvailable(data.provider_available);
            }
            
            // If the order backend state is now paid, we refresh the order to unlock QR
            if (data.order_payment_status === "paid") {
                const orderResp = await api.get<OrderDetail>(orderUrl(id));
                setOrder(orderResp.data);
            }
        } catch (err: any) {
            console.error("Failed to fetch payment status:", err);
            setStatusError(err?.response?.data?.detail || "Could not retrieve payment status");
        } finally {
            setIsFetchingStatus(false);
        }
    };

    // Bounded polling for initializing checkouts
    useEffect(() => {
        if (activeTx?.is_initializing && pollingCount < 10) {
            const timer = setTimeout(() => {
                setPollingCount(prev => prev + 1);
                refreshPaymentStatus();
            }, 2000);
            return () => clearTimeout(timer);
        } else if (!activeTx?.is_initializing) {
            setPollingCount(0);
        }
    }, [activeTx?.is_initializing, pollingCount]);

    const handlePaypalCapture = async (paypalOrderId: string) => {
        setIsCapturing(true);
        setError(null);
        try {
            await api.post("/payments/paypal/capture/", {
                paypal_order_id: paypalOrderId
            });
            // Refresh order to unlock QR
            const orderResp = await api.get<OrderDetail>(orderUrl(id));
            setOrder(orderResp.data);
            await refreshPaymentStatus();
        } catch (err: any) {
            setError(err?.response?.data?.detail || "Payment capture failed");
        } finally {
            setIsCapturing(false);
        }
    };

    useEffect(() => {
        if (!id) return;

        const fetchOrder = async () => {
            try {
                const { data } = await api.get<OrderDetail>(orderUrl(id));
                setOrder(data);
            } catch (err: any) {
                if (err?.response?.status === 404) {
                    setError(t("notFound"));
                } else {
                    setError(err?.response?.data?.detail || t("errorTitle"));
                }
            } finally {
                setIsLoading(false);
            }
        };

        const fetchPaymentStatus = async () => {
            setIsFetchingStatus(true);
            setStatusError(null);
            try {
                const { data } = await api.get<any>(paymentStatusUrl(id));
                setLatestTx(data.latest_transaction);
                setActiveTx(data.active_transaction);
                if (data.active_provider) {
                    setActiveProvider(data.active_provider);
                }
                if (data.provider_mode) {
                    setProviderMode(data.provider_mode);
                }
                if (data.provider_available !== undefined) {
                    setProviderAvailable(data.provider_available);
                }
            } catch (err: any) {
                console.error("Failed to fetch payment status:", err);
                setStatusError(err?.response?.data?.detail || "Could not retrieve payment status");
            } finally {
                setIsFetchingStatus(false);
            }
        };

        fetchOrder();
        fetchPaymentStatus();
    }, [id, t]);

    useEffect(() => {
        if (queryToken && activeProvider === "paypal" && id) {
            handlePaypalCapture(queryToken);
            
            const url = new URL(window.location.href);
            url.searchParams.delete("transaction_id");
            url.searchParams.delete("status");
            url.searchParams.delete("token");
            url.searchParams.delete("PayerID");
            window.history.replaceState({}, "", url.toString());
        } else if (queryStatus && queryTxId && id) {
            refreshPaymentStatus();
            
            const url = new URL(window.location.href);
            url.searchParams.delete("transaction_id");
            url.searchParams.delete("status");
            window.history.replaceState({}, "", url.toString());
        }
    }, [queryStatus, queryTxId, queryToken, activeProvider, id]);

    const handleMockPayment = async () => {
        if (!order) return;
        setIsPaying(true);
        setError(null);

        try {
            await api.post(orderMockPayUrl(order.id));
            setPaymentSuccess(true);
            
            // Refresh payment status
            await refreshPaymentStatus();
            
            // Refetch order to get updated payment_status
            const { data } = await api.get<OrderDetail>(orderUrl(id));
            setOrder(data);
            setTimeout(() => setPaymentSuccess(false), 3000);
        } catch (err: any) {
            const msg = err?.response?.data?.detail || "Payment failed";
            setError(msg);
        } finally {
            setIsPaying(false);
        }
    };

    const handleSecurePayment = async () => {
        if (!order) return;
        setIsPaying(true);
        setError(null);

        try {
            const response = await api.post<any>(paymentCreateUrl(order.id));
            const data = response.data;
            const status_code = response.status;
            
            if (status_code === 202 || data.code === "checkout_initializing") {
                setPollingCount(0);
                await refreshPaymentStatus();
            } else if (data.checkout_url) {
                window.location.assign(data.checkout_url);
            } else {
                setError(tPayments("noCheckoutUrl") || "Checkout URL not found.");
            }
        } catch (err: any) {
            if (err?.response?.status === 202) {
                setPollingCount(0);
                await refreshPaymentStatus();
            } else {
                setError(err?.response?.data?.detail || tPayments("createError") || "Payment creation failed.");
            }
        } finally {
            setIsPaying(false);
        }
    };

    const handleSubmitReview = async () => {
        if (!order || reviewRating === 0) return;
        setIsSubmittingReview(true);
        setReviewError(null);

        try {
            await api.post(ENDPOINTS.ORDER_REVIEW(order.id), {
                rating: reviewRating,
                text: reviewText,
            });
            // Refetch to see the review
            const { data } = await api.get<OrderDetail>(orderUrl(order.id));
            setOrder(data);
        } catch (err: any) {
            setReviewError(err?.response?.data?.detail || "Failed to submit review");
        } finally {
            setIsSubmittingReview(false);
        }
    };

    const generateQr = async (type: "start" | "finish") => {
        if (!order || isGeneratingQr) return;

        setIsGeneratingQr(true);
        setError(null);

        try {
            const { data } = await api.get<QrCodeResponse>(
                orderQrCodeUrl(order.id),
                { params: { type } }
            );
            setQrData(data);

            // Generate QR image from token
            const qrUrl = await QRCode.toDataURL(data.token, {
                width: 300,
                margin: 2,
            });
            setQrImageUrl(qrUrl);
        } catch (err: any) {
            const errCode = err?.response?.data?.code;
            let msg = "Failed to generate QR code";
            if (errCode) {
                if (errCode === "order_not_paid") {
                    msg = t("qr.paymentRequired");
                } else if (errCode === "invalid_order_status") {
                    msg = t("qr.invalidStatus");
                } else if (errCode === "qr_not_available") {
                    msg = t("qr.unavailableForAccount");
                } else {
                    msg = err?.response?.data?.detail || msg;
                }
            } else {
                msg = err?.response?.data?.detail || err.message || msg;
            }
            setError(msg);
        } finally {
            setIsGeneratingQr(false);
        }
    };

    const copyToken = async () => {
        if (!qrData) return;

        try {
            await navigator.clipboard.writeText(qrData.token);
            setCopySuccess(true);
            setTimeout(() => setCopySuccess(false), 2000);
        } catch (err) {
            console.error("Failed to copy:", err);
        }
    };

    const verifyProviderToken = async (type: "start" | "finish") => {
        if (!order || isVerifyingToken || !providerTokenInput.trim()) return;

        setIsVerifyingToken(true);
        setVerificationError(null);
        setVerificationSuccess(null);

        const actionPath = type === "start" ? "check-in" : "complete";
        const actionUrl = `/orders/${order.id}/actions/${actionPath}/`;

        try {
            await api.post(actionUrl, { token: providerTokenInput.trim() });
            
            setVerificationSuccess(type === "start" ? t("qr.checkInSuccess") : t("qr.completionSuccess"));
            setProviderTokenInput("");
            
            // Refetch order details to refresh state and capabilities
            const { data } = await api.get<OrderDetail>(orderUrl(order.id));
            setOrder(data);
        } catch (err: any) {
            const errCode = err?.response?.data?.code;
            let msg = "Verification failed.";
            if (errCode) {
                if (errCode === "qr_token_expired" || errCode === "qr_token_replaced") {
                    msg = t("qr.tokenExpired");
                } else if (errCode === "invalid_qr_token") {
                    msg = t("qr.invalidToken");
                } else {
                    msg = err?.response?.data?.detail || msg;
                }
            } else {
                msg = err?.response?.data?.detail || err.message || msg;
            }
            setVerificationError(msg);
        } finally {
            setIsVerifyingToken(false);
        }
    };

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
            hour: "2-digit",
            minute: "2-digit",
        });
        return formatter.format(date);
    };

    const getStatusLabel = (status: OrderStatus) => {
        return tStatus(status);
    };

    const renderQrSection = () => {
        if (!order) return null;

        const caps = order.qr_capabilities || {
            is_client_owner: false,
            is_assigned_provider: false,
            can_generate_start: false,
            can_generate_finish: false,
            can_check_in: false,
            can_complete: false
        };

        // If unpaid and user is the owner, show payment alert / checkout link
        if (order.payment_status !== 'paid' && caps.is_client_owner) {
            return (
                <div className="space-y-4">
                    <p className="text-sm text-slate-650 leading-relaxed">
                        {tPayments("requiredBody") || "Payment is required to proceed with this order."}
                    </p>
                    <Link href={`/${locale}/dashboard/orders/${order.id}/checkout`}>
                        <Button className="w-full font-bold py-3">
                            {tPayments("continueCheckout") || "Proceed to payment"}
                        </Button>
                    </Link>
                </div>
            );
        }

        // 1. CLIENT UI
        if (caps.is_client_owner) {
            if (order.status === "completed") {
                return (
                    <div className="text-center py-8 text-green-600 font-semibold flex flex-col items-center justify-center gap-2">
                        <span className="text-3xl">✓</span>
                        {t("qr.completed")}
                    </div>
                );
            }

            if (order.status === "cancelled" || order.status === "disputed") {
                return (
                    <div className="text-center py-8 text-neutral-500 font-medium">
                        {t("qr.unavailable")}
                    </div>
                );
            }

            const canGenerate = caps.can_generate_start || caps.can_generate_finish;
            const qrType = caps.can_generate_start ? "start" : "finish";
            const buttonText = caps.can_generate_start ? t("qr.generateStart") : t("qr.generateFinish");
            const titleText = caps.can_generate_start ? t("qr.startTitle") : t("qr.finishTitle");

            if (!canGenerate && !qrImageUrl) {
                return (
                    <div className="text-center py-8 text-neutral-500 font-medium">
                        {t("qr.unavailable")}
                    </div>
                );
            }

            return (
                <div className="space-y-4">
                    {!qrImageUrl ? (
                        <Button
                            onClick={() => generateQr(qrType)}
                            isLoading={isGeneratingQr}
                            className="w-full font-bold py-3"
                        >
                            {buttonText}
                        </Button>
                    ) : (
                        <div className="space-y-4">
                            <div className="text-center">
                                <h3 className="text-sm font-bold text-slate-800 mb-1">{titleText}</h3>
                                <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                                    {t("qr.clientInstructions")}
                                </p>
                            </div>

                            {/* QR Code Image */}
                            <div className="flex justify-center bg-white p-6 rounded-2xl border border-slate-200 shadow-sm max-w-sm mx-auto">
                                <img src={qrImageUrl} alt="QR Code" className="w-64 h-64" />
                            </div>

                            {/* Expiration and countdown */}
                            {qrData && (
                                <div className="space-y-3 text-center">
                                    <div className="flex items-center justify-center gap-2 text-xs font-bold uppercase tracking-wider">
                                        <span className="text-slate-400">{t("qr.expires")}:</span>
                                        <span className="text-violet-600">{formatDate(qrData.expires_at)}</span>
                                        {timeLeft !== null && (
                                            <span className="bg-violet-50 text-violet-700 px-2 py-0.5 rounded-full font-mono text-[10px]">
                                                {Math.floor(timeLeft / 60)}:{(timeLeft % 60).toString().padStart(2, "0")}
                                            </span>
                                        )}
                                    </div>
                                    <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 max-w-md mx-auto">
                                        <input
                                            type="password"
                                            readOnly
                                            value={qrData.token}
                                            className="text-center w-full text-xs font-mono text-slate-650 bg-transparent border-none outline-none select-all"
                                        />
                                        <button
                                            onClick={copyToken}
                                            className="text-xs text-violet-600 font-bold hover:text-violet-700 transition underline mt-2 block mx-auto"
                                        >
                                            {copySuccess ? t("qr.copied") : t("qr.copy")}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Warning message */}
                            <p className="text-center text-[11px] text-amber-600 font-medium max-w-sm mx-auto leading-normal bg-amber-50 border border-amber-100 rounded-xl py-2 px-3">
                                {t("qr.regenerateWarning")}
                            </p>

                            {/* Regenerate button */}
                            <Button
                                onClick={() => generateQr(qrType)}
                                isLoading={isGeneratingQr}
                                variant="outline"
                                className="w-full font-bold py-2.5 rounded-xl border-slate-350"
                            >
                                {t("qr.regenerate")}
                            </Button>
                        </div>
                    )}
                </div>
            );
        }

        // 2. PROVIDER UI
        if (caps.is_assigned_provider) {
            const canVerify = caps.can_check_in || caps.can_complete;
            const verifyType = caps.can_check_in ? "start" : "finish";
            const scanTitle = caps.can_check_in ? t("qr.providerScanStart") : t("qr.providerScanFinish");

            if (!canVerify) {
                return (
                    <div className="text-center py-8 text-neutral-500 font-medium">
                        {t("qr.unavailable")}
                    </div>
                );
            }

            return (
                <div className="space-y-4">
                    <div className="text-center mb-2">
                        <h3 className="text-base font-bold text-slate-800">{scanTitle}</h3>
                    </div>

                    <div className="space-y-3 max-w-md mx-auto">
                        <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
                            {t("qr.enterToken")}
                        </label>
                        <input
                            type="password"
                            placeholder="eyJhbGciOi..."
                            value={providerTokenInput}
                            onChange={(e) => setProviderTokenInput(e.target.value)}
                            disabled={isVerifyingToken}
                            className="w-full px-4 py-2.5 text-sm font-mono bg-white border border-slate-200 rounded-xl outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition disabled:bg-slate-50"
                        />

                        {verificationError && (
                            <div className="p-3 bg-red-50 border border-red-150 text-red-750 text-xs font-semibold rounded-xl leading-normal">
                                {verificationError}
                            </div>
                        )}

                        {verificationSuccess && (
                            <div className="p-3 bg-green-50 border border-green-150 text-green-750 text-xs font-semibold rounded-xl leading-normal">
                                {verificationSuccess}
                            </div>
                        )}

                        <Button
                            onClick={() => verifyProviderToken(verifyType)}
                            isLoading={isVerifyingToken}
                            disabled={!providerTokenInput.trim()}
                            className="w-full font-bold py-2.5 rounded-xl"
                        >
                            {t("qr.verify")}
                        </Button>
                    </div>
                </div>
            );
        }

        // 3. UNRELATED USER / STAFF
        return null;
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    if (error && !order) {
        return (
            <div className="max-w-4xl mx-auto space-y-4">
                <div className="rounded-2xl bg-red-50 border border-red-100 p-5 text-red-700">
                    <div className="font-semibold mb-1">{t("errorTitle")}</div>
                    <div className="text-sm">{error}</div>
                </div>
                <Link
                    href={`/${locale}/dashboard/orders`}
                    className="text-sm text-violet-600 font-semibold hover:text-violet-700 transition"
                >
                    {t("back")}
                </Link>
            </div>
        );
    }

    if (!order) {
        return (
            <div className="max-w-4xl mx-auto">
                <div className="text-center py-12 bg-white border border-slate-200 rounded-2xl">
                    <div className="text-lg font-semibold text-slate-700 mb-4">
                        {t("notFound")}
                    </div>
                    <Link href={`/${locale}/dashboard/orders`}>
                        <Button>{t("back")}</Button>
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Back link */}
            <div className="flex items-center">
                <Link
                    href={`/${locale}/dashboard/orders`}
                    className="group inline-flex items-center text-sm font-bold text-slate-500 hover:text-violet-600 transition duration-200"
                >
                    <svg className="mr-2 h-4 w-4 transform group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    {t("back")}
                </Link>
            </div>

            {/* Order Info Card */}
            <Card className="border border-slate-200 p-6 sm:p-8 rounded-2xl shadow-xs">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6 pb-6 border-b border-slate-100">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <span className="text-xs text-slate-400 font-bold uppercase tracking-wider">
                                #{order.id}
                            </span>
                            <StatusBadge status={order.status} label={getStatusLabel(order.status)} />
                        </div>
                        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                            {t("title")}
                        </h1>
                    </div>
                    <div className="text-left md:text-right">
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{t("fields.price")}</div>
                        <div className="text-3xl font-extrabold text-violet-600">
                            {formatPrice(order.price_agreed)}
                        </div>
                    </div>
                </div>

                {/* Service snapshot if available */}
                {order.service_snapshot && (
                    <div className="mb-6 pb-6 border-b border-slate-100">
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1.5">{t("fields.service")}</div>
                        <div className="font-bold text-lg text-slate-800">{order.service_snapshot.title}</div>
                        <div className="text-sm text-slate-500 mt-0.5">
                            {order.service_snapshot.category_name} • {order.service_snapshot.city}
                        </div>
                    </div>
                )}

                {/* Order details grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div>
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{t("fields.provider")}</div>
                        <div className="font-semibold text-slate-800">{order.provider?.email ?? tCommon("unknown")}</div>
                    </div>
                    <div>
                        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{t("fields.created")}</div>
                        <div className="font-semibold text-slate-800">{formatDate(order.created_at)}</div>
                    </div>
                    {order.checkin_at && (
                        <div>
                            <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{t("fields.checkin")}</div>
                            <div className="font-semibold text-slate-800">{formatDate(order.checkin_at)}</div>
                        </div>
                    )}
                    {order.completed_at && (
                        <div>
                            <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{t("fields.completed")}</div>
                            <div className="font-semibold text-slate-800">{formatDate(order.completed_at)}</div>
                        </div>
                    )}
                </div>
            </Card>

            {/* QR Code Section */}
            <Card className="border border-slate-200 p-6 rounded-2xl shadow-xs">
                <h2 className="text-xl font-bold text-slate-900 mb-4">{t("qr.title")}</h2>
                {renderQrSection()}
            </Card>

            {/* Reviews Section */}
            {order.status === "completed" && (
                <Card className="border border-slate-200 p-6 rounded-2xl shadow-xs">
                    <h2 className="text-xl font-bold text-slate-900 mb-4">{tReviews("title")}</h2>

                    {order.review ? (
                        <div className="space-y-4">
                            <div className="flex items-center gap-2">
                                <span className="font-extrabold text-lg text-amber-500">
                                    ★ {order.review.rating}/5
                                </span>
                            </div>
                            {order.review.text && (
                                <p className="text-slate-700 bg-slate-50 border border-slate-100 p-4 rounded-2xl leading-relaxed whitespace-pre-wrap text-sm">
                                    {order.review.text}
                                </p>
                            )}
                            {order.review.provider_reply && (
                                <div className="mt-4 border-l-4 border-violet-600 pl-4 space-y-2">
                                    <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                                        {tReviews("providerReply")}
                                    </div>
                                    <p className="text-slate-700 bg-violet-50/20 border border-violet-100/50 p-4 rounded-2xl leading-relaxed whitespace-pre-wrap text-sm">
                                        {order.review.provider_reply}
                                    </p>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                                    {tReviews("rating")}
                                </label>
                                <div className="flex gap-1">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                        <button
                                            key={star}
                                            onClick={() => setReviewRating(star)}
                                            className={`text-3xl transition-transform hover:scale-110 active:scale-95 duration-200 ${
                                                reviewRating >= star ? "text-amber-500" : "text-slate-300"
                                            }`}
                                        >
                                            ★
                                        </button>
                                    ))}
                                </div>
                            </div>
                            
                            <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                                    {tReviews("text")}
                                </label>
                                <Textarea
                                    value={reviewText}
                                    onChange={(e) => setReviewText(e.target.value)}
                                    rows={4}
                                />
                            </div>

                            {reviewError && (
                                <div className="text-rose-600 text-sm font-medium">{reviewError}</div>
                            )}

                            <Button
                                onClick={handleSubmitReview}
                                isLoading={isSubmittingReview}
                                disabled={reviewRating === 0}
                                className="w-full font-bold rounded-xl"
                            >
                                {tReviews("submit")}
                            </Button>
                        </div>
                    )}
                </Card>
            )}
        </div>
    );
}
