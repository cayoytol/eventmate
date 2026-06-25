// frontend/src/app/[locale]/(provider)/provider/requests/[id]/page.tsx
"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { EventRequest } from "@/types/marketplace";
import type { Service } from "@/types/catalog";
import { Availability } from "@/types/availability";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { Badge } from "@/components/ui/Badge";

export default function RequestDetailPage(props: { params: Promise<{ id: string }> }) {
    const params = use(props.params);
    const { id } = params;

    const locale = useLocale();
    const t = useTranslations("provider.requests");
    const tCommon = useTranslations("common");
    const tAi = useTranslations("ai");
    const router = useRouter();

    const [request, setRequest] = useState<EventRequest | null>(null);
    const [myServices, setMyServices] = useState<Service[]>([]);

    // Availability State
    const [availability, setAvailability] = useState<Availability | null>(null);
    const [isCheckingAvailability, setIsCheckingAvailability] = useState(true);

    // UI states
    const [isLoading, setIsLoading] = useState(true);
    const [isSending, setIsSending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    // AI state
    const [isAiLoading, setIsAiLoading] = useState(false);
    const [aiError, setAiError] = useState<string | null>(null);
    const [aiNotice, setAiNotice] = useState<string | null>(null);
    const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
    const [aiSource, setAiSource] = useState<string | null>(null);

    // Form
    const [form, setForm] = useState({
        service: "",
        price: "",
        message: "",
        delivery_date: ""
    });

    useEffect(() => {
        const loadData = async () => {
            try {
                // 1. Load Request Detail
                const reqRes = await api.get<EventRequest>(`${ENDPOINTS.REQUESTS}${id}/`);
                setRequest(reqRes.data);

                // Pre-fill delivery date
                const eventDateStr = reqRes.data.event_date.split('T')[0];
                setForm(prev => ({
                    ...prev,
                    delivery_date: eventDateStr
                }));

                // 2. Check Availability for this date
                checkAvailability(eventDateStr);

                // 3. Load My Services (for dropdown)
                const servicesRes = await api.get<{ results: Service[] } | Service[]>(
                    ENDPOINTS.SERVICES,
                    { params: { provider: "me" } }
                );
                const services = Array.isArray(servicesRes.data) ? servicesRes.data : servicesRes.data.results;
                setMyServices(services || []);

            } catch (err: any) {
                console.error("Load failed:", err);
                setError("Failed to load request details");
            } finally {
                setIsLoading(false);
            }
        };
        loadData();
    }, [id]);

    const checkAvailability = async (eventDateStr: string | Date) => {
        setIsCheckingAvailability(true);
        try {
            const reqStart = request?.event_start_at ? new Date(request.event_start_at) : new Date(eventDateStr);
            const reqEnd = new Date(reqStart.getTime() + 60 * 60 * 1000); // Default 1 hour assumption if unknown service

            // Format dates for API query
            const dateQuery = reqStart.toISOString().split('T')[0];

            const { data } = await api.get<Availability[]>(`/availability/my/?from=${dateQuery}&to=${dateQuery}`);

            // Check overlaps
            const busySlot = data.find(slot => {
                const slotStart = new Date(slot.start_at);
                const slotEnd = new Date(slot.end_at);
                return (slotStart < reqEnd && slotEnd > reqStart);
            });

            setAvailability(busySlot || null);
        } catch (error) {
            console.error("Failed to check availability", error);
        } finally {
            setIsCheckingAvailability(false);
        }
    };

    const handleAiAssist = async () => {
        if (!request) return;
        setAiError(null);
        setAiNotice(null);
        setAiSuggestion(null);
        setAiSource(null);
        setIsAiLoading(true);

        try {
            const currentService = myServices.find(s => s.id === parseInt(form.service, 10));
            const serviceTitle = currentService ? currentService.title : "";

            const { data } = await api.post<{ suggested_letter: string, source: string }>(
                ENDPOINTS.AI_OFFER_ASSISTANT,
                {
                    request_description: request.description,
                    service_title: serviceTitle,
                    price: form.price,
                    locale
                }
            );

            if (data.suggested_letter) {
                if (form.message.trim().length <= 15) {
                    setForm(prev => ({
                        ...prev,
                        message: data.suggested_letter
                    }));
                    if (data.source === "fallback") {
                        setAiNotice(tAi("fallbackUsed"));
                    }
                } else {
                    setAiSuggestion(data.suggested_letter);
                    setAiSource(data.source || "llm");
                }
            } else {
                setAiError(tAi("error"));
            }
        } catch (err: any) {
            console.error("AI Assistant request failed:", err);
            const errCode = err.response?.data?.code;
            if (errCode === "ai_not_configured") {
                setAiError(tAi("notConfigured") || "AI service is not configured.");
            } else if (errCode === "subscription_required") {
                setAiError(tAi("subscriptionRequired") || "AI features require an active subscription.");
            } else if (errCode === "limit_reached") {
                setAiError(tAi("limitReached") || "AI request limit reached.");
            } else {
                setAiError(tAi("requestFailed") || "AI request failed.");
            }
        } finally {
            setIsAiLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (availability) {
            setError(t("dateUnavailableAlert"));
            return;
        }

        setError(null);
        setIsSending(true);

        try {
            await api.post(ENDPOINTS.OFFERS, {
                request: parseInt(id),
                service: parseInt(form.service),
                price: parseInt(form.price),
                message: form.message,
                delivery_date: form.delivery_date
            });

            setSuccess(true);
            setTimeout(() => {
                router.push(`/${locale}/provider/requests/`);
            }, 2000);
        } catch (err: any) {
            console.error("Offer failed:", err);
            const msg = err?.response?.data?.detail ||
                Object.values(err?.response?.data || {}).flat().join(", ") ||
                "Failed to send offer. You might have already sent one.";
            setError(msg);
        } finally {
            setIsSending(false);
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    if (!request) {
        return (
            <div className="max-w-4xl mx-auto py-12 text-center text-red-500 font-semibold">
                Request not found
            </div>
        );
    }

    const categoryName = request.category
        ? (request.category[`name_${locale as 'ru' | 'en' | 'kz'}`] || request.category.name_en)
        : tCommon("notSpecified");
    const isDateBlocked = !!availability;

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            {/* Back link */}
            <div className="flex items-center">
                <Link
                    href={`/${locale}/provider/requests`}
                    className="group inline-flex items-center text-sm font-bold text-slate-500 hover:text-violet-600 transition duration-200"
                >
                    <svg className="mr-2 h-4 w-4 transform group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    {t("back")}
                </Link>
            </div>

            {/* Request Detail Card */}
            <Card className="border border-slate-200 p-6 sm:p-8 rounded-2xl bg-white shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 pb-6 border-b border-slate-100">
                    <div>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-violet-50 text-violet-700 border border-violet-100 mb-2">
                            {categoryName}
                        </span>
                        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-tight tracking-tight">{request.title}</h1>
                    </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-6">
                    <div>
                        <span className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">Event Date</span>
                        <span className="font-semibold text-slate-800">
                            {new Date(request.event_date).toLocaleDateString(locale, {
                                year: 'numeric',
                                month: 'long',
                                day: 'numeric'
                            })}
                        </span>
                    </div>
                    <div>
                        <span className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">City</span>
                        <span className="font-semibold text-slate-800">{request.city}</span>
                    </div>
                    <div>
                        <span className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{t("budget")}</span>
                        <span className="font-bold text-slate-900">{request.budget_min.toLocaleString()} - {request.budget_max.toLocaleString()} ₸</span>
                    </div>
                </div>

                <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 shadow-3xs">
                    <span className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2">Description</span>
                    <p className="text-slate-700 leading-relaxed whitespace-pre-wrap text-sm font-medium">{request.description}</p>
                </div>
            </Card>

            {/* Availability Warning */}
            {isDateBlocked && (
                <Card className="border border-rose-200 bg-rose-50/50 p-5 rounded-2xl shadow-3xs">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                        <div className="space-y-1.5">
                            <div className="flex items-center gap-2">
                                <span className="bg-rose-100 text-rose-700 text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border border-rose-200">
                                    {t("dateUnavailableTitle")}
                                </span>
                            </div>
                            <p className="text-sm text-rose-700 leading-relaxed font-semibold">
                                {t("dateUnavailableDesc", {
                                    type: availability.status === 'busy' ? t("busyType") : t("blockedType"),
                                    start: new Date(availability.start_at).toLocaleString(locale),
                                    end: new Date(availability.end_at).toLocaleTimeString(locale)
                                })}
                            </p>
                        </div>
                        {availability.status === 'blocked' && (
                            <Link href={`/${locale}/provider/calendar/`} className="text-sm font-bold text-rose-700 hover:text-rose-800 underline shrink-0 transition">
                                {t("manageCalendar")}
                            </Link>
                        )}
                    </div>
                </Card>
            )}

            {/* Offer Form */}
            <Card className={`border border-slate-200 p-6 sm:p-8 rounded-2xl bg-white shadow-xs ${isDateBlocked ? 'opacity-50 pointer-events-none' : ''}`}>
                <h2 className="text-xl font-bold text-slate-900 mb-6">{t("createOffer")}</h2>

                {success ? (
                    <div className="bg-emerald-50 border border-emerald-100 text-emerald-700 p-6 rounded-2xl text-center shadow-3xs">
                        <p className="font-extrabold text-lg mb-1">{t("success")}</p>
                        <p className="text-sm font-medium">Redirecting...</p>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit} className="space-y-6">
                        {error && (
                            <div className="bg-rose-50 border border-rose-100 text-rose-700 p-4 rounded-2xl text-sm font-medium">
                                {error}
                            </div>
                        )}

                        <div className="space-y-1.5">
                            <Select
                                label={`${t("selectService")} *`}
                                value={form.service}
                                onChange={e => setForm({ ...form, service: e.target.value })}
                                required
                            >
                                <option value="">Select a service...</option>
                                {myServices.filter(s => s.is_active).map(service => (
                                    <option key={service.id} value={service.id}>
                                        {service.title} ({parseInt(service.price_amount).toLocaleString()} ₸)
                                    </option>
                                ))}
                            </Select>
                            {myServices.length === 0 && (
                                <p className="text-xs text-amber-700 font-semibold bg-amber-50 border border-amber-100 rounded-lg p-3 mt-1 shadow-3xs">
                                    You need to create a service first. <a href={`/${locale}/provider/services/new`} className="underline font-bold hover:text-amber-800 transition">Create Service</a>
                                </p>
                            )}
                        </div>

                        <Input
                            label={`${t("price")} (₸) *`}
                            required
                            type="number"
                            min="0"
                            value={form.price}
                            onChange={e => setForm({ ...form, price: e.target.value })}
                        />

                        <div className="space-y-4 pt-2">
                            {/* Premium AI Assistant helper panel */}
                            <div className="bg-gradient-to-br from-violet-50 to-slate-50 border border-violet-100 p-5 rounded-2xl flex flex-col gap-4 shadow-3xs">
                                <div className="flex items-start gap-3.5">
                                    <span className="text-xl">✨</span>
                                    <div className="space-y-1">
                                        <p className="text-xs font-bold text-violet-800">
                                            {locale === 'en' ? 'Smart AI Assistant' : locale === 'kz' ? 'Ақылды ИИ Көмекшісі' : 'Умный ИИ-помощник'}
                                        </p>
                                        <p className="text-xs text-violet-700/90 leading-relaxed font-semibold">
                                            {tAi("reviewBeforeSubmit") || "Текст будет создан автоматически ИИ на основе заполненных полей. Вы всегда сможете его отредактировать перед отправкой."}
                                        </p>
                                    </div>
                                </div>
                                <Button
                                    type="button"
                                    onClick={handleAiAssist}
                                    disabled={isAiLoading || !form.service}
                                    variant="secondary"
                                    size="sm"
                                    className="bg-violet-600 hover:bg-violet-700 text-white font-extrabold flex items-center justify-center gap-1.5 shadow-xs shadow-violet-100 transition duration-200 active:scale-95 w-full sm:w-auto self-start"
                                >
                                    {isAiLoading ? (
                                        <span>{tAi("loading")}</span>
                                    ) : (
                                        <>
                                            <span>✨</span>
                                            <span>{tAi("assistOfferButton")}</span>
                                        </>
                                    )}
                                </Button>
                            </div>

                            <div className="space-y-1.5">
                                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">{t("message")}</label>
                                <Textarea
                                    value={form.message}
                                    onChange={e => setForm({ ...form, message: e.target.value })}
                                    rows={6}
                                    placeholder="Hi, I'd love to help with your event..."
                                />
                                {aiNotice && <p className="text-xs text-slate-500 font-semibold mt-1">{aiNotice}</p>}
                                {aiError && <p className="text-xs text-rose-500 font-semibold mt-1">{aiError}</p>}

                                {aiSuggestion && (
                                    <div className="bg-gradient-to-br from-violet-50/50 to-slate-50 border border-violet-200 rounded-2xl p-5 space-y-4 shadow-sm mt-4">
                                        <div className="flex items-center justify-between">
                                            <h4 className="text-sm font-bold text-slate-900">
                                                {tAi("suggestionPreview")}
                                            </h4>
                                            <Badge variant={aiSource === "llm" ? "violet" : "warning"}>
                                                {aiSource === "llm" ? tAi("sourceLlm") : tAi("sourceFallback")}
                                            </Badge>
                                        </div>
                                        
                                        <div className="bg-white border border-slate-200 rounded-xl p-4 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed font-medium max-h-60 overflow-y-auto shadow-3xs">
                                            {aiSuggestion}
                                        </div>

                                        <div className="flex items-start gap-2 text-xs text-slate-500 font-semibold leading-relaxed">
                                            <span>ℹ️</span>
                                            <span>{tAi("noOverwriteNotice")} {tAi("reviewBeforeSubmit")}</span>
                                        </div>

                                        <div className="flex flex-wrap gap-2.5 pt-1">
                                            <Button
                                                type="button"
                                                size="sm"
                                                onClick={() => {
                                                    setForm(prev => ({ ...prev, message: aiSuggestion }));
                                                    setAiSuggestion(null);
                                                    setAiSource(null);
                                                }}
                                                className="bg-violet-600 hover:bg-violet-700 text-white font-extrabold shadow-xs shadow-violet-100"
                                            >
                                                {tAi("replaceDraft")}
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => {
                                                    setForm(prev => ({
                                                        ...prev,
                                                        message: prev.message ? `${prev.message}\n\n${aiSuggestion}` : aiSuggestion
                                                    }));
                                                    setAiSuggestion(null);
                                                    setAiSource(null);
                                                }}
                                                className="bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-extrabold"
                                            >
                                                {tAi("insertBelow")}
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => {
                                                    setAiSuggestion(null);
                                                    setAiSource(null);
                                                }}
                                                className="hover:bg-slate-100 text-slate-500 font-extrabold"
                                            >
                                                {tAi("dismissSuggestion")}
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="pt-4">
                            <Button
                                type="submit"
                                disabled={myServices.length === 0 || isDateBlocked || isSending}
                                isLoading={isSending}
                                className="w-full font-bold text-sm py-3.5 rounded-2xl shadow-md shadow-violet-100"
                            >
                                {t("submit")}
                            </Button>
                        </div>
                    </form>
                )}
            </Card>
        </div>
    );
}
