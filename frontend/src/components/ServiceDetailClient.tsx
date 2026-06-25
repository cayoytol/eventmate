'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Link } from '@/routing';
import { useTranslations } from 'next-intl';
import { Service } from '@/types/catalog';
import ContactModal from '@/components/ContactModal';
import { useAuthStore } from '@/store/useAuthStore';
import FavoriteButton from '@/components/features/favorites/FavoriteButton';
import ServiceComments from '@/components/features/comments/ServiceComments';
import ReportButton from '@/components/features/reports/ReportButton';
import { Card } from '@/components/ui/Card';

interface ServiceDetailClientProps {
    service: Service;
    locale: string;
}

export default function ServiceDetailClient({ service, locale }: ServiceDetailClientProps) {
    const t = useTranslations('service');
    const tCommon = useTranslations('common');
    const router = useRouter();
    const searchParams = useSearchParams();
    const { user, isReady } = useAuthStore();

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [imageFailed, setImageFailed] = useState(false);

    useEffect(() => {
        setImageFailed(false);
    }, [service.cover]);

    // Auto-reopen modal after login via ?contact=1
    useEffect(() => {
        if (isReady && searchParams.get('contact') === '1') {
            setIsModalOpen(true);
            // Remove query param (shallow replace)
            const newUrl = `/${locale}/service/${service.id}`;
            router.replace(newUrl, { scroll: false });
        }
    }, [isReady, searchParams, locale, service.id, router]);

    // Check ownership safely
    const providerId = typeof service.provider === 'object' && service.provider !== null
        ? (service.provider as any).id
        : service.provider;
    const isOwner = user?.provider_profile_id === providerId;

    // Handle inactive service
    if (!service.is_active && !isOwner) {
        return (
            <div className="container mx-auto px-4 py-16 text-center max-w-xl">
                <h1 className="text-4xl font-black text-neutral-900 mb-4">404</h1>
                <p className="text-neutral-500">{t('unavailable')}</p>
            </div>
        );
    }

    let ctaText = t('ctaGuest');
    if (isOwner) {
        ctaText = t('ctaOwner');
    } else if (user) {
        ctaText = t('ctaClient');
    }

    const handleContactClick = () => {
        if (isOwner) {
            router.push(`/provider/services/${service.id}/`);
            return;
        }
        if (!user) {
            const nextUrl = `/${locale}/service/${service.id}?contact=1`;
            router.push(`/login?next=${encodeURIComponent(nextUrl)}`);
            return;
        }
        setIsModalOpen(true);
    };

    return (
        <>
            <div className="container mx-auto px-4 py-8 max-w-5xl">
                {/* Back button link */}
                <Link
                    href="/catalog"
                    className="inline-flex items-center gap-1 text-sm font-bold text-neutral-500 hover:text-violet-600 transition mb-6"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                    </svg>
                    {t('backToList') || "Назад к каталогу"}
                </Link>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Main Content Column */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Cover Image */}
                        {service.cover && !imageFailed ? (
                            <div className="aspect-[16/9] w-full overflow-hidden rounded-3xl bg-neutral-50 border border-neutral-150 shadow-xs relative">
                                <img
                                    src={service.cover}
                                    alt={service.title}
                                    className="h-full w-full object-cover"
                                    onError={() => setImageFailed(true)}
                                />
                            </div>
                        ) : (
                            <div className="aspect-[16/9] w-full overflow-hidden rounded-3xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-fuchsia-600 text-white flex flex-col items-center justify-center p-8 text-center select-none overflow-hidden relative shadow-xs border border-neutral-150">
                                <div className="absolute -bottom-16 -right-16 w-48 h-48 rounded-full bg-white/5 border border-white/10 pointer-events-none" />
                                <div className="absolute -top-16 -left-16 w-40 h-40 rounded-full bg-white/5 pointer-events-none" />
                                
                                <span className="text-6xl font-black opacity-25 mb-2 tracking-wider uppercase select-none">
                                    {service.category_name ? service.category_name.slice(0, 2).toUpperCase() : 'SR'}
                                </span>
                                <span className="text-sm font-black uppercase tracking-widest text-violet-100/95 max-w-full truncate px-4 select-none">
                                    {service.category_name || 'Service'}
                                </span>
                            </div>
                        )}

                        {/* Title & Category Info Card */}
                        <Card className="p-6 md:p-8">
                            <div className="flex items-start justify-between gap-4 mb-4">
                                <div className="space-y-2">
                                    <span className="inline-block px-3 py-1 text-[10px] font-extrabold uppercase tracking-widest text-violet-700 bg-violet-50 border border-violet-100 rounded-full">
                                        {service.category_name}
                                    </span>
                                    <h1 className="text-3xl md:text-4xl font-black text-neutral-900 leading-tight">
                                        {service.title}
                                    </h1>
                                    {(service.address?.trim() || service.city?.trim()) && (
                                        <div className="flex items-center gap-1.5 text-sm font-semibold text-neutral-500 mt-2">
                                            <svg className="w-4 h-4 text-neutral-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                            </svg>
                                            <span>{service.address?.trim() || service.city?.trim()}</span>
                                        </div>
                                    )}
                                </div>
                                {!isOwner && (
                                    <div className="shrink-0 pt-1">
                                        <FavoriteButton
                                            contentType="service"
                                            objectId={service.id}
                                            initialIsFavorite={!!service.is_favorite}
                                        />
                                    </div>
                                )}
                            </div>
                            <p className="text-sm text-neutral-600 leading-relaxed whitespace-pre-wrap">
                                {service.description}
                            </p>
                        </Card>

                        {/* Additional Details Card */}
                        <Card className="p-6 md:p-8">
                            <h2 className="text-xl font-extrabold text-neutral-900 mb-4 flex items-center gap-2">
                                <svg className="w-5 h-5 text-violet-650" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                {t('details') || "Детали услуги"}
                            </h2>
                            <div className="prose max-w-none text-sm text-neutral-600 leading-relaxed whitespace-pre-wrap">
                                {service.description}
                            </div>
                        </Card>

                        {/* Q&A Section */}
                        <ServiceComments serviceId={service.id} providerId={providerId} />
                    </div>

                    {/* Sidebar Column */}
                    <div className="lg:col-span-1">
                        <div className="sticky top-24 bg-white rounded-3xl border border-neutral-150 p-6 shadow-xs space-y-6">
                            {/* Price block */}
                            <div>
                                <p className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-2">
                                    {t('price')}
                                </p>
                                <div className="text-3xl font-black text-neutral-900 flex items-baseline gap-1">
                                    <span>₸ {parseInt(service.price_amount).toLocaleString()}</span>
                                    <span className="text-xs font-normal text-neutral-500">
                                        /{service.price_type}
                                    </span>
                                </div>
                            </div>

                            {/* Provider Card Info */}
                            <div className="border-t border-neutral-100 pt-6">
                                <p className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-3">
                                    {t('provider')}
                                </p>
                                <div className="flex items-center justify-between gap-3 bg-neutral-50 border border-neutral-150 p-3.5 rounded-2xl">
                                    <Link 
                                        href={`/providers/${providerId}`} 
                                        className="flex items-center hover:opacity-85 transition-opacity min-w-0"
                                    >
                                        <div className="h-12 w-12 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center font-black text-lg border-2 border-white shadow-xs shrink-0 mr-3">
                                            {service.provider?.username?.[0]?.toUpperCase() || 'P'}
                                        </div>
                                        <div className="min-w-0">
                                            <p className="font-bold text-sm text-neutral-900 truncate">
                                                {service.provider?.username ?? tCommon('unknown')}
                                            </p>
                                            <div className="flex items-center text-xs text-neutral-500 mt-0.5">
                                                <svg className="h-3.5 w-3.5 text-amber-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                                </svg>
                                                <span>
                                                    {service.provider?.rating_avg ?? 0.0} ({service.provider?.reviews_count ?? 0})
                                                </span>
                                            </div>
                                        </div>
                                    </Link>
                                    {(!user || user?.provider_profile_id !== providerId) && (
                                        <FavoriteButton
                                            contentType="provider"
                                            objectId={providerId}
                                            initialIsFavorite={!!service.provider?.is_favorite}
                                            size="sm"
                                        />
                                    )}
                                </div>
                            </div>

                            {/* CTA Button */}
                            <button
                                onClick={handleContactClick}
                                className="w-full rounded-2xl bg-violet-600 hover:bg-violet-700 text-white font-bold py-3.5 text-sm transition-all duration-200 active:scale-95 shadow-md shadow-violet-100 hover:shadow-violet-200 hover:shadow-lg"
                            >
                                {ctaText}
                            </button>

                            {/* Report Button */}
                            {!isOwner && (
                                <div className="mt-4 flex justify-center border-t border-neutral-100 pt-4">
                                    <ReportButton
                                        contentType="service"
                                        objectId={service.id}
                                        variant="text"
                                        className="text-xs font-semibold text-neutral-400 hover:text-rose-600 transition"
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Contact Modal */}
            <ContactModal
                service={service}
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                locale={locale}
            />
        </>
    );
}
