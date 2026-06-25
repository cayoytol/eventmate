"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

interface SubscriptionQuote {
    plan_code: string;
    plan_name_ru: string;
    plan_name_en: string;
    plan_name_kz: string;
    duration_days: number;
    original_amount: string;
    discount_amount: string;
    final_amount: string;
    original_currency: string;
    provider_amount: string;
    provider_currency: string;
    conversion_rate: string;
    conversion_source: string;
    promo_code: string | null;
    promo_valid: boolean;
    promo_message: string;
    active_provider: string;
    quote_fingerprint: string;
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

const getOrCreateIdempotencyKey = (userId: string, planCode: string, promo: string) => {
    const normalizedPromo = (promo || "").trim().toLowerCase();
    const storageKey = `checkout-idempotency-${userId}-${planCode}-${normalizedPromo}`;
    let key = sessionStorage.getItem(storageKey);
    if (!key) {
        key = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36);
        sessionStorage.setItem(storageKey, key);
    }
    return key;
};

const clearIdempotencyKey = (userId: string, planCode: string, promo: string) => {
    const normalizedPromo = (promo || "").trim().toLowerCase();
    const storageKey = `checkout-idempotency-${userId}-${planCode}-${normalizedPromo}`;
    sessionStorage.removeItem(storageKey);
};

