"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS, billingPaymentStatusUrl } from "@/lib/api/endpoints";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/useAuthStore";
import type { Plan, CurrentSubscriptionResponse, PromoCode } from "@/types/billing";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ProviderBillingPage() {
    const locale = useLocale();
    const t = useTranslations("provider.billing");
    const user = useAuthStore((s) => s.user);
    const searchParams = useSearchParams();
    const router = useRouter();

    // Current subscription state
    const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
    const [subscription, setSubscription] = useState<CurrentSubscriptionResponse["subscription"]>(null);
    const [isLoadingSub, setIsLoadingSub] = useState(true);
    const [subError, setSubError] = useState<string | null>(null);

    // Plans list state
    const [plans, setPlans] = useState<Plan[]>([]);
    const [isLoadingPlans, setIsLoadingPlans] = useState(true);
    const [plansError, setPlansError] = useState<string | null>(null);

    // Promo code state
    const [promoCode, setPromoCode] = useState("");
    const [promoResult, setPromoResult] = useState<PromoCode | null>(null);
    const [promoError, setPromoError] = useState<string | null>(null);
    const [isValidatingPromo, setIsValidatingPromo] = useState(false);

    // Activation & Cancellation state
    const [activatingPlanId, setActivatingPlanId] = useState<number | null>(null);
    const [isCanceling, setIsCanceling] = useState(false);
    const [activationSuccess, setActivationSuccess] = useState<string | null>(null);
    const [activationError, setActivationError] = useState<string | null>(null);

    // Payment history and status state
    const [payments, setPayments] = useState<any[]>([]);
    const [historyLoading, setHistoryLoading] = useState(true);
    const [historyError, setHistoryError] = useState<string | null>(null);
    const [historyPage, setHistoryPage] = useState(1);
    const [historyHasNext, setHistoryHasNext] = useState(false);
    const [activeProvider, setActiveProvider] = useState<string>("mock");
    const [isCapturing, setIsCapturing] = useState(false);
    
    const [paymentStatusLoading, setPaymentStatusLoading] = useState(false);
    const [paymentStatusInfo, setPaymentStatusInfo] = useState<any | null>(null);
    const [pollingPaymentId, setPollingPaymentId] = useState<string | null>(null);

    // --- Data Fetching ---

    const fetchCurrentSubscription = async (signal?: AbortSignal) => {
        try {
            setSubError(null);
            const { data } = await api.get<CurrentSubscriptionResponse>(
                ENDPOINTS.BILLING_SUBSCRIPTION_CURRENT,
                { signal }
            );
            setSubscription(data.subscription);
            setCurrentPlan(data.plan || data.current_plan);
            if ((data as any).active_provider) {
                setActiveProvider((data as any).active_provider);
            }
        } catch (err: any) {
            if (err.name === "AbortError" || err.code === "ERR_CANCELED") return;
            setSubError(err?.response?.data?.detail || t("error"));
        } finally {
            setIsLoadingSub(false);
        }
    };

    const fetchPlans = async (signal?: AbortSignal) => {
        try {
            setPlansError(null);
            const { data } = await api.get<Plan[]>(ENDPOINTS.BILLING_PLANS, { signal });
            const plansList = Array.isArray(data) ? data : (data as any)?.results ?? [];
            setPlans(plansList);
        } catch (err: any) {
            if (err.name === "AbortError" || err.code === "ERR_CANCELED") return;
            setPlansError(err?.response?.data?.detail || t("error"));
        } finally {
            setIsLoadingPlans(false);
        }
    };

    const fetchPaymentHistory = async (page: number = 1, signal?: AbortSignal) => {
        setHistoryLoading(true);
        setHistoryError(null);
        try {
            const { data } = await api.get<any>(
                `${ENDPOINTS.BILLING_PAYMENTS}?page=${page}`,
                { signal }
            );
            const paymentList = data.results || data || [];
            setPayments(paymentList);
            setHistoryHasNext(!!data.next);
        } catch (err: any) {
            if (err.name === "AbortError" || err.code === "ERR_CANCELED") return;
            setHistoryError(t("loadHistoryError") || "Failed to load payment history");
        } finally {
            setHistoryLoading(false);
        }
    };

    const handlePaypalCapture = async (paypalOrderId: string) => {
        setIsCapturing(true);
        setActivationSuccess(null);
        setActivationError(null);
        try {
            await api.post("/billing/paypal/capture/", {
                paypal_order_id: paypalOrderId
            });
            setActivationSuccess(t("planActivated") || "Subscription activated successfully!");
            setIsLoadingSub(true);
            await fetchCurrentSubscription();
            fetchPaymentHistory(historyPage);
        } catch (err: any) {
            const detail = err?.response?.data?.detail || "Payment capture failed";
            setActivationError(detail);
        } finally {
            setIsCapturing(false);
        }
    };

    useEffect(() => {
        if (!pollingPaymentId) return;

        let attempts = 0;
        const maxAttempts = 20; // 20 * 3s = 60s max
        const intervalTime = 3000; // 3s

        const poll = async () => {
            try {
                const { data } = await api.get<any>(billingPaymentStatusUrl(pollingPaymentId));
                setPaymentStatusInfo(data);

                if (data.status === "paid") {
                    setPollingPaymentId(null);
                    setIsLoadingSub(true);
                    fetchCurrentSubscription();
                    fetchPaymentHistory(historyPage);
                } else if (data.status === "failed" || data.status === "cancelled") {
                    setPollingPaymentId(null);
                    fetchPaymentHistory(historyPage);
                } else {
                    attempts++;
                    if (attempts >= maxAttempts) {
                        setPollingPaymentId(null);
                    }
                }
            } catch (err) {
                console.error("Error polling payment status", err);
                attempts++;
                if (attempts >= maxAttempts) {
                    setPollingPaymentId(null);
                }
            }
        };

        poll();

        const timer = setInterval(() => {
            poll();
        }, intervalTime);

        return () => clearInterval(timer);
    }, [pollingPaymentId]);

    useEffect(() => {
        const paymentId = searchParams.get("payment_id");
        const token = searchParams.get("token");
        
        if (token && activeProvider === "paypal") {
            handlePaypalCapture(token);
        } else if (paymentId) {
            setPollingPaymentId(paymentId);
        }
        
        if (paymentId || token) {
            const url = new URL(window.location.href);
            url.searchParams.delete("payment_id");
            url.searchParams.delete("status");
            url.searchParams.delete("token");
            url.searchParams.delete("PayerID");
            window.history.replaceState({}, "", url.toString());
        }
    }, [searchParams, activeProvider]);

    useEffect(() => {
        const ac = new AbortController();
        setIsLoadingSub(true);
        setIsLoadingPlans(true);
        setHistoryLoading(true);
        fetchCurrentSubscription(ac.signal);
        fetchPlans(ac.signal);
        fetchPaymentHistory(historyPage, ac.signal);
        return () => ac.abort();
    }, [user?.id, historyPage]);

    // --- Promo Code Validation ---

    const handleValidatePromo = async () => {
        if (!promoCode.trim()) return;
        setIsValidatingPromo(true);
        setPromoError(null);
        setPromoResult(null);
        try {
            const { data } = await api.post<PromoCode>(
                ENDPOINTS.BILLING_PROMO_VALIDATE,
                { code: promoCode.trim() }
            );
            setPromoResult(data);
        } catch (err: any) {
            const detail =
                err?.response?.data?.code?.[0] ||
                err?.response?.data?.detail ||
                t("invalidPromo");
            setPromoError(detail);
        } finally {
            setIsValidatingPromo(false);
        }
    };

    // --- Checkout & Activation ---

    const handleCheckout = async (plan: Plan) => {
        if (activeProvider === "paypal") {
            router.push(`/${locale}/provider/billing/checkout?plan=${plan.code}${promoResult ? `&promo=${promoResult.code}` : ""}`);
            return;
        }
        setActivatingPlanId(plan.id);
        setActivationSuccess(null);
        setActivationError(null);
        try {
            const idempotencyKey = `checkout-${user?.id}-${plan.code}-${Date.now()}`;
            const response = await api.post(
                ENDPOINTS.BILLING_CHECKOUT,
                {
                    plan_code: plan.code,
                    promo_code: promoResult ? promoResult.code : undefined
                },
                {
                    headers: {
                        "Idempotency-Key": idempotencyKey
                    }
                }
            );

            if (response.status === 202) {
                // Initializing state
                setActivationSuccess(t("checkoutInitializing") || "Checkout is preparing. Please wait...");
                setTimeout(() => handleCheckout(plan), 3000);
                return;
            }

            const payment = response.data;
            if (payment.checkout_url) {
                window.location.href = payment.checkout_url;
            } else {
                setActivationSuccess(t("planActivated"));
                setIsLoadingSub(true);
                await fetchCurrentSubscription();
                fetchPaymentHistory(historyPage);
            }
        } catch (err: any) {
            if (err?.response?.status === 202) {
                setActivationSuccess(t("checkoutInitializing") || "Checkout is preparing. Please wait...");
                setTimeout(() => handleCheckout(plan), 3000);
            } else {
                const detail = err?.response?.data?.detail || err?.response?.data?.detail?.detail || t("checkoutError") || "Failed to initiate checkout";
                setActivationError(detail);
            }
        } finally {
            setActivatingPlanId(null);
        }
    };

    // --- Subscription Cancellation ---

    const handleCancelSubscription = async () => {
        const confirmMsg = locale === 'en' 
            ? "Are you sure you want to cancel auto-renewal?" 
            : locale === 'kz' 
            ? "Жазылымды автоматты түрде ұзартудан бас тартасыз ба?" 
            : "Вы уверены, что хотите отменить автопродление подписки?";
        
        if (!confirm(confirmMsg)) return;
        
        setIsCanceling(true);
        setActivationSuccess(null);
        setActivationError(null);
        try {
            await api.post(`${ENDPOINTS.BILLING_SUBSCRIPTION}cancel/`);
            setActivationSuccess(
                locale === 'en'
                    ? "Auto-renewal cancelled successfully. Access remains active until the end date."
                    : locale === 'kz'
                    ? "Автоматты түрде ұзарту сәтті тоқтатылды. Қолжетімділік мерзімі аяқталғанша сақталады."
                    : "Автопродление успешно отменено. Доступ сохранится до окончания оплаченного периода."
            );
            setIsLoadingSub(true);
            await fetchCurrentSubscription();
        } catch (err: any) {
            const detail = err?.response?.data?.detail || t("error");
            setActivationError(detail);
        } finally {
            setIsCanceling(false);
        }
    };

    // --- Helpers ---

    const getPlanName = (plan: Plan) => {
        if (locale === "en") return plan.name_en || plan.name;
        if (locale === "kz") return plan.name_kz || plan.name;
        return plan.name_ru || plan.name;
    };

    const isCurrentPlan = (plan: Plan) => {
        return currentPlan?.id === plan.id;
    };

    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleDateString(locale === "kz" ? "kk-KZ" : locale === "en" ? "en-US" : "ru-RU");
        } catch {
            return dateStr;
        }
    };

    const isAnyActivating = activatingPlanId !== null || isCanceling;

    return (
        <div className="max-w-6xl mx-auto space-y-8 px-4 pb-12">
            {/* Billing Page Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 bg-white p-6 md:p-8 border border-slate-200 rounded-2xl shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/5 rounded-full blur-2xl pointer-events-none"></div>
                <div className="space-y-2 max-w-2xl">
                    <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        {t("title")}
                    </h1>
                    <p className="text-sm text-slate-500 leading-relaxed">
                        {t("subtitle")}
                    </p>
                </div>
                <div className="flex items-center gap-2.5 bg-violet-50 border border-violet-100/50 px-4 py-2.5 rounded-xl self-start md:self-auto">
                    <div className="w-2 h-2 rounded-full bg-violet-600 animate-pulse"></div>
                    <span className="text-xs font-bold text-violet-700 uppercase tracking-wider">
                        {activeProvider === "paypal" ? "PayPal Sandbox" : t("demoModeTitle")}
                    </span>
                </div>
            </div>

            {/* Warning: Simulated Mode Honesty Card */}
            <Card className="border border-amber-200 bg-amber-50/50 p-5 flex flex-col sm:flex-row items-start gap-4">
                <div className="p-3 rounded-xl bg-amber-100 text-amber-800 shrink-0">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                <div className="space-y-1.5">
                    <h3 className="font-bold text-slate-900 text-sm sm:text-base leading-snug">
                        {activeProvider === "paypal" ? "PayPal Sandbox" : t("demoModeTitle")}
                    </h3>
                    <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                        {activeProvider === "paypal" ? (
                            locale === "en" ? (
                                "PayPal Sandbox test conversion. No real funds are charged. Your billing plans KZT price will be converted to USD at a fixed test conversion rate (e.g. 5,000 ₸ to 11.11 USD at 1 USD = 450 ₸)."
                            ) : locale === "kz" ? (
                                "PayPal Sandbox тестілік түрлендіруі. Нақты қаражат алынбайды. Жазылым тарифінің теңгедегі бағасы АҚШ долларына бекітілген тестілік бағамен ауыстырылады (мысалы, 5 000 ₸ 11.11 USD-ге 1 USD = 450 ₸ бағамымен)."
                            ) : (
                                "PayPal Sandbox test conversion. No real funds are charged. Тестовая конверсия PayPal Sandbox. Реальные средства списываться не будут. Стоимость планов в тенге будет сконвертирована в USD по фиксированному курсу (например, 5 000 ₸ в 11.11 USD по курсу 1 USD = 450 ₸)."
                            )
                        ) : (
                            <>
                                {t("demoModeDescription")} <span className="font-semibold text-slate-900">{t("realPaymentsSoon")}</span>
                            </>
                        )}
                    </p>
                </div>
            </Card>

            {isCapturing && (
                <div className="rounded-xl bg-violet-50 border border-violet-100 text-violet-800 px-4 py-3.5 text-sm flex items-center gap-2 shadow-sm font-medium animate-pulse">
                    <div className="w-4 h-4 border-2 border-violet-600 border-t-transparent rounded-full animate-spin shrink-0"></div>
                    <span>{locale === 'en' ? "Confirming payment with PayPal..." : locale === 'kz' ? "Төлемді PayPal-мен растау..." : "Подтверждаем оплату в PayPal..."}</span>
                </div>
            )}

            {/* Global Notifications for Activations / Cancellations */}
            {activationSuccess && (
                <div className="rounded-xl bg-emerald-50 border border-emerald-100 text-emerald-800 px-4 py-3.5 text-sm flex justify-between items-center shadow-sm font-medium">
                    <div className="flex items-center gap-2">
                        <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                        <span>{activationSuccess}</span>
                    </div>
                    <button onClick={() => setActivationSuccess(null)} className="text-emerald-500 hover:text-emerald-800 ml-2 font-bold transition">×</button>
                </div>
            )}
            {activationError && (
                <div className="rounded-xl bg-rose-50 border border-rose-100 text-rose-800 px-4 py-3.5 text-sm flex justify-between items-center shadow-sm font-medium">
                    <div className="flex items-center gap-2">
                        <svg className="w-4 h-4 text-rose-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    <span>{activationError}</span>
                    </div>
                    <button onClick={() => setActivationError(null)} className="text-rose-500 hover:text-rose-800 ml-2 font-bold transition">×</button>
                </div>
            )}

            {paymentStatusInfo && (
                <div className={`rounded-xl border p-4 text-sm font-medium flex justify-between items-center shadow-sm ${
                    paymentStatusInfo.status === 'paid'
                        ? "bg-emerald-50 border-emerald-100 text-emerald-800"
                        : paymentStatusInfo.status === 'pending'
                        ? "bg-blue-50 border-blue-100 text-blue-800"
                        : paymentStatusInfo.status === 'failed'
                        ? "bg-rose-50 border-rose-100 text-rose-800"
                        : "bg-slate-50 border-slate-100 text-slate-800"
                }`}>
                    <div className="flex items-center gap-2">
                        {paymentStatusInfo.status === 'paid' ? (
                            <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                            </svg>
                        ) : paymentStatusInfo.status === 'pending' ? (
                            <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin shrink-0"></div>
                        ) : (
                            <svg className="w-4 h-4 text-rose-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        )}
                        <span>
                            {paymentStatusInfo.status === 'paid'
                                ? t("paymentSuccess") || "Payment confirmed! Your subscription is now active."
                                : paymentStatusInfo.status === 'pending'
                                ? t("paymentPending") || "Payment is pending. Please complete your checkout."
                                : paymentStatusInfo.status === 'failed'
                                ? t("paymentFailed") || "Payment failed. Please try again."
                                : paymentStatusInfo.status === 'cancelled'
                                ? t("paymentCancelled") || "Checkout was cancelled."
                                : `Payment status: ${paymentStatusInfo.status}`}
                        </span>
                    </div>
                    <button onClick={() => setPaymentStatusInfo(null)} className="text-slate-400 hover:text-slate-700 ml-2 font-bold transition">×</button>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                {/* Left Column: Current Plan & Promo Code */}
                <div className="lg:col-span-2 space-y-8">
                    {/* Current Plan Card */}
                    <Card className="border border-slate-200 bg-white">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-5 mb-6">
                            <div>
                                <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">
                                    {t("currentPlan")}
                                </h2>
                                <p className="text-xs text-slate-500">
                                    {t("subscriptionStatus")}
                                </p>
                            </div>
                            {isLoadingSub ? (
                                <Skeleton className="w-24 h-6 rounded-full" />
                            ) : (
                                <span
                                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${
                                        subscription?.effective_status === 'active'
                                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                            : subscription?.effective_status === 'cancelled_active'
                                            ? "bg-amber-50 text-amber-700 border-amber-200"
                                            : subscription?.effective_status === 'pending'
                                            ? "bg-blue-50 text-blue-700 border-blue-200"
                                            : subscription?.effective_status === 'expired'
                                            ? "bg-rose-50 text-rose-700 border-rose-200"
                                            : "bg-slate-50 text-slate-600 border-slate-200"
                                    }`}
                                >
                                    {subscription?.effective_status === 'active'
                                        ? t("active")
                                        : subscription?.effective_status === 'cancelled_active'
                                        ? t("cancelled")
                                        : subscription?.effective_status === 'pending'
                                        ? t("pending")
                                        : subscription?.effective_status === 'expired'
                                        ? t("expired")
                                        : t("freePlan")}
                                </span>
                            )}
                        </div>

                        {isLoadingSub ? (
                            <div className="space-y-4">
                                <Skeleton className="h-8 w-1/3" />
                                <Skeleton className="h-12 w-full" />
                                <Skeleton className="h-16 w-full" />
                            </div>
                        ) : subError ? (
                            <div className="rounded-xl bg-rose-50 border border-rose-100 text-rose-800 p-4 text-sm font-medium">
                                {subError}
                            </div>
                        ) : (
                            <div className="space-y-6">
                                {/* Plan detail row */}
                                <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                                    <div>
                                        <h3 className="text-xl font-black text-violet-700">
                                            {currentPlan ? getPlanName(currentPlan) : t("freePlan")}
                                        </h3>
                                        {currentPlan && (
                                            <p className="text-xs text-slate-500 mt-1">
                                                {currentPlan.price === 0
                                                    ? t("free")
                                                    : `₸${parseFloat(currentPlan.price as any).toLocaleString()} / ${currentPlan.duration_days} ${t("durationDays", { days: "" }).replace("{days}", "").trim()}`}
                                            </p>
                                        )}
                                    </div>
                                    {subscription && (
                                        <div className="flex flex-col items-end gap-1">
                                            <span className="text-xs font-medium text-slate-500">
                                                ID: <span className="font-bold text-slate-700">{subscription.id}</span>
                                            </span>
                                            {subscription.effective_status === 'active' && (
                                                <Button
                                                    onClick={handleCancelSubscription}
                                                    disabled={isAnyActivating}
                                                    variant="outline"
                                                    className="text-xs py-1 px-2.5 h-auto text-rose-600 hover:text-rose-700 border-rose-200 hover:bg-rose-50 rounded-lg transition"
                                                >
                                                    {locale === 'en' ? 'Cancel Auto-Renewal' : locale === 'kz' ? 'Жазылымды тоқтату' : 'Отменить автопродление'}
                                                </Button>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* Active Until / Remaining Duration Info */}
                                {subscription && (
                                    <div className="space-y-3">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm bg-white p-4 border border-slate-100 rounded-xl">
                                            <div className="flex items-center gap-3">
                                                <div className="p-2 rounded-lg bg-slate-50 text-slate-600 shrink-0">
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                    </svg>
                                                </div>
                                                <div>
                                                    <p className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">{t("activeUntil")}</p>
                                                    <p className="font-semibold text-slate-700">{formatDate(subscription.ends_at)}</p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <div className="p-2 rounded-lg bg-slate-50 text-slate-600 shrink-0">
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                    </svg>
                                                </div>
                                                <div>
                                                    <p className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">{locale === 'en' ? 'Remaining Time' : locale === 'kz' ? 'Қалған уақыт' : 'Оставшееся время'}</p>
                                                    <p className="font-semibold text-slate-700">
                                                        {t("remainingDays").replace("{days}", subscription.remaining_days.toString())}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>

                                        {subscription.effective_status === 'cancelled_active' && (
                                            <div className="rounded-xl bg-amber-50 border border-amber-100 text-amber-800 p-4 text-xs font-medium leading-relaxed">
                                                ⚠️ {locale === 'en' 
                                                    ? "Auto-renewal is disabled. Paid access remains active until the end date, after which your account falls back to the Free plan." 
                                                    : locale === 'kz'
                                                    ? "Автоматты түрде ұзарту өшірілген. Белсенді қолжетімділік мерзімі аяқталғанша сақталады, одан кейін аккаунт Тегін тарифке ауысады."
                                                    : "Автопродление отключено. Доступ к функциям активен до даты окончания подписки, после чего аккаунт будет переведен на Бесплатный тариф."}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Entitlements Summary */}
                                {currentPlan?.limits_json && (
                                    <div className="space-y-3">
                                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">{t("entitlements")}</h4>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            {currentPlan.limits_json.max_services !== undefined && (
                                                <div className="bg-violet-50/50 border border-violet-100 p-4 rounded-xl flex items-center justify-between">
                                                    <div>
                                                        <p className="text-xs text-slate-500 font-medium">{t("serviceLimit")}</p>
                                                        <p className="text-lg font-black text-violet-700 mt-0.5">
                                                            {currentPlan.limits_json.max_services === -1
                                                                ? t("unlimited")
                                                                : currentPlan.limits_json.max_services}
                                                        </p>
                                                    </div>
                                                    <div className="p-3 bg-violet-100/30 text-violet-700 rounded-lg">
                                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                                        </svg>
                                                    </div>
                                                </div>
                                            )}
                                            {currentPlan.limits_json.max_portfolio_items !== undefined && (
                                                <div className="bg-amber-50/50 border border-amber-100 p-4 rounded-xl flex items-center justify-between">
                                                    <div>
                                                        <p className="text-xs text-slate-500 font-medium">{t("portfolioLimit")}</p>
                                                        <p className="text-lg font-black text-amber-700 mt-0.5">
                                                            {currentPlan.limits_json.max_portfolio_items === -1
                                                                ? t("unlimited")
                                                                : currentPlan.limits_json.max_portfolio_items}
                                                        </p>
                                                    </div>
                                                    <div className="p-3 bg-amber-100/30 text-amber-700 rounded-lg">
                                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                        </svg>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </Card>

                    {/* Promo Code Card */}
                    <Card className="border border-slate-200 bg-white p-6">
                        <div className="space-y-1 mb-4">
                            <h3 className="text-base font-bold text-slate-900">{t("promoTitle")}</h3>
                            <p className="text-xs text-slate-500">{t("promoDescription")}</p>
                        </div>
                        <div className="flex gap-3 items-end">
                            <div className="flex-1">
                                <Input
                                    value={promoCode}
                                    onChange={(e) => {
                                        setPromoCode(e.target.value);
                                        setPromoError(null);
                                        setPromoResult(null);
                                    }}
                                    placeholder={t("promoCodePlaceholder")}
                                    disabled={isValidatingPromo}
                                    className="w-full"
                                />
                            </div>
                            <Button
                                onClick={handleValidatePromo}
                                disabled={isValidatingPromo || !promoCode.trim()}
                                isLoading={isValidatingPromo}
                                className="font-bold rounded-xl h-[42px] px-6 shadow-sm shadow-violet-100"
                            >
                                {t("validatePromo")}
                            </Button>
                        </div>

                        {/* Promo Validation Alerts */}
                        {promoResult && (
                            <div className="mt-3.5 rounded-xl bg-emerald-50 border border-emerald-100 text-emerald-800 px-4 py-3 text-xs sm:text-sm font-medium flex items-center gap-2">
                                <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                </svg>
                                <span>{t("promoValid").replace("{percent}", promoResult.discount_percent.toString())}</span>
                            </div>
                        )}
                        {promoError && (
                            <div className="mt-3.5 rounded-xl bg-rose-50 border border-rose-100 text-rose-800 px-4 py-3 text-xs sm:text-sm font-medium flex items-center gap-2">
                                <svg className="w-4 h-4 text-rose-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                                <span>{promoError}</span>
                            </div>
                        )}
                    </Card>
                </div>

                {/* Right Column: Information Side Card */}
                <div className="space-y-6">
                    <Card className="border border-violet-100 bg-violet-50/30 p-6 relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-24 h-24 bg-violet-600/5 rounded-full blur-xl pointer-events-none"></div>
                        <div className="space-y-4">
                            <div className="w-10 h-10 rounded-xl bg-violet-600 text-white flex items-center justify-center font-bold">
                                ?
                            </div>
                            <div className="space-y-1">
                                <h4 className="font-bold text-slate-900 text-sm">{locale === 'en' ? 'How subscriptions work' : locale === 'kz' ? 'Жазылым қалай жұмыс істейді' : 'Как это работает'}</h4>
                                <p className="text-xs text-slate-500 leading-relaxed">
                                    {locale === 'en'
                                        ? 'Provider accounts receive limit packages for catalog services and monthly proposals. You can upgrade or switch plans anytime. All payments are simulated for demo purposes.'
                                        : locale === 'kz'
                                        ? 'Орындаушы аккаунттары каталогта қызметтерді орналастыруға және айлық ұсыныстар жіберуге лимит пакеттерін алады. Тарифті кез келген уақытта ауыстыруға болады.'
                                        : 'Аккаунты исполнителей получают лимиты на размещение услуг в каталоге и количество ежемесячных предложений клиентам. Смена тарифа происходит мгновенно.'}
                                </p>
                            </div>
                            <div className="border-t border-slate-100/80 pt-4 space-y-2.5">
                                <div className="flex items-center gap-2 text-xs text-slate-600">
                                    <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                    </svg>
                                    <span>{locale === 'en' ? 'Zero commissions' : locale === 'kz' ? 'Комиссия 0%' : 'Комиссия 0%'}</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-slate-600">
                                    <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                    </svg>
                                    <span>{locale === 'en' ? 'Simulated activation' : locale === 'kz' ? 'Симуляциялық белсендіру' : 'Тестовая активация'}</span>
                                </div>
                            </div>
                        </div>
                    </Card>
                </div>
            </div>

            {/* Pricing Plans Grid */}
            <div className="space-y-6 pt-4">
                <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">
                    {t("availablePlans")}
                </h2>

                {plansError ? (
                    <div className="rounded-xl bg-rose-50 border border-rose-100 text-rose-700 p-4 text-sm font-medium">
                        {plansError}
                    </div>
                ) : isLoadingPlans ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <Skeleton className="h-96 w-full rounded-2xl" />
                        <Skeleton className="h-96 w-full rounded-2xl" />
                        <Skeleton className="h-96 w-full rounded-2xl" />
                    </div>
                ) : plans.length === 0 ? (
                    <EmptyState
                        title={t("noPlansTitle")}
                        description={t("noPlansDescription")}
                    />
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {plans.map((plan) => {
                            const isCurrent = isCurrentPlan(plan);
                            const isActivating = activatingPlanId === plan.id;

                            return (
                                <div
                                    key={plan.id}
                                    className={`flex flex-col justify-between p-6 rounded-2xl bg-white transition-all duration-300 relative border ${
                                        isCurrent
                                            ? "border-violet-600 shadow-lg ring-1 ring-violet-500/20"
                                            : "border-slate-200 hover:border-slate-300 hover:shadow-md"
                                    }`}
                                >
                                    {isCurrent && (
                                        <span className="absolute -top-3 right-4 px-3 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-violet-600 text-white shadow-sm">
                                            {t("currentPlanBadge")}
                                        </span>
                                    )}

                                    <div className="space-y-5">
                                        <div>
                                            <h3 className="text-lg font-black text-slate-900">
                                                {getPlanName(plan)}
                                            </h3>
                                            <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider font-bold">
                                                {plan.duration_days} {locale === 'en' ? 'days' : locale === 'kz' ? 'күн' : 'дней'}
                                            </p>
                                        </div>

                                        <div className="flex items-baseline gap-1.5 border-b border-slate-100 pb-4">
                                            <span className="text-3xl font-black text-slate-900 tracking-tight">
                                                {plan.price === 0 ? t("free") : `₸${parseFloat(plan.price as any).toLocaleString()}`}
                                            </span>
                                            {plan.price > 0 && (
                                                <span className="text-xs text-slate-500 font-medium lowercase">
                                                    / {t("duration").toLowerCase()}
                                                </span>
                                            )}
                                        </div>

                                        <ul className="space-y-3.5 text-xs text-slate-600">
                                            {plan.limits_json?.max_active_services !== undefined && (
                                                <li className="flex items-center gap-2.5">
                                                    <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                                    </svg>
                                                    <span>
                                                        {t("serviceLimit")}: <span className="font-bold text-slate-800">
                                                            {plan.limits_json.max_active_services === -1
                                                                ? t("unlimited")
                                                                : plan.limits_json.max_active_services}
                                                        </span>
                                                    </span>
                                                </li>
                                            )}
                                            {plan.limits_json?.max_portfolio_items !== undefined && (
                                                <li className="flex items-center gap-2.5">
                                                    <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                                    </svg>
                                                    <span>
                                                        {t("portfolioLimit")}: <span className="font-bold text-slate-800">
                                                            {plan.limits_json.max_portfolio_items === -1
                                                                ? t("unlimited")
                                                                : plan.limits_json.max_portfolio_items}
                                                        </span>
                                                    </span>
                                                </li>
                                            )}
                                            {plan.limits_json?.offers_per_month !== undefined && (
                                                <li className="flex items-center gap-2.5">
                                                    <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                                    </svg>
                                                    <span>
                                                        {t("offersPerMonth")}: <span className="font-bold text-slate-800">
                                                            {plan.limits_json.offers_per_month === -1
                                                                ? t("unlimited")
                                                                : plan.limits_json.offers_per_month}
                                                        </span>
                                                    </span>
                                                </li>
                                            )}
                                            {Object.entries(plan.limits_json || {})
                                                .filter(([key]) => key !== "max_active_services" && key !== "max_services" && key !== "offers_per_month" && key !== "max_portfolio_items")
                                                .map(([key, value]) => (
                                                    <li key={key} className="flex items-center gap-2.5">
                                                        <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                                        </svg>
                                                        <span className="capitalize">
                                                            {key.replace(/_/g, " ")}: <span className="font-bold text-slate-800">{value === -1 ? t("unlimited") : value ? "Yes" : "No"}</span>
                                                        </span>
                                                    </li>
                                                ))}
                                        </ul>
                                    </div>

                                    <div className="mt-8">
                                        {isCurrent ? (
                                            <div className="text-center text-xs font-bold text-violet-700 bg-violet-50 rounded-xl py-3 border border-violet-100">
                                                ✓ {t("currentPlanBadge")}
                                            </div>
                                        ) : (
                                            <Button
                                                onClick={() => handleCheckout(plan)}
                                                disabled={isAnyActivating || plan.code === 'free'}
                                                isLoading={activatingPlanId === plan.id}
                                                variant={plan.price === 0 ? "outline" : "primary"}
                                                className="w-full font-bold rounded-xl py-2.5 shadow-sm transition"
                                            >
                                                {activeProvider === 'paypal' ? (t("upgrade") || "Subscribe") : t("demoActivation")}
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
