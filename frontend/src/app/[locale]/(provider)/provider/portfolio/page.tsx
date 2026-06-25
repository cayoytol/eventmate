'use client';

import { useState, useEffect } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { api } from '@/lib/api';
import { ENDPOINTS, portfolioItemUrl } from '@/lib/api/endpoints';
import { useAuthStore } from '@/store/useAuthStore';
import { PortfolioItem } from '@/types/portfolio';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { Modal } from '@/components/ui/Modal';

export default function ProviderPortfolioPage() {
    const locale = useLocale();
    const t = useTranslations('portfolio');
    const { user } = useAuthStore();

    const [items, setItems] = useState<PortfolioItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Custom dialog deletion states
    const [deleteItemId, setDeleteItemId] = useState<number | null>(null);

    const fetchPortfolio = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const { data } = await api.get(ENDPOINTS.PORTFOLIO_ITEMS);
            
            // Normalize response (could be array or paginated object)
            const list = Array.isArray(data) ? data : data.results ?? [];
            
            // Filter ownership
            const providerProfileId = user?.provider_profile_id;
            const ownItems = list.filter(
                (item: any) => item.provider_profile === providerProfileId
            );

            setItems(ownItems);
        } catch (err) {
            console.error('[ProviderPortfolioPage] Failed to fetch portfolio items:', err);
            setError(t('error'));
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (user) {
            fetchPortfolio();
        }
    }, [user]);

    const confirmDelete = async () => {
        if (deleteItemId === null) return;
        
        const id = deleteItemId;
        setDeleteItemId(null); // Close modal immediately
        
        const previousItems = [...items];
        // Optimistic UI update
        setItems(prev => prev.filter(item => item.id !== id));

        try {
            await api.delete(portfolioItemUrl(id));
        } catch (err) {
            console.error('[ProviderPortfolioPage] Failed to delete portfolio item:', err);
            // Rollback on error
            setItems(previousItems);
        }
    };

    const isDirectVideoUrl = (url: string) => {
        if (!url) return false;
        const cleanUrl = url.split('?')[0].toLowerCase();
        return cleanUrl.endsWith('.mp4') || cleanUrl.endsWith('.webm') || cleanUrl.endsWith('.ogg');
    };

    const isDirectImageUrl = (url: string) => {
        if (!url) return false;
        const cleanUrl = url.split('?')[0].toLowerCase();
        return cleanUrl.endsWith('.jpg') || cleanUrl.endsWith('.jpeg') || cleanUrl.endsWith('.png') || cleanUrl.endsWith('.gif') || cleanUrl.endsWith('.webp') || cleanUrl.endsWith('.svg');
    };

    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleDateString(locale === 'kz' ? 'kk-KZ' : locale === 'en' ? 'en-US' : 'ru-RU');
        } catch {
            return dateStr;
        }
    };

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            {/* PageHeader section */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-6 border border-slate-200 rounded-2xl shadow-sm">
                <div className="space-y-1">
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        {t('title')}
                    </h1>
                    <p className="text-sm text-slate-500">
                        {t('subtitle')}
                    </p>
                </div>
                <Link href={`/${locale}/provider/portfolio/new/`}>
                    <Button className="font-bold rounded-xl shadow-md shadow-violet-100 flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                        </svg>
                        <span>{t('create')}</span>
                    </Button>
                </Link>
            </div>

            {error && (
                <div className="rounded-2xl bg-red-50 border border-red-100 text-red-700 p-4 text-sm font-medium flex justify-between items-center">
                    <span>{error}</span>
                    <Button variant="outline" size="sm" onClick={fetchPortfolio} className="border-red-200 text-red-700 hover:bg-red-100/30">
                        Retry
                    </Button>
                </div>
            )}

            {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <Skeleton className="h-80 w-full rounded-2xl" />
                    <Skeleton className="h-80 w-full rounded-2xl" />
                    <Skeleton className="h-80 w-full rounded-2xl" />
                </div>
            ) : items.length === 0 ? (
                <EmptyState
                    title={t('emptyTitle')}
                    description={t('emptyDescription')}
                    action={
                        <div className="mt-4">
                            <Link href={`/${locale}/provider/portfolio/new/`}>
                                <Button>{t('create')}</Button>
                            </Link>
                        </div>
                    }
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {items.map((item) => {
                        const coverUrl = item.cover_url || (item.media && item.media.length > 0 ? item.media[0].resolved_url || item.media[0].file_url : null);
                        const firstMedia = item.media && item.media.length > 0 ? item.media[0] : null;

                        return (
                            <Card
                                key={item.id}
                                className="group relative flex flex-col justify-between p-0 overflow-hidden border border-slate-200 rounded-2xl bg-white hover:border-violet-200 hover:shadow-md transition duration-200"
                                hoverable
                            >
                                <div className="flex flex-col">
                                    {/* Media Preview or Fallback */}
                                    <div className="aspect-[16/10] w-full bg-slate-50 relative overflow-hidden border-b border-slate-100 flex items-center justify-center text-slate-400">
                                        {coverUrl ? (
                                            (() => {
                                                const isVideo = firstMedia && firstMedia.media_type === 'video';
                                                return isVideo ? (
                                                    <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
                                                        <video
                                                            src={coverUrl}
                                                            className="h-full w-full object-cover opacity-80"
                                                            muted
                                                            playsInline
                                                        />
                                                        <div className="absolute w-10 h-10 rounded-full bg-white/30 backdrop-blur flex items-center justify-center text-white">
                                                            <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
                                                                <path d="M8 5v14l11-7z" />
                                                            </svg>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <img
                                                        src={coverUrl}
                                                        alt={item.title}
                                                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                                                        onError={(e) => {
                                                            // Hide image and show fallback element on error safely
                                                            const imgElem = e.target as HTMLElement;
                                                            imgElem.style.display = 'none';
                                                            const fallbackElem = imgElem.nextSibling as HTMLElement;
                                                            if (fallbackElem) {
                                                                fallbackElem.style.display = 'flex';
                                                            }
                                                        }}
                                                    />
                                                );
                                            })()
                                        ) : null}

                                        {/* Premium Placeholder Fallback on Error or Absent Image */}
                                        <div
                                            style={{ display: coverUrl ? 'none' : 'flex' }}
                                            className="absolute inset-0 bg-gradient-to-tr from-violet-600 via-indigo-600 to-fuchsia-600 text-white flex flex-col items-center justify-center p-4 text-center select-none overflow-hidden"
                                        >
                                            <div className="absolute -bottom-8 -right-8 w-24 h-24 rounded-full bg-white/5 border border-white/10 pointer-events-none" />
                                            <div className="absolute -top-8 -left-8 w-20 h-20 rounded-full bg-white/5 pointer-events-none" />
                                            
                                            <span className="text-3xl font-black opacity-25 mb-1 tracking-wider uppercase select-none">
                                                {item.title ? item.title.slice(0, 2).toUpperCase() : 'PT'}
                                            </span>
                                            <span className="text-[10px] font-black uppercase tracking-widest text-violet-100/95 max-w-full truncate px-2 select-none">
                                                {item.title || 'Portfolio'}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Content info */}
                                    <div className="p-5 space-y-2">
                                        <div className="flex justify-between items-baseline gap-2">
                                            <h3 className="text-lg font-bold text-slate-900 line-clamp-1 group-hover:text-violet-600 transition duration-150">
                                                {item.title}
                                            </h3>
                                        </div>
                                        <p className="text-slate-500 text-sm line-clamp-3 leading-relaxed">
                                            {item.description || 'No description provided.'}
                                        </p>
                                        <span className="block text-[11px] text-slate-400 font-semibold uppercase tracking-wider pt-2">
                                            {formatDate(item.created_at)}
                                        </span>
                                    </div>
                                </div>

                                {/* Actions row */}
                                <div className="px-5 pb-5 pt-3 border-t border-slate-100/60 flex items-center justify-between gap-4">
                                    <Link
                                        href={`/${locale}/provider/portfolio/${item.id}/`}
                                        className="flex-1"
                                    >
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full font-bold rounded-xl"
                                        >
                                            {t('edit')}
                                        </Button>
                                    </Link>
                                    <Button
                                        onClick={() => setDeleteItemId(item.id)}
                                        variant="ghost"
                                        size="sm"
                                        className="inline-flex items-center justify-center p-2 text-rose-500 hover:text-rose-600 hover:bg-rose-50/50 rounded-xl transition"
                                        title={t('delete')}
                                    >
                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </Button>
                                </div>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Custom confirmation dialog replacing browser native confirm() */}
            <Modal
                isOpen={deleteItemId !== null}
                onClose={() => setDeleteItemId(null)}
                title={t('delete')}
            >
                <div className="space-y-6 pt-2">
                    <p className="text-sm text-slate-600 leading-relaxed">
                        {t('deleteConfirm')}
                    </p>
                    <div className="flex items-center justify-end gap-3">
                        <Button
                            variant="outline"
                            onClick={() => setDeleteItemId(null)}
                            className="rounded-xl font-bold"
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={confirmDelete}
                            className="bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-bold"
                        >
                            {t('delete')}
                        </Button>
                    </div>
                </div>
            </Modal>
        </div>
    );
}