export default function SubscriptionCheckoutPage() {
    const locale = useLocale();
    const router = useRouter();
    const searchParams = useSearchParams();

    const t = useTranslations("payments");
    const tBilling = useTranslations("provider.billing");
    const tCommon = useTranslations("common");

    const planCode = searchParams.get("plan");
    const initialPromo = searchParams.get("promo") || "";

    const [quote, setQuote] = useState<SubscriptionQuote | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Promo code state
    const [promoInput, setPromoInput] = useState(initialPromo);
    const [appliedPromo, setAppliedPromo] = useState(initialPromo);
    const [isValidatingPromo, setIsValidatingPromo] = useState(false);
    const [promoFeedback, setPromoFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

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
    const paymentId = searchParams.get("payment_id");
    const queryStatus = searchParams.get("status");

    // Fetch quote
    const fetchQuote = async (plan: string, promo: string, isInitial: boolean = false) => {
        if (isInitial) setIsLoading(true);
        else setIsValidatingPromo(true);
        
        setPromoFeedback(null);
        try {
            const response = await api.post<SubscriptionQuote>("/billing/subscription/quote/", {
                plan_code: plan,
                promo_code: promo || undefined
            });
            setQuote(response.data);
            setAppliedPromo(promo);
            
            if (promo) {
                if (response.data.promo_valid) {
                    setPromoFeedback({
                        type: "success",
                        message: tBilling("promoValid") || "Promo code applied successfully!"
                    });
                } else {
                    setPromoFeedback({
                        type: "error",
                        message: response.data.promo_message || tBilling("promoInvalid") || "Promo code is invalid or expired."
                    });
                }
            }
        } catch (err: any) {
            if (isInitial) {
                setError(err?.response?.data?.detail || "Failed to load subscription quote.");
            } else {
                setPromoFeedback({
                    type: "error",
                    message: err?.response?.data?.detail || tBilling("promoInvalid") || "Promo code is invalid or expired."
                });
            }
        } finally {
            if (isInitial) setIsLoading(false);
            else setIsValidatingPromo(false);
        }
    };

    useEffect(() => {
        if (planCode) {
            fetchQuote(planCode, initialPromo, true);
        } else {
            setIsLoading(false);
        }
    }, [planCode]);

    // Polling function for active subscription entitlements after capture
    const pollSubscriptionStatus = (payId: string) => {
        let attempts = 0;
        const maxAttempts = 10;
        const interval = setInterval(async () => {
            attempts++;
            try {
                const response = await api.get(`/billing/subscription/payments/${payId}/status/`);
                if (response.data.paid_entitlements_active) {
                    clearInterval(interval);
                    // Clear the used idempotency key
                    clearIdempotencyKey("me", planCode || "", appliedPromo);
                    router.push(`/${locale}/provider/billing`);
                } else if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    clearIdempotencyKey("me", planCode || "", appliedPromo);
                    router.push(`/${locale}/provider/billing`);
                }
            } catch (err) {
                clearInterval(interval);
                clearIdempotencyKey("me", planCode || "", appliedPromo);
                router.push(`/${locale}/provider/billing`);
            }
        }, 2500);
    };

    // Handle return capture
    const handleCapture = async (token: string) => {
        setIsCapturing(true);
        setCaptureError(null);
        try {
            const response = await api.post("/billing/paypal/capture/", {
                paypal_order_id: token
            });
            if (response.data.status === "success") {
                setCaptureSuccess(true);
                // Clean URL parameters
                const url = new URL(window.location.href);
                url.searchParams.delete("token");
                url.searchParams.delete("payment_id");
                url.searchParams.delete("status");
                url.searchParams.delete("PayerID");
                window.history.replaceState({}, "", url.toString());

                if (paymentId) {
                    pollSubscriptionStatus(paymentId);
                } else {
                    setTimeout(() => {
                        clearIdempotencyKey("me", planCode || "", appliedPromo);
                        router.push(`/${locale}/provider/billing`);
                    }, 2500);
                }
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

    // Handle checkout initiation
    const handleCreateCheckout = async () => {
        if (!planCode) return;
        setIsCreatingCheckout(true);
        setCheckoutError(null);
        setInitializingStatus(null);

        // Fetch or create stable Idempotency-Key
        const idKey = getOrCreateIdempotencyKey("me", planCode, appliedPromo);

        try {
            const response = await api.post(
                "/billing/subscription/checkout/",
                {
                    plan_code: planCode,
                    promo_code: appliedPromo || undefined
                },
                {
                    headers: {
                        "Idempotency-Key": idKey
                    }
                }
            );

            if (response.status === 202) {
                setInitializingStatus("Preparing subscription checkout... Please wait.");
                pollCheckoutStatus(idKey);
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
            if (err?.response?.status === 202) {
                setInitializingStatus("Preparing subscription checkout... Please wait.");
                pollCheckoutStatus(idKey);
            } else {
                const detail = err?.response?.data?.detail || "Failed to initiate subscription checkout.";
                setCheckoutError(detail);
                setIsCreatingCheckout(false);
            }
        }
    };

    const pollCheckoutStatus = (idKey: string) => {
        let attempts = 0;
        const maxAttempts = 10;
        const interval = setInterval(async () => {
            attempts++;
            try {
                const response = await api.post(
                    "/billing/subscription/checkout/",
                    {
                        plan_code: planCode,
                        promo_code: appliedPromo || undefined
                    },
                    {
                        headers: {
                            "Idempotency-Key": idKey
                        }
                    }
                );
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

    const handleApplyPromo = () => {
        if (planCode) {
            fetchQuote(planCode, promoInput);
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-md mx-auto py-12 flex flex-col items-center justify-center space-y-4">
                <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-violet-600"></div>
                <p className="text-sm text-slate-500 font-medium">{tCommon("loading")}</p>
            </div>
        );
    }

    if (error || !planCode || !quote) {
        return (
            <div className="max-w-md mx-auto py-8 text-center space-y-4">
                <div className="bg-red-55 border border-red-100 text-red-700 p-4 rounded-2xl text-sm">
                    {error || "Invalid plan selected for checkout."}
                </div>
                <Link href={`/${locale}/provider/billing`}>
                    <Button variant="outline">{tCommon("back") || "Back"}</Button>
                </Link>
            </div>
        );
    }

    const planName = locale === "en" ? quote.plan_name_en : locale === "kz" ? quote.plan_name_kz : quote.plan_name_ru;
    const finalKzt = parseFloat(quote.final_amount);
    const isFree = finalKzt === 0;

    return (
        <div className="max-w-xl mx-auto space-y-6 px-4 sm:px-0">
            {/* Header */}
            <div className="flex items-center">
                <Link
                    href={`/${locale}/provider/billing`}
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
                        {tBilling("paymentSuccess") || "Subscription Activated!"}
                    </h3>
                    <p className="text-sm text-green-700">
                        {tBilling("successMessage") || "Your subscription is now active. Redirecting back to Billing page..."}
                    </p>
                </Card>
            )}

            {/* Errors */}
            {captureError && (
                <div className="bg-red-50 border border-red-100 text-red-800 p-4 rounded-xl text-sm leading-relaxed">
                    <strong>{tCommon("error") || "Error"}:</strong> {captureError}
                </div>
            )}

            {checkoutError && (
                <div className="bg-red-55 border border-red-100 text-red-800 p-4 rounded-xl text-sm leading-relaxed">
                    {checkoutError}
                </div>
            )}

            {initializingStatus && (
                <div className="bg-amber-50 border border-amber-100 text-amber-800 p-4 rounded-xl text-sm flex items-center gap-3">
                    <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-amber-800"></div>
                    <span>{initializingStatus}</span>
                </div>
            )}

            {/* Main Checkout UI */}
            {!captureSuccess && (
                <Card className="border border-slate-200 p-6 sm:p-8 rounded-2xl shadow-xs space-y-6">
                    <div className="border-b border-slate-100 pb-5">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">
                            {tCommon("brand")} {tBilling("billingNav") || "Provider Billing"}
                        </span>
                        <h2 className="text-xl font-extrabold text-slate-900">
                            {tBilling("checkoutPage.title") || tBilling("activatePlan") || "Subscription Checkout"}
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            {tBilling("checkoutPage.subtitle") || "Review your billing information and verify exchange rates before proceeding."}
                        </p>
                    </div>

                    {/* Plan Summary */}
                    <div className="bg-slate-50 rounded-2xl p-4 border border-slate-150 flex justify-between items-center">
                        <div>
                            <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider block mb-0.5">
                                {tBilling("checkoutPage.planName") || "Selected Plan"}
                            </span>
                            <div className="font-bold text-slate-800 text-base">{planName}</div>
                        </div>
                        <div className="text-right">
                            <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider block mb-0.5">
                                {tBilling("duration") || "Duration"}
                            </span>
                            <div className="font-bold text-slate-600 text-sm">
                                {tBilling("durationDays", { days: quote.duration_days })}
                            </div>
                        </div>
                    </div>

                    {/* Promo Code Application */}
                    <div className="space-y-2">
                        <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider">
                            {tBilling("promoCode") || "Promo Code"}
                        </label>
                        <div className="flex gap-2">
                            <Input
                                value={promoInput}
                                onChange={(e) => setPromoInput(e.target.value)}
                                placeholder={tBilling("promoCodePlaceholder") || "Enter promo code"}
                                disabled={isCreatingCheckout || isCapturing}
                                className="rounded-xl text-sm"
                            />
                            <Button
                                onClick={handleApplyPromo}
                                isLoading={isValidatingPromo}
                                disabled={isCreatingCheckout || isCapturing}
                                variant="outline"
                                className="font-bold shrink-0 rounded-xl px-5 text-sm"
                            >
                                {tBilling("applyPromo") || "Apply"}
                            </Button>
                        </div>
                        {promoFeedback && (
                            <p className={`text-xs font-semibold ${promoFeedback.type === "success" ? "text-green-600" : "text-rose-600"}`}>
                                {promoFeedback.message}
                            </p>
                        )}
                    </div>

                    {/* Pricing quote breakdown */}
                    <div className="space-y-3 pt-2 border-t border-slate-100">
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-slate-500 font-medium">
                                {tBilling("checkoutPage.originalPrice") || "Original Price"}
                            </span>
                            <span className="font-bold text-slate-700">
                                {parseFloat(quote.original_amount).toLocaleString(locale)} {quote.original_currency}
                            </span>
                        </div>

                        {parseFloat(quote.discount_amount) > 0 && (
                            <div className="flex justify-between items-center text-sm text-green-600">
                                <span className="font-medium">
                                    {tBilling("checkoutPage.discount") || "Promo Discount"}
                                </span>
                                <span className="font-bold">
                                    -{parseFloat(quote.discount_amount).toLocaleString(locale)} {quote.original_currency}
                                </span>
                            </div>
                        )}

                        <div className="flex justify-between items-center text-sm pt-2 border-t border-slate-100">
                            <span className="text-slate-900 font-bold">
                                {tBilling("checkoutPage.finalPrice") || "Total Amount"}
                            </span>
                            <span className="font-extrabold text-slate-900">
                                {finalKzt.toLocaleString(locale)} {quote.original_currency}
                            </span>
                        </div>

                        {quote.active_provider === "paypal" && quote.conversion_source !== "direct" && !isFree && (
                            <>
                                <div className="flex justify-between items-center text-sm">
                                    <span className="text-slate-500 font-medium">
                                        {tBilling("checkoutPage.exchangeRate") || "Exchange Rate"}
                                    </span>
                                    <span className="font-semibold text-slate-700">
                                        1 USD = {parseFloat(quote.conversion_rate).toFixed(2)} KZT
                                    </span>
                                </div>
                                <div className="flex justify-between items-center text-sm pt-1.5 border-t border-slate-100">
                                    <span className="text-slate-900 font-bold">
                                        {tBilling("checkoutPage.convertedPrice") || "Converted Total"}
                                    </span>
                                    <span className="text-xl font-extrabold text-violet-600">
                                        ${parseFloat(quote.provider_amount).toFixed(2)} {quote.provider_currency}
                                    </span>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Recipient Wording */}
                    <div className="bg-violet-50/40 border border-violet-100 rounded-2xl p-4 text-xs text-violet-800 leading-relaxed">
                        🔒 <strong>{tBilling("checkoutPage.recipientLabel") || "Recipient Wording"}:</strong> {tBilling("checkoutPage.recipientText") || "Sfera platform"}
                    </div>

                    {/* Actions */}
                    <div className="pt-2">
                        {paypalToken ? (
                            <Button
                                disabled
                                className="w-full font-bold py-3 text-sm flex items-center justify-center gap-2"
                            >
                                <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
                                {tBilling("checkoutPage.capturing") || "Verifying payment status..."}
                            </Button>
                        ) : (
                            <div className="flex flex-col sm:flex-row gap-3">
                                <Link href={`/${locale}/provider/billing`} className="w-full sm:w-1/3">
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
                                        ? (tBilling("checkoutPage.redirecting") || "Redirecting to PayPal Sandbox...") 
                                        : (isFree ? (tBilling("activatePlan") || "Activate Plan") : (tBilling("checkoutPage.proceedButton") || "Proceed to PayPal Sandbox"))}
                                </Button>
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {/* Informational Footer */}
            {queryStatus === "cancel" && (
                <div className="bg-amber-50 border border-amber-100 text-amber-800 p-4 rounded-xl text-xs text-center leading-normal">
                    {tBilling("checkoutPage.cancelMessage") || "Subscription checkout cancelled. You can retry at any time."}
                </div>
            )}
        </div>
    );
}
