// frontend/src/app/[locale]/(dashboard)/dashboard/favorites/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { api } from '@/lib/api';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { FavoriteItem } from '@/types/favorites';
import FavoriteButton from '@/components/features/favorites/FavoriteButton';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';

export default function FavoritesPage() {
    const locale = useLocale();
    const t = useTranslations('favorites');
    const tCommon = useTranslations('common');

    const [activeTab, setActiveTab] = useState<'services' | 'providers'>('services');
    
    const [services, setServices] = useState<FavoriteItem[]>([]);
    const [providers, setProviders] = useState<FavoriteItem[]>([]);
    
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchFavorites = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [servicesRes, providersRes] = await Promise.all([
                api.get<FavoriteItem[]>(ENDPOINTS.FAVORITES, { params: { type: 'service' } }),
                api.get<FavoriteItem[]>(ENDPOINTS.FAVORITES, { params: { type: 'provider' } }),
            ]);

            setServices(Array.isArray(servicesRes.data) ? servicesRes.data : []);
            setProviders(Array.isArray(providersRes.data) ? providersRes.data : []);
        } catch (err) {
            console.error('[FavoritesPage] Failed to fetch favorites:', err);
            setError(t('error'));
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchFavorites();
    }, []);

    const removeServiceLocally = (id: number) => {
        setServices((prev) => prev.filter((item) => item.id !== id));
    };

    const removeProviderLocally = (id: number) => {
        setProviders((prev) => prev.filter((item) => item.id !== id));
    };

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            <div className="bg-white p-6 border border-slate-200 rounded-2xl shadow-xs">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                    {t('title')}
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                    {activeTab === 'services' ? t('services') : t('providers')}
                </p>
            </div>

            {/* Premium Tab Navigation */}
            <div className="flex border-b border-slate-200 gap-6">
                <button
                    onClick={() => setActiveTab('services')}
                    className={`pb-4 text-sm font-semibold transition-all relative -mb-px ${
                        activeTab === 'services'
                            ? 'text-violet-600 border-b-2 border-violet-600'
                            : 'text-slate-400 hover:text-slate-800'
                    }`}
                >
                    {t('services')} ({services.length})
                </button>
                <button
                    onClick={() => setActiveTab('providers')}
                    className={`pb-4 text-sm font-semibold transition-all relative -mb-px ${
                        activeTab === 'providers'
                            ? 'text-violet-600 border-b-2 border-violet-600'
                            : 'text-slate-400 hover:text-slate-800'
                    }`}
                >
                    {t('providers')} ({providers.length})
                </button>
            </div>

            {/* Content States */}
            {isLoading ? (
                <div className="flex flex-col items-center justify-center py-20">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
                    <p className="text-slate-500 text-sm mt-2">{t('loading')}</p>
                </div>
            ) : error ? (
                <Card className="bg-red-50 border border-red-100 p-6 text-center max-w-md mx-auto rounded-2xl">
                    <p className="text-red-800 font-medium mb-4">{error}</p>
                    <Button onClick={fetchFavorites} variant="outline" size="sm">
                        {tCommon('retry')}
                    </Button>
                </Card>
            ) : activeTab === 'services' ? (
                services.length === 0 ? (
                    <EmptyState
                        title={t('emptyServices')}
                        description={locale === 'en' ? 'Explore catalog and add event services to your favorites.' : 'Перейдите в каталог и добавляйте услуги в избранное.'}
                        action={
                            <div className="mt-4">
                                <Link href={`/${locale}/catalog/`}>
                                    <Button>{t('add')}</Button>
                                </Link>
                            </div>
                        }
                    />
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {services.map((item) => {
                            if (!item.object_data) {
                                return (
                                    <Card
                                        key={item.id}
                                        className="bg-slate-50 flex items-center justify-between p-4 rounded-2xl border border-slate-200"
                                    >
                                        <span className="text-slate-400 italic text-sm">
                                            {t('unavailable')}
                                        </span>
                                        <FavoriteButton
                                            contentType="service"
                                            objectId={item.object_id}
                                            initialIsFavorite={true}
                                            onChange={(isFav) => {
                                                if (!isFav) removeServiceLocally(item.id);
                                            }}
                                        />
                                    </Card>
                                );
                            }

                            const service = item.object_data;
                            return (
                                <Card
                                    key={item.id}
                                    className="group relative flex flex-col justify-between p-6 border border-slate-200 rounded-2xl bg-white hover:border-violet-200 hover:shadow-md transition duration-200"
                                >
                                    <div>
                                        <div className="flex items-start justify-between gap-4 mb-3">
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-50 text-violet-700">
                                                {service.category_name}
                                            </span>
                                            <div className="z-10">
                                                <FavoriteButton
                                                    contentType="service"
                                                    objectId={item.object_id}
                                                    initialIsFavorite={true}
                                                    onChange={(isFav) => {
                                                        if (!isFav) removeServiceLocally(item.id);
                                                    }}
                                                />
                                            </div>
                                        </div>
                                        <h3 className="font-extrabold text-slate-900 line-clamp-1 mb-1 tracking-tight">
                                            {service.title}
                                        </h3>
                                        <p className="text-xs text-slate-500 flex items-center gap-1">
                                            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                            </svg>
                                            {service.city}
                                        </p>
                                    </div>

                                    <div className="flex items-center justify-between pt-4 border-t border-slate-100 mt-5">
                                        <div className="text-lg font-black text-violet-600">
                                            ₸ {service.price_amount ? parseInt(service.price_amount).toLocaleString() : 0}
                                            <span className="text-xs font-normal text-slate-500 ml-1">
                                                /{service.price_type}
                                            </span>
                                        </div>
                                        <Link
                                            href={`/${locale}/service/${service.id}/`}
                                            className="text-xs font-bold text-violet-600 hover:text-violet-700 transition flex items-center gap-0.5"
                                        >
                                            <span>{tCommon('viewDetails')}</span>
                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                                            </svg>
                                        </Link>
                                    </div>
                                </Card>
                            );
                        })}
                    </div>
                )
            ) : providers.length === 0 ? (
                <EmptyState
                    title={t('emptyProviders')}
                    description={locale === 'en' ? 'You have no favorite event providers yet.' : 'У вас пока нет избранных исполнителей.'}
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {providers.map((item) => {
                        if (!item.object_data) {
                            return (
                                <Card
                                    key={item.id}
                                    className="bg-slate-50 flex items-center justify-between p-4 rounded-2xl border border-slate-200"
                                >
                                    <span className="text-slate-400 italic text-sm">
                                        {t('unavailable')}
                                    </span>
                                    <FavoriteButton
                                        contentType="provider"
                                        objectId={item.object_id}
                                        initialIsFavorite={true}
                                        onChange={(isFav) => {
                                            if (!isFav) removeProviderLocally(item.id);
                                        }}
                                    />
                                </Card>
                            );
                        }

                        const provider = item.object_data;
                        return (
                            <Card
                                key={item.id}
                                className="group relative flex flex-col justify-between p-6 border border-slate-200 rounded-2xl bg-white hover:border-violet-200 hover:shadow-md transition duration-200"
                            >
                                <div className="flex items-start gap-4 mb-4 pr-8">
                                    <Link href={`/${locale}/providers/${item.object_id}/`} className="flex items-start gap-4 hover:opacity-90 transition flex-1 min-w-0">
                                        <div className="h-12 w-12 rounded-2xl bg-violet-50 flex items-center justify-center text-violet-600 font-extrabold text-lg shrink-0 shadow-sm border border-violet-100">
                                            {provider.username?.[0]?.toUpperCase() || 'P'}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h3 className="font-extrabold text-slate-900 truncate tracking-tight mb-1">
                                                {provider.username}
                                            </h3>
                                            <div className="flex items-center text-xs font-bold text-slate-600 bg-slate-50 border border-slate-100 rounded-lg px-2 py-0.5 w-fit">
                                                <svg
                                                    className="h-3.5 w-3.5 text-amber-400 mr-1 shrink-0"
                                                    fill="currentColor"
                                                    viewBox="0 0 20 20"
                                                >
                                                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                                </svg>
                                                <span>{provider.rating_avg ?? "0.0"} ({provider.reviews_count ?? 0})</span>
                                            </div>
                                        </div>
                                    </Link>
                                    <div className="absolute top-6 right-6 z-10">
                                        <FavoriteButton
                                            contentType="provider"
                                            objectId={item.object_id}
                                            initialIsFavorite={true}
                                            onChange={(isFav) => {
                                                if (!isFav) removeProviderLocally(item.id);
                                            }}
                                        />
                                    </div>
                                </div>
                                <div className="text-xs font-semibold text-slate-500 pt-4 border-t border-slate-100 flex items-center justify-between mt-auto">
                                    <span className="truncate mr-2 flex items-center gap-1">
                                        <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                        </svg>
                                        {provider.email}
                                    </span>
                                    {provider.city && (
                                        <span className="shrink-0 bg-slate-50 border border-slate-100 rounded px-1.5 py-0.5 text-[10px] uppercase font-bold tracking-wider">
                                            {provider.city}
                                        </span>
                                    )}
                                </div>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
