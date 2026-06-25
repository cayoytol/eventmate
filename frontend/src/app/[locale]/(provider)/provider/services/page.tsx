// frontend/src/app/[locale]/(provider)/provider/services/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { useAuthStore } from "@/store/useAuthStore";
import type { Service } from "@/types/catalog";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function ProviderServicesPage() {
    const locale = useLocale();
    const t = useTranslations("provider.services");
    const pathname = usePathname();
    const user = useAuthStore((s) => s.user);

    const [services, setServices] = useState<Service[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchServices = async (signal?: AbortSignal) => {
        try {
            // GET ENDPOINTS.SERVICES params: { provider: "me" }
            const { data } = await api.get<{ results: Service[] } | Service[]>(
                ENDPOINTS.SERVICES,
                { params: { provider: "me" }, signal }
            );

            // Normalize response
            const list = Array.isArray(data) ? data : (data.results ?? []);
            setServices(list);
        } catch (err: any) {
            if (err.name === 'AbortError' || err.code === 'ERR_CANCELED') return;
            setError(err?.response?.data?.detail || "Failed to load services");
            setServices([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        const abortController = new AbortController();
        setIsLoading(true);
        fetchServices(abortController.signal);

        return () => abortController.abort();
    }, [pathname, user?.id]);

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
                <Link href={`/${locale}/provider/services/new/`}>
                    <Button className="font-bold rounded-xl shadow-md shadow-violet-100 flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                        </svg>
                        <span>{t("create")}</span>
                    </Button>
                </Link>
            </div>

            {error && (
                <div className="rounded-2xl bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm font-medium">
                    {error}
                </div>
            )}

            {services.length === 0 ? (
                <EmptyState
                    title={t("empty")}
                    description={locale === 'en' ? 'Create a service offering to list it in the catalog.' : 'Создайте первую услугу, чтобы она появилась в общем каталоге.'}
                    action={
                        <div className="mt-4">
                            <Link href={`/${locale}/provider/services/new/`}>
                                <Button>{t("emptyCta")}</Button>
                            </Link>
                        </div>
                    }
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {services.map((service) => (
                        <ServiceManagementCard key={service.id} service={service} locale={locale} t={t} />
                    ))}
                </div>
            )}
        </div>
    );
}

function ServiceManagementCard({ service, locale, t }: { service: Service; locale: string; t: any }) {
    const formattedPrice = service.price_amount
        ? parseFloat(service.price_amount.toString()).toLocaleString()
        : "0";

    return (
        <Card className="group relative flex flex-col justify-between p-6 border border-slate-200 rounded-2xl bg-white hover:border-violet-200 hover:shadow-md transition duration-200" hoverable>
            <div>
                {/* Image Section */}
                <div className="aspect-[16/10] w-full overflow-hidden bg-slate-50 relative rounded-xl border border-slate-100 mb-4 shadow-3xs">
                    {service.cover ? (
                        <img
                            src={service.cover}
                            alt={service.title}
                            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                            loading="lazy"
                        />
                    ) : (
                        <div className="flex h-full items-center justify-center text-slate-400 text-xs font-bold uppercase tracking-wider bg-violet-50/20">
                            {service.category_name || 'Service'}
                        </div>
                    )}
                    
                    {/* Status Badge inside image top-left */}
                    <div className="absolute top-3 left-3 z-10">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase border shadow-2xs ${
                            service.is_active
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                                : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}>
                            {service.is_active ? t("active") : t("inactive")}
                        </span>
                    </div>
                </div>

                <div className="flex items-center justify-between gap-3 mb-2.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-violet-700 bg-violet-50 px-2.5 py-0.5 rounded-full border border-violet-100">
                        {service.category_name}
                    </span>
                    {service.city && (
                        <span className="text-xs text-slate-500 font-semibold flex items-center gap-1">
                            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            {service.city}
                        </span>
                    )}
                </div>

                <h3 className="font-extrabold text-slate-900 group-hover:text-violet-600 transition-colors duration-200 line-clamp-1 mb-1 tracking-tight text-base leading-snug">{service.title}</h3>
                <p className="text-sm text-slate-500 line-clamp-2 leading-relaxed mb-4 h-10 font-medium">
                    {service.description}
                </p>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-slate-100 mt-4">
                <span className="font-black text-lg text-slate-900">
                    ₸ {formattedPrice}
                    {service.price_type && (
                        <span className="text-xs font-normal text-slate-500 ml-1">/{service.price_type}</span>
                    )}
                </span>
                <Link href={`/${locale}/provider/services/${service.id}/`}>
                    <Button variant="outline" size="sm" className="font-bold rounded-xl">
                        {t("edit")}
                    </Button>
                </Link>
            </div>
        </Card>
    );
}
