// frontend/src/app/[locale]/(provider)/provider/services/new/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { Category } from "@/types/catalog";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import ProviderLocationPicker from "@/components/map/ProviderLocationPicker";
import { uploadServiceCover } from "@/lib/api/services";
import { ServiceCoverUploader } from "@/components/services/ServiceCoverUploader";

export default function CreateServicePage() {
    const locale = useLocale();
    const t = useTranslations("provider.services");
    const router = useRouter();

    const [categories, setCategories] = useState<Category[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [coverFile, setCoverFile] = useState<File | null>(null);
    const [coverPreview, setCoverPreview] = useState<string | null>(null);
    const [createdServiceId, setCreatedServiceId] = useState<number | null>(null);

    // Clean up local preview object URL
    useEffect(() => {
        return () => {
            if (coverPreview) {
                URL.revokeObjectURL(coverPreview);
            }
        };
    }, [coverPreview]);

    // Form state
    const [formData, setFormData] = useState({
        title: "",
        category: "",
        description: "",
        price_amount: "",
        price_type: "fixed",
        city: "",
        address: "",
        latitude: null as number | null,
        longitude: null as number | null,
        is_active: true
    });

    // Load categories on mount
    useEffect(() => {
        const fetchCategories = async () => {
            try {
                const response = await api.get<Category[]>(ENDPOINTS.CATEGORIES);
                const categoriesData = Array.isArray(response.data)
                    ? response.data
                    : (response.data as any)?.results || [];
                setCategories(categoriesData);
            } catch (err: any) {
                console.error("Failed to load categories:", err);
                setError("Failed to load categories. Please refresh the page.");
            }
        };
        fetchCategories();
    }, []);

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
        setIsLoading(true);

        try {
            let serviceId = createdServiceId;

            if (!serviceId) {
                const payload = {
                    ...formData,
                    category: parseInt(formData.category),
                    latitude: formData.latitude === null || (formData.latitude as any) === "" ? null : parseFloat(formData.latitude as any),
                    longitude: formData.longitude === null || (formData.longitude as any) === "" ? null : parseFloat(formData.longitude as any),
                };
                const response = await api.post(ENDPOINTS.SERVICES, payload);
                serviceId = response.data.id;
            }

            if (coverFile && serviceId) {
                try {
                    const formDataObj = new FormData();
                    formDataObj.append("file", coverFile);
                    await uploadServiceCover(serviceId, formDataObj);
                } catch (coverErr: any) {
                    console.error("Cover upload failed:", coverErr);
                    setCreatedServiceId(serviceId);
                    setError(
                        locale === "en"
                            ? "Service was created successfully, but cover image upload failed. You can retry cover upload below."
                            : locale === "kz"
                            ? "Қызмет сәтті жасалды, бірақ мұқаба суретін жүктеу сәтсіз аяқталды. Төменде қайталауға болады."
                            : "Услуга создана успешно, но не удалось загрузить изображение обложки. Вы можете повторить попытку ниже."
                    );
                    setIsLoading(false);
                    return;
                }
            }

            router.replace(`/${locale}/provider/services/`);
        } catch (err: any) {
            console.error("Create failed:", err);
            const msg = err?.response?.data?.detail ||
                Object.values(err?.response?.data || {}).flat().join(", ") ||
                "Failed to create service";
            setError(msg);
        } finally {
            setIsLoading(false);
        }
    };

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
                <h1 className="text-3xl font-black text-slate-900 leading-tight">
                    {t("create")}
                </h1>
                <p className="text-sm text-slate-500">
                    {locale === 'en' ? 'Describe your event service offering and publish it to the event catalog.' : 'Опишите ваше предложение и опубликуйте его в общем event-каталоге.'}
                </p>
            </div>

            {error && (
                <div className="rounded-2xl bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 text-sm font-medium">
                    {error}
                </div>
            )}

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
                            placeholder="e.g. Professional Wedding Photography"
                        />

                        <div className="grid grid-cols-1 gap-4">
                            <Select
                                label={`${t("form.category")} *`}
                                name="category"
                                value={formData.category}
                                onChange={handleChange}
                                required
                            >
                                <option value="" className="text-slate-500">Select category...</option>
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
                        placeholder="Describe your service in detail..."
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
                    disabled={isLoading}
                />

                {/* Section: Service Cover Image */}
                <Card className="p-6 sm:p-8 space-y-6 border border-slate-200 rounded-2xl bg-white shadow-xs">
                    <h3 className="text-md font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                        <span className="w-6 h-6 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center text-xs font-bold">5</span>
                        <span>{locale === 'en' ? 'Service Cover Image' : locale === 'kz' ? 'Қызмет мұқабасы' : 'Обложка услуги'}</span>
                    </h3>

                    {createdServiceId ? (
                        <div className="space-y-4">
                            <ServiceCoverUploader
                                serviceId={createdServiceId}
                                initialCoverUrl={null}
                                onUploadSuccess={() => {
                                    router.replace(`/${locale}/provider/services/`);
                                }}
                                onDeleteSuccess={() => {}}
                            />
                            <div className="flex justify-end pt-2">
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => router.replace(`/${locale}/provider/services/`)}
                                    className="font-bold rounded-xl text-xs py-2 px-4 border border-slate-200 text-slate-600 hover:bg-slate-50"
                                >
                                    {locale === 'en' ? 'Skip Cover Upload' : locale === 'kz' ? 'Мұқаба жүктеуді өткізіп жіберу' : 'Пропустить загрузку обложки'}
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {!coverPreview ? (
                                <div
                                    onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); }}
                                    onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                                    onDrop={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                                            const file = e.dataTransfer.files[0];
                                            const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
                                            if (allowedTypes.includes(file.type) && file.size <= 5 * 1024 * 1024) {
                                                setCoverFile(file);
                                                setCoverPreview(URL.createObjectURL(file));
                                            }
                                        }
                                    }}
                                    onClick={() => document.getElementById('local-cover-input')?.click()}
                                    className="border-2 border-dashed border-slate-200 hover:border-slate-300 hover:bg-slate-50/30 rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200"
                                >
                                    <input
                                        id="local-cover-input"
                                        type="file"
                                        onChange={(e) => {
                                            if (e.target.files && e.target.files[0]) {
                                                const file = e.target.files[0];
                                                const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
                                                if (allowedTypes.includes(file.type) && file.size <= 5 * 1024 * 1024) {
                                                    setCoverFile(file);
                                                    setCoverPreview(URL.createObjectURL(file));
                                                }
                                            }
                                        }}
                                        accept="image/jpeg,image/png,image/webp"
                                        className="hidden"
                                    />
                                    <div className="p-4 bg-violet-50 text-violet-600 rounded-2xl mb-4">
                                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                        </svg>
                                    </div>
                                    <h3 className="text-sm font-bold text-slate-700">
                                        {locale === 'en' ? 'Choose File' : locale === 'kz' ? 'Файлды таңдаңыз' : 'Выберите файл'}
                                    </h3>
                                    <p className="text-xs text-slate-400 mt-1">
                                        {locale === 'en' ? 'or drag and drop it here' : locale === 'kz' ? 'немесе оны осында сүйреп апарыңыз' : 'или перетащите его сюда'}
                                    </p>
                                </div>
                            ) : (
                                <div className="border border-slate-200 rounded-2xl p-5 bg-slate-50 space-y-4">
                                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                                        <div className="min-w-0 flex-1">
                                            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                                                {locale === 'en' ? 'Selected file' : locale === 'kz' ? 'Таңдалған файл' : 'Выбранный файл'}
                                            </span>
                                            <span className="text-sm font-bold text-slate-700 truncate block mt-0.5">
                                                {coverFile?.name}
                                            </span>
                                        </div>
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => {
                                                if (coverPreview) URL.revokeObjectURL(coverPreview);
                                                setCoverPreview(null);
                                                setCoverFile(null);
                                            }}
                                            className="text-rose-600 hover:bg-rose-50/50 hover:text-rose-700 rounded-xl font-bold"
                                        >
                                            {locale === 'en' ? 'Remove Cover' : locale === 'kz' ? 'Мұқабаны жою' : 'Удалить обложку'}
                                        </Button>
                                    </div>
                                    <div className="aspect-[16/10] w-full bg-slate-200 rounded-xl overflow-hidden relative border border-slate-150">
                                        <img
                                            src={coverPreview}
                                            alt="Preview"
                                            className="h-full w-full object-cover"
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
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
                                checked={formData.is_active}
                                onChange={handleCheckboxChange}
                                className="w-5 h-5 rounded border-slate-300 text-violet-600 focus:ring-violet-500 transition cursor-pointer"
                            />
                            <div className="flex flex-col select-none">
                                <span className="text-sm font-extrabold text-slate-800">{t("form.isActive")}</span>
                                <span className="text-xs text-slate-500 font-semibold mt-0.5">
                                    {formData.is_active
                                        ? (locale === 'en' ? 'Service is visible to clients in catalog' : locale === 'kz' ? 'Қызмет каталогта көрінеді' : 'Услуга опубликована и видна в общем каталоге')
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
                        isLoading={isLoading}
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
