// frontend/src/app/[locale]/(provider)/provider/services/[id]/page.tsx
"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { ENDPOINTS, serviceUrl } from "@/lib/api/endpoints";
import type { Category, Service } from "@/types/catalog";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import ProviderLocationPicker from "@/components/map/ProviderLocationPicker";
import { ServiceCoverUploader } from "@/components/services/ServiceCoverUploader";

export default function EditServicePage(props: { params: Promise<{ id: string }> }) {
    const params = use(props.params);
    const { id } = params;

    const locale = useLocale();
    const t = useTranslations("provider.services");
    const router = useRouter();

    const [categories, setCategories] = useState<Category[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [initialCoverUrl, setInitialCoverUrl] = useState<string | null>(null);

    // Form state
    const [formData, setFormData] = useState({
        title: "",
        category: "",
        description: "",
        price_amount: "",
        price_type: "fixed" as "fixed" | "hourly" | "range",
        city: "",
        address: "",
        latitude: null as number | null,
        longitude: null as number | null,
        is_active: false
    });

    useEffect(() => {
        const loadData = async () => {
            try {
                // 1. Load Categories
                const catRes = await api.get<Category[]>(ENDPOINTS.CATEGORIES);
                setCategories(catRes.data);

                // 2. Load Service Detail
                const serviceRes = await api.get<Service>(serviceUrl(id));
                const s = serviceRes.data;

                setFormData({
                    title: s.title ?? "",
                    category: s.category?.toString() ?? "",
                    description: s.description ?? "",
                    price_amount: s.price_amount ?? "",
                    price_type: s.price_type ?? "fixed",
                    city: s.city ?? "",
                    address: s.address ?? "",
                    latitude: s.latitude !== null && s.latitude !== undefined ? s.latitude : null,
                    longitude: s.longitude !== null && s.longitude !== undefined ? s.longitude : null,
                    is_active: Boolean(s.is_active)
                });
                setInitialCoverUrl((s as any).cover_url || null);

            } catch (err: any) {
                console.error("Failed to load service:", err);
                setError(t("form.loadError") || "Failed to load service");
            } finally {
                setIsLoading(false);
            }
        };

        loadData();
    }, [id]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData(prev => ({
            ...prev,
            is_active: e.target.checked
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsSaving(true);

        try {
            const payload = {
                ...formData,
                category: parseInt(formData.category),
                latitude: formData.latitude === null || (formData.latitude as any) === "" ? null : parseFloat(formData.latitude as any),
                longitude: formData.longitude === null || (formData.longitude as any) === "" ? null : parseFloat(formData.longitude as any),
            };
            await api.patch(serviceUrl(id), payload);

            router.replace(`/${locale}/provider/services/`);
            router.refresh();
        } catch (err: any) {
            console.error("Update failed:", err);
            const msg = err?.response?.data?.detail ||
                Object.values(err?.response?.data || {}).flat().join(", ") ||
                "Failed to update service";
            setError(msg);
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-2xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    if (error && !isLoading) {
        return (
            <div className="max-w-2xl mx-auto space-y-4">
                <div className="bg-red-50 border border-red-100 text-red-700 p-5 rounded-2xl">{error}</div>
                <Button variant="outline" onClick={() => router.back()}>
                    Go Back
                </Button>
            </div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto space-y-8">
            {/* Header section */}
            <div className="space-y-1">
                <Link
                    href={`/${locale}/provider/services/`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-slate-500 hover:text-violet-600 transition mb-2"
                >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                    </svg>
                    <span>{locale === 'en' ? 'Back to list' : locale === 'kz' ? 'Тізімге оралу' : 'Назад к списку'}</span>
                </Link>
                <div className="flex flex-wrap items-center justify-between gap-4">
                    <h1 className="text-3xl font-black text-slate-900 leading-tight">
                        {t("edit")}
                    </h1>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-extrabold uppercase border shadow-3xs ${
                        formData.is_active
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                    }`}>
                        {formData.is_active ? t("active") : t("inactive")}
                    </span>
                </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* Section 1: Basics */}
                <Card className="p-6 sm:p-8 space-y-6 border border-slate-200 rounded-2xl bg-white shadow-xs">
                    <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">1</span>
                        <span>{locale === 'en' ? 'Service Basics' : locale === 'kz' ? 'Басты ақпарат' : 'Основная информация'}</span>
                    </h3>

                    <div className="space-y-4">
                        <Input
                            label={`${t("form.title")} *`}
                            name="title"
                            value={formData.title}
                            onChange={handleChange}
                            required
                        />

                        <div className="grid grid-cols-1 gap-4">
                            <Select
                                label={`${t("form.category")} *`}
                                name="category"
                                value={formData.category}
                                onChange={handleChange}
                                required
                            >
                                <option value="">Select category...</option>
                                {categories.map(cat => (
                                    <option key={cat.id} value={cat.id}>
                                        {cat[`name_${locale as 'ru' | 'en' | 'kz'}`] || cat.name_en}
                                    </option>
                                ))}
                            </Select>
                        </div>
                    </div>
                </Card>

                {/* Section 2: Pricing */}
                <Card className="p-6 sm:p-8 space-y-6 border border-slate-200 rounded-2xl bg-white shadow-xs">
                    <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">2</span>
                        <span>{locale === 'en' ? 'Pricing & Unit' : locale === 'kz' ? 'Баға және төлем' : 'Стоимость и оплата'}</span>
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <Input
                            label={`${t("form.price")} (₸) *`}
                            name="price_amount"
                            type="number"
                            min="0"
                            value={formData.price_amount}
                            onChange={handleChange}
                            required
                        />

                        <Select
                            label={t("form.priceType")}
                            name="price_type"
                            value={formData.price_type}
                            onChange={handleChange}
                        >
                            <option value="fixed">Fixed Price</option>
                            <option value="hourly">Per Hour</option>
                            <option value="range">Range</option>
                        </Select>
                    </div>
                </Card>

                {/* Section 3: Description */}
                <Card className="p-6 sm:p-8 space-y-6 border border-slate-200 rounded-2xl bg-white shadow-xs">
                    <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">3</span>
                        <span>{t("form.description")}</span>
                    </h3>

                    <Textarea
                        label={`${t("form.description")} *`}
                        name="description"
                        value={formData.description}
                        onChange={handleChange}
                        required
                        rows={5}
                    />
                </Card>

                {/* Section 5: Location Details */}
                <ProviderLocationPicker
                    value={{
                        address: formData.address,
                        city: formData.city,
                        latitude: formData.latitude,
                        longitude: formData.longitude,
                    }}
                    onChange={(val) => {
                        setFormData(prev => ({
                            ...prev,
                            address: val.address,
                            city: val.city,
                            latitude: val.latitude,
                            longitude: val.longitude,
                        }));
                    }}
                    locale={locale}
                    disabled={isSaving}
                />

                {/* Section: Service Cover Image */}
                <Card className="p-6 sm:p-8 space-y-6 border border-slate-200 rounded-2xl bg-white shadow-xs">
                    <ServiceCoverUploader
                        serviceId={id}
                        initialCoverUrl={initialCoverUrl}
                        onUploadSuccess={(media) => {
                            setInitialCoverUrl(media.file);
                        }}
                        onDeleteSuccess={() => {
                            setInitialCoverUrl(null);
                        }}
                        disabled={isSaving}
                    />
                </Card>

                {/* Section 4: Visibility */}
                <Card className="p-6 sm:p-8 space-y-6 border border-slate-200 rounded-2xl bg-white shadow-xs">
                    <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">4</span>
                        <span>{locale === 'en' ? 'Visibility Settings' : locale === 'kz' ? 'Көріну реттеулері' : 'Настройки видимости'}</span>
                    </h3>

                    <div className="p-4 bg-slate-50/50 border border-slate-200 rounded-2xl hover:bg-slate-50 transition duration-200">
                        <label className="flex items-center gap-3.5 cursor-pointer">
                            <input
                                type="checkbox"
                                name="is_active"
                                checked={!!formData.is_active}
                                onChange={handleCheckboxChange}
                                className="w-5 h-5 rounded border-slate-300 text-violet-600 focus:ring-violet-500 transition cursor-pointer"
                            />
                            <div className="flex flex-col select-none">
                                <span className="text-sm font-extrabold text-slate-800">{t("form.isActive")}</span>
                                <span className="text-xs text-slate-500 font-semibold mt-0.5">
                                    {formData.is_active
                                        ? (locale === 'en' ? 'Service is visible to clients in catalog' : locale === 'kz' ? 'Қызмет каталогта клиенттерге көрінеді' : 'Услуга опубликована и видна в общем каталоге')
                                        : (locale === 'en' ? 'Service is hidden from catalog' : locale === 'kz' ? 'Қызмет каталогта клиенттерге көрінбейді' : 'Услуга скрыта из каталога')}
                                </span>
                            </div>
                        </label>
                    </div>
                </Card>

                {/* Form Actions */}
                <div className="pt-4 flex gap-4">
                    <Button
                        type="submit"
                        isLoading={isSaving}
                        className="flex-1 font-bold text-sm py-3.5 rounded-2xl shadow-md shadow-violet-100"
                    >
                        {t("form.submit")}
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => router.back()}
                        className="px-6 border border-slate-200 text-slate-700 hover:bg-slate-50 font-bold rounded-2xl text-sm"
                    >
                        Cancel
                    </Button>
                </div>
            </form>
        </div>
    );
}
