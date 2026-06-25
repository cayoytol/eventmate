"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { ENDPOINTS, orderUrl } from "@/lib/api/endpoints";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

interface OrderDetail {
    id: number;
    status: string;
    price_agreed: string;
    payment_status: string;
    service_snapshot?: {
        title: string;
        category_name: string;
        city: string;
    };
    provider?: {
        email: string;
    };
}

interface PaymentQuote {
    order_id: number;
    original_amount: string;
    original_currency: string;
    provider_amount: string;
    provider_currency: string;
    conversion_rate: string;
    conversion_source: string;
    active_provider: string;
}

function isSafeHttpsUrl(urlString: string): boolean {
    try {
        const url = new URL(urlString);
        if (url.protocol !== "https:") return false;
        const hostname = url.hostname.toLowerCase();
        return hostname === "sandbox.paypal.com" || hostname === "www.sandbox.paypal.com";
    } catch (_) {
        return false;
    }
}

export default function OrderCheckoutPage() {
    const params = useParams();
    const id = String(params.id);
    const locale = useLocale();
    const router = useRouter();
    const searchParams = useSearchParams();
    
    const t = useTranslations("payments");
    const tDetail = useTranslations("dashboard.orderDetail");
    const tCommon = useTranslations("common");

    const [order, setOrder] = useState<OrderDetail | null>(null);
    const [quote, setQuote] = useState<PaymentQuote | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Checkout creation states
    const [isCreatingCheckout, setIsCreatingCheckout] = useState(false);
    const [checkoutError, setCheckoutError] = useState<string | null>(null);
    const [initializingStatus, setInitializingStatus] = useState<string | null>(null);

    // Capture states
    const [isCapturing, setIsCapturing] = useState(false);
    const [captureSuccess, setCaptureSuccess] = useState(false);
    const [captureError, setCaptureError] = useState<string | null>(null);

    const captureCalled = useRef(false);
    const paypalToken = searchParams.get("token");
    const queryStatus = searchParams.get("status");

    // Fetch details
    const fetchOrderAndQuote = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [orderRes, quoteRes] = await Promise.all([
                api.get<OrderDetail>(orderUrl(id)),
                api.get<PaymentQuote>(`/payments/orders/${id}/quote/`)
            ]);
            setOrder(orderRes.data);
            setQuote(quoteRes.data);
        } catch (err: any) {
            setError(err?.response?.data?.detail || "Failed to load checkout details.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchOrderAndQuote();
    }, [id]);

    // Handle return capture
    const handleCapture = async (token: string) => {
        setIsCapturing(true);
        setCaptureError(null);
        try {
            const response = await api.post("/payments/paypal/capture/", {
                paypal_order_id: token
            });
            if (response.data.status === "success") {
                setCaptureSuccess(true);
                // Clean URL parameters
                const url = new URL(window.location.href);
                url.searchParams.delete("token");
                url.searchParams.delete("transaction_id");
                url.searchParams.delete("status");
                url.searchParams.delete("PayerID");
                window.history.replaceState({}, "", url.toString());

                // Redirect back to order page
                setTimeout(() => {
                    router.push(`/${locale}/dashboard/orders/${id}`);
                }, 2500);
            } else {
                setCaptureError("Payment capture was not successful.");
            }
        } catch (err: any) {
            const detail = err?.response?.data?.detail || "Failed to capture payment.";
            setCaptureError(detail);
        } finally {
            setIsCapturing(false);
        }
    };

    useEffect(() => {
        if (paypalToken && !captureCalled.current) {
            captureCalled.current = true;
            handleCapture(paypalToken);
        }
    }, [paypalToken]);

    // Checkout initiation
    const handleCreateCheckout = async () => {
        setIsCreatingCheckout(true);
        setCheckoutError(null);
        setInitializingStatus(null);
        
        try {
            const response = await api.post(`/payments/orders/${id}/create/`);
            
            if (response.status === 202) {
                setInitializingStatus("Preparing PayPal checkout session... Please wait.");
                pollCheckoutStatus();
                return;
            }

            const data = response.data;
            if (data.checkout_url) {
                if (isSafeHttpsUrl(data.checkout_url)) {
                    window.location.assign(data.checkout_url);
                } else {
                    setCheckoutError("Unsafe or invalid checkout URL returned by provider.");
                }
            } else {
                setCheckoutError("paypal_approve_url_missing");
            }
        } catch (err: any) {
            if (err?.response?.status === 503) {
                setCheckoutError("payment_provider_unavailable");
            } else {
                const detail = err?.response?.data?.detail || "Failed to initiate payment.";
                setCheckoutError(detail);
            }
            setIsCreatingCheckout(false);
        }
    };

    const pollCheckoutStatus = () => {
        let attempts = 0;
        const maxAttempts = 10;
        const interval = setInterval(async () => {
            attempts++;
            try {
                const response = await api.post(`/payments/orders/${id}/create/`);
                if (response.status === 200 || response.status === 201) {
                    clearInterval(interval);
                    const data = response.data;
                    if (data.checkout_url) {
                        if (isSafeHttpsUrl(data.checkout_url)) {
                            window.location.assign(data.checkout_url);
                        } else {
                            setCheckoutError("Unsafe or invalid checkout URL returned by provider.");
                        }
                    } else {
                        setCheckoutError("paypal_approve_url_missing");
                    }
                    setIsCreatingCheckout(false);
                    setInitializingStatus(null);
                } else if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    setCheckoutError("Checkout session preparation timed out. Please try again.");
                    setIsCreatingCheckout(false);
                    setInitializingStatus(null);
                }
            } catch (err: any) {
                clearInterval(interval);
                const detail = err?.response?.data?.detail || "Failed to initialize checkout.";
                setCheckoutError(detail);
                setIsCreatingCheckout(false);
                setInitializingStatus(null);
            }
        }, 2500);
    };

    if (isLoading) {
        return (
            <div className="max-w-md mx-auto py-12 flex flex-col items-center justify-center space-y-4">
                <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-violet-600"></div>
                <p className="text-sm text-slate-500 font-medium">{tCommon("loading")}</p>
            </div>
        );
    }

    if (error || !order || !quote) {
        return (
            <div className="max-w-md mx-auto py-8 text-center space-y-4">
                <div className="bg-red-55 border border-red-100 text-red-700 p-4 rounded-2xl text-sm">
                    {error || "Order metadata could not be fetched."}
                </div>
                <Link href={`/${locale}/dashboard/orders/${id}`}>
                    <Button variant="outline">{tCommon("back") || "Back"}</Button>
                </Link>
            </div>
        );
    }

    const isPaid = order.payment_status === "paid";

    return (
        <div className="max-w-xl mx-auto space-y-6 px-4 sm:px-0">
            {/* Header */}
            <div className="flex items-center">
                <Link
                    href={`/${locale}/dashboard/orders/${id}`}
                    className="group inline-flex items-center text-sm font-bold text-slate-500 hover:text-violet-600 transition duration-200"
                >
                    <svg className="mr-2 h-4 w-4 transform group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    {tCommon("back") || "Back"}
                </Link>
            </div>

            {/* Success State */}
            {captureSuccess && (
                <Card className="border border-green-100 bg-green-50/50 p-6 rounded-2xl text-center space-y-3">
                    <div className="text-3xl text-green-600 font-bold">✓</div>
                    <h3 className="text-lg font-bold text-green-900">
                        {t("paidSuccess") || "Payment Successful!"}
                    </h3>
                    <p className="text-sm text-green-700">
                        {t("successMessage") || "Payment captured successfully! Redirecting you back to your order."}
                    </p>
                </Card>
            )}

            {/* Error States */}
            {captureError && (
                <div className="bg-red-55 border border-red-100 text-red-800 p-4 rounded-xl text-sm leading-relaxed">
                    <strong>{tCommon("error") || "Error"}:</strong> {captureError}
                </div>
            )}

            {checkoutError && (
                <div className="bg-red-55 border border-red-100 text-red-800 p-4 rounded-xl text-sm leading-relaxed">
                    {checkoutError === "payment_provider_unavailable"
                        ? (t("providerUnavailable") || "Payment provider is currently unavailable. Please try again later.")
                        : checkoutError === "paypal_approve_url_missing"
                        ? (t("approveUrlMissing") || "PayPal approval link could not be generated. Please contact support.")
                        : checkoutError}
                </div>
            )}

            {initializingStatus && (
                <div className="bg-amber-50 border border-amber-100 text-amber-800 p-4 rounded-xl text-sm flex items-center gap-3">
                    <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-amber-800"></div>
                    <span>{initializingStatus}</span>
                </div>
            )}

            {/* Main Checkout View */}
            {!captureSuccess && (
                <Card className="border border-slate-200 p-6 sm:p-8 rounded-2xl shadow-xs space-y-6">
                    <div className="border-b border-slate-100 pb-5">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">
                            {t("orderCheckout.marketplaceOrder") || "Marketplace Order"} #{order.id}
                        </span>
                        <h2 className="text-xl font-extrabold text-slate-900">
                            {t("orderCheckout.title") || "Order Checkout"}
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            {t("orderCheckout.subtitle") || "Please review your order details and price conversion below."}
                        </p>
                    </div>

                    {/* Order summary */}
                    {order.service_snapshot && (
                        <div className="bg-slate-50 rounded-2xl p-4 border border-slate-150">
                            <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider block mb-0.5">
                                {tDetail("fields.service") || "Service"}
                            </span>
                            <div className="font-bold text-slate-800 text-sm">
                                {order.service_snapshot.title}
                            </div>
                            <div className="text-xs text-slate-500 mt-0.5">
                                {order.service_snapshot.category_name} • {order.service_snapshot.city}
                            </div>
                        </div>
                    )}

                    {/* Pricing quote breakdown */}
                    <div className="space-y-3">
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-slate-500 font-medium">
                                {t("orderCheckout.originalPrice") || "Original Price"}
                            </span>
                            <span className="font-bold text-slate-800">
                                {parseFloat(quote.original_amount).toLocaleString(locale)} {quote.original_currency}
                            </span>
                        </div>

                        {quote.active_provider === "paypal" && quote.conversion_source !== "direct" && (
                            <>
                                <div className="flex justify-between items-center text-sm">
                                    <span className="text-slate-500 font-medium">
                                        {t("orderCheckout.exchangeRate") || "Exchange Rate"}
                                    </span>
                                    <span className="font-semibold text-slate-700">
                                        1 USD = {parseFloat(quote.conversion_rate).toFixed(2)} KZT
                                    </span>
                                </div>
                                <div className="flex justify-between items-center text-sm pt-1.5 border-t border-slate-100">
                                    <span className="text-slate-900 font-bold">
                                        {t("orderCheckout.convertedPrice") || "Price in USD"}
                                    </span>
                                    <span className="text-xl font-extrabold text-violet-600">
                                        ${parseFloat(quote.provider_amount).toFixed(2)} {quote.provider_currency}
                                    </span>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Recipient Statement */}
                    <div className="bg-violet-50/40 border border-violet-100 rounded-2xl p-4 text-xs text-violet-800 leading-relaxed">
                        🔒 <strong>{t("orderCheckout.recipientLabel") || "Recipient Wording"}:</strong> {t("orderCheckout.recipientText") || "Payment processed through the Sfera platform"}
                    </div>

                    {/* Actions */}
                    <div className="pt-2">
                        {isPaid ? (
                            <div className="text-center text-green-600 font-bold text-sm bg-green-50 border border-green-100 py-3 rounded-xl">
                                ✓ {t("paidDescription") || "Order is already paid."}
                            </div>
                        ) : paypalToken ? (
                            <Button
                                disabled
                                className="w-full font-bold py-3 text-sm flex items-center justify-center gap-2"
                            >
                                <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
                                {t("orderCheckout.capturing") || "Verifying payment..."}
                            </Button>
                        ) : (
                            <div className="flex flex-col sm:flex-row gap-3">
                                <Link href={`/${locale}/dashboard/orders/${id}`} className="w-full sm:w-1/3">
                                    <Button variant="outline" className="w-full font-bold py-3 text-sm">
                                        {tCommon("cancel") || "Cancel"}
                                    </Button>
                                </Link>
                                <Button
                                    onClick={handleCreateCheckout}
                                    isLoading={isCreatingCheckout || isCapturing}
                                    className="w-full sm:w-2/3 font-bold py-3 text-sm"
                                    aria-busy={isCreatingCheckout || isCapturing}
                                >
                                    {isCreatingCheckout 
                                        ? (t("orderCheckout.redirecting") || "Redirecting...")
                                        : (t("orderCheckout.proceedButton") || "Proceed to PayPal Sandbox")}
                                </Button>
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {/* Informational Footer */}
            {queryStatus === "cancel" && (
                <div className="bg-amber-50 border border-amber-100 text-amber-800 p-4 rounded-xl text-xs text-center leading-normal">
                    {t("orderCheckout.cancelMessage") || "Payment checkout cancelled. You can retry anytime."}
                </div>
            )}
        </div>
    );
}
