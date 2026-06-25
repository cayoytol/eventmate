// frontend/src/app/[locale]/(dashboard)/dashboard/requests/new/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "@/routing";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/routing";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { Category } from "@/types/catalog";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export default function CreateRequestPage() {
    const locale = useLocale();
    const router = useRouter();
    const t = useTranslations("dashboard.requests.createForm");
    const tAi = useTranslations("ai");
    const tDetail = useTranslations("dashboard.requests.detail");

    // Form state
    const [categoryId, setCategoryId] = useState("");
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [city, setCity] = useState("");
    const [eventDate, setEventDate] = useState("");
    const [budgetMin, setBudgetMin] = useState("");
    const [budgetMax, setBudgetMax] = useState("");

    // AI state
    const [isAiLoading, setIsAiLoading] = useState(false);
    const [aiError, setAiError] = useState<string | null>(null);
    const [aiNotice, setAiNotice] = useState<string | null>(null);
    const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
    const [aiSource, setAiSource] = useState<string | null>(null);

    // UI state
    const [categories, setCategories] = useState<Category[]>([]);
    const [isLoadingCategories, setIsLoadingCategories] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Fetch categories on mount
    useEffect(() => {
        const fetchCategories = async () => {
            try {
                const { data } = await api.get<Category[]>(ENDPOINTS.CATEGORIES);
                const rootCategories = data.filter((cat) => cat.parent === null);
                setCategories(rootCategories);
            } catch (err) {
                console.error("Failed to load categories:", err);
            } finally {
                setIsLoadingCategories(false);
            }
        };

        fetchCategories();
    }, []);

    const getCategoryName = (category: Category) => {
        switch (locale) {
            case "en":
                return category.name_en;
            case "kz":
                return category.name_kz;
            default:
                return category.name_ru;
        }
    };

    const validateForm = (): string | null => {
        if (!categoryId || !title || !city || !eventDate || !budgetMin || !budgetMax) {
            return t("errors.required");
        }

        const min = parseInt(budgetMin, 10);
        const max = parseInt(budgetMax, 10);
        if (isNaN(min) || isNaN(max) || min <= 0 || max <= 0) {
            return t("errors.budgetInvalid");
        }
        if (max <= min) {
            return t("errors.budgetInvalid");
        }

        const selectedDate = new Date(eventDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        if (selectedDate < today) {
            return t("errors.dateInvalid");
        }

        return null;
    };

    const handleAiAssist = async () => {
        setAiError(null);
        setAiNotice(null);
        setAiSuggestion(null);
        setAiSource(null);
        setIsAiLoading(true);

        try {
            const currentCat = categories.find(c => c.id === parseInt(categoryId, 10));
            const categoryName = currentCat ? getCategoryName(currentCat) : "";

            const { data } = await api.post<{ suggested_text: string, source: string }>(
                ENDPOINTS.AI_REQUEST_ASSISTANT,
                {
                    category: categoryName,
                    city,
                    event_date: eventDate,
                    budget: budgetMin && budgetMax ? `${budgetMin} - ${budgetMax}` : budgetMin || budgetMax || "",
                    draft: description,
                    locale
                }
            );

            if (data.suggested_text) {
                if (description.trim().length <= 15) {
                    setDescription(data.suggested_text);
                    if (data.source === "fallback") {
                        setAiNotice(tAi("fallbackUsed"));
                    }
                } else {
                    setAiSuggestion(data.suggested_text);
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
        setError(null);

        const validationError = validateForm();
        if (validationError) {
            setError(validationError);
            return;
        }

        setIsSubmitting(true);

        try {
            await api.post(ENDPOINTS.REQUESTS, {
                category: parseInt(categoryId, 10),
                title,
                description,
                city,
                event_date: eventDate,
                budget_min: parseInt(budgetMin, 10),
                budget_max: parseInt(budgetMax, 10),
            });

            router.push("/dashboard/requests");
        } catch (err: any) {
            const msg =
                err?.response?.data?.detail ||
                err?.response?.data?.non_field_errors?.[0] ||
                t("errors.createFailed");
            setError(msg);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="max-w-3xl mx-auto space-y-8">
            {/* Header section */}
            <div className="space-y-1">
                <Link
                    href="/dashboard/requests"
                    className="inline-flex items-center gap-1 text-xs font-bold text-slate-500 hover:text-violet-600 transition mb-2"
                >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                    </svg>
                    <span>{tDetail("backToList").replace("← ", "")}</span>
                </Link>
                <h1 className="text-3xl font-black text-slate-900 leading-tight">
                    {t("title")}
                </h1>
                <p className="text-sm text-slate-500">
                    {t("subtitle")}
                </p>
            </div>

            {error ? (
                <div className="rounded-2xl bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 text-sm font-medium">
                    {error}
                </div>
            ) : null}

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* Section 1: Event Basics */}
                <Card className="p-6 md:p-8 space-y-6 border border-slate-200 shadow-xs rounded-2xl">
                    <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">1</span>
                        <span>{locale === 'en' ? 'Event Basics' : locale === 'kz' ? 'Басты ақпарат' : 'Основная информация'}</span>
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Category */}
                        <div className="space-y-1 md:col-span-2">
                            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                                {t("category")} <span className="text-rose-500">*</span>
                            </label>
                            {isLoadingCategories ? (
                                <div className="text-xs text-slate-400">Loading categories...</div>
                            ) : (
                                <Select
                                    value={categoryId}
                                    onChange={(e) => setCategoryId(e.target.value)}
                                    required
                                >
                                    <option value="">{t("categoryPlaceholder")}</option>
                                    {categories.map((cat) => (
                                        <option key={cat.id} value={cat.id}>
                                            {getCategoryName(cat)}
                                        </option>
                                    ))}
                                </Select>
                            )}
                        </div>

                        {/* Title */}
                        <div className="space-y-1 md:col-span-2">
                            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                                {t("requestTitle")} <span className="text-rose-500">*</span>
                            </label>
                            <Input
                                type="text"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder={t("requestTitlePlaceholder")}
                                required
                            />
                        </div>

                        {/* City */}
                        <div className="space-y-1">
                            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                                {t("city")} <span className="text-rose-500">*</span>
                            </label>
                            <Input
                                type="text"
                                value={city}
                                onChange={(e) => setCity(e.target.value)}
                                placeholder={t("cityPlaceholder")}
                                required
                            />
                        </div>

                        {/* Event Date */}
                        <div className="space-y-1">
                            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                                {t("eventDate")} <span className="text-rose-500">*</span>
                            </label>
                            <Input
                                type="date"
                                value={eventDate}
                                onChange={(e) => setEventDate(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                </Card>

                {/* Section 2: AI Description Assistant */}
                <Card className="p-6 md:p-8 space-y-6 border border-slate-200 shadow-xs rounded-2xl">
                    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-3">
                        <h3 className="text-md font-bold text-slate-900 flex items-center gap-2">
                            <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">2</span>
                            <span>{t("description")}</span>
                        </h3>
                        <Button
                            type="button"
                            onClick={handleAiAssist}
                            disabled={isAiLoading || (!categoryId && !city && !eventDate)}
                            variant="secondary"
                            size="sm"
                            className="bg-violet-600 hover:bg-violet-700 text-white font-extrabold flex items-center gap-1.5 shadow-xs shadow-violet-100 transition duration-200 active:scale-95"
                        >
                            {isAiLoading ? (
                                <span>{tAi("loading")}</span>
                            ) : (
                                <>
                                    <span>✨</span>
                                    <span>{tAi("assistRequestButton")}</span>
                                </>
                            )}
                        </Button>
                    </div>

                    <div className="space-y-4">
                        {/* Premium violet helper panel */}
                        <div className="bg-gradient-to-br from-violet-50 to-slate-50 border border-violet-100 p-5 rounded-2xl flex items-start gap-3.5 shadow-3xs">
                            <span className="text-xl">✨</span>
                            <div className="space-y-1">
                                <p className="text-xs font-bold text-violet-800">
                                    {locale === 'en' ? 'Smart AI Assistant' : locale === 'kz' ? 'Ақылды ИИ Көмекшісі' : 'Умный ИИ-помощник'}
                                </p>
                                <p className="text-xs text-violet-700/90 leading-relaxed font-medium">
                                    {tAi("reviewBeforeSubmit") || "Текст будет создан автоматически ИИ на основе заполненных полей. Вы всегда сможете его отредактировать перед отправкой."}
                                </p>
                            </div>
                        </div>

                        <Textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder={t("descriptionPlaceholder")}
                            rows={6}
                        />

                        {aiNotice && <p className="text-xs text-slate-500 font-semibold">{aiNotice}</p>}
                        {aiError && <p className="text-xs text-rose-500 font-semibold">{aiError}</p>}

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
                                            setDescription(aiSuggestion);
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
                                            setDescription(prev => prev ? `${prev}\n\n${aiSuggestion}` : aiSuggestion);
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
                </Card>

                {/* Section 3: Budget details */}
                <Card className="p-6 md:p-8 space-y-6 border border-slate-200 shadow-xs rounded-2xl">
                    <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">3</span>
                        <span>{locale === 'en' ? 'Budget Details' : locale === 'kz' ? 'Бюджет мәліметтері' : 'Детали бюджета'}</span>
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-1">
                            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                                {t("budgetMin")} <span className="text-rose-500">*</span>
                            </label>
                            <Input
                                type="number"
                                value={budgetMin}
                                onChange={(e) => setBudgetMin(e.target.value)}
                                min="1"
                                required
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                                {t("budgetMax")} <span className="text-rose-500">*</span>
                            </label>
                            <Input
                                type="number"
                                value={budgetMax}
                                onChange={(e) => setBudgetMax(e.target.value)}
                                min="1"
                                required
                            />
                        </div>
                    </div>
                </Card>

                {/* Action buttons */}
                <div className="flex gap-4 pt-4">
                    <Button
                        type="submit"
                        disabled={isSubmitting}
                        variant="primary"
                        isLoading={isSubmitting}
                        className="flex-1 font-bold text-sm py-3.5 rounded-2xl shadow-md shadow-violet-100"
                    >
                        {t("submit")}
                    </Button>
                    <Link
                        href="/dashboard/requests"
                        className="inline-flex items-center justify-center px-6 border border-slate-200 text-slate-700 hover:bg-slate-50 font-bold rounded-2xl text-sm transition active:scale-95"
                    >
                        {t("cancel")}
                    </Link>
                </div>
            </form>
        </div>
    );
}
