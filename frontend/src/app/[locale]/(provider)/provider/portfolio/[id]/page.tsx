'use client';

import { useState, useEffect, use, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { api } from '@/lib/api';
import {
    portfolioItemUrl,
    portfolioItemMediaAddUrl,
    portfolioMediaDeleteUrl
} from '@/lib/api/endpoints';
import { deletePortfolioMedia } from '@/lib/api/portfolio';
import { useAuthStore } from '@/store/useAuthStore';
import { PortfolioItem, PortfolioMedia } from '@/types/portfolio';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';
import { PortfolioImageUploader } from '@/components/portfolio/PortfolioImageUploader';

interface EditPageProps {
    params: Promise<{
        id: string;
        locale: string;
    }>;
}

export default function PortfolioEditPage({ params }: EditPageProps) {
    const { id: itemIdStr } = use(params);
    const itemId = parseInt(itemIdStr);
    
    const locale = useLocale();
    const router = useRouter();
    const t = useTranslations('portfolio');
    const { user } = useAuthStore();

    const [item, setItem] = useState<PortfolioItem | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [saveSuccess, setSaveSuccess] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);

    // Edit form states
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');

    // Add media states
    const [mediaUrl, setMediaUrl] = useState('');
    const [mediaType, setMediaType] = useState<'image' | 'video'>('image');
    const [isAddingMedia, setIsAddingMedia] = useState(false);
    const [mediaError, setMediaError] = useState<string | null>(null);

    // Modal states for dialog replacement
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [mediaToDeleteId, setMediaToDeleteId] = useState<number | null>(null);

    // Tab/source states for media upload/url choice
    const [sourceMode, setSourceMode] = useState<'upload' | 'url'>('upload');
    const [pendingSourceMode, setPendingSourceMode] = useState<'upload' | 'url' | null>(null);
    const [mediaToReplaceId, setMediaToReplaceId] = useState<number | null>(null);

    const providerProfileId = user?.provider_profile_id;

    const fetchItem = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const { data } = await api.get<PortfolioItem>(portfolioItemUrl(itemId));
            
            // Ownership check
            if (data.provider_profile !== providerProfileId) {
                setError(t('notAllowed'));
                setIsLoading(false);
                return;
            }

            setItem(data);
            setTitle(data.title);
            setDescription(data.description || '');
        } catch (err) {
            console.error('[PortfolioEditPage] Failed to fetch portfolio item:', err);
            setError(t('error'));
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (user && providerProfileId && itemId) {
            fetchItem();
        }
    }, [user, providerProfileId, itemId]);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaveError(null);
        setSaveSuccess(false);

        const cleanTitle = title.trim();
        if (!cleanTitle) {
            setSaveError('Title cannot be empty');
            return;
        }

        setIsSaving(true);
        try {
            const { data } = await api.patch<PortfolioItem>(portfolioItemUrl(itemId), {
                title: cleanTitle,
                description: description.trim(),
            });
            setItem(data);
            setSaveSuccess(true);
        } catch (err) {
            console.error('[PortfolioEditPage] Failed to update portfolio item:', err);
            setSaveError(t('error'));
        } finally {
            setIsSaving(false);
        }
    };

    const confirmDeleteItem = async () => {
        setIsDeleteModalOpen(false);
        setIsSaving(true);
        try {
            await api.delete(portfolioItemUrl(itemId));
            router.push(`/${locale}/provider/portfolio/`);
        } catch (err) {
            console.error('[PortfolioEditPage] Failed to delete portfolio item:', err);
            setError(t('error'));
            setIsSaving(false);
        }
    };

    const handleAddMedia = async (e: React.FormEvent) => {
        e.preventDefault();
        setMediaError(null);

        const cleanUrl = mediaUrl.trim();
        if (!cleanUrl) {
            setMediaError(t('mediaUrl') + ' is required');
            return;
        }

        setIsAddingMedia(true);
        try {
            const { data } = await api.post<PortfolioMedia>(
                portfolioItemMediaAddUrl(itemId),
                {
                    file_url: cleanUrl,
                    media_type: mediaType,
                }
            );

            // Update local state with new media
            if (item) {
                setItem({
                    ...item,
                    media: [...(item.media || []), data],
                });
            }
            setMediaUrl('');
        } catch (err: any) {
            console.error('[PortfolioEditPage] Failed to add media:', err);
            
            // Check for backend limit errors (e.g. max 10 items)
            if (err.response?.data?.detail) {
                setMediaError(err.response.data.detail);
            } else {
                setMediaError(t('error'));
            }
        } finally {
            setIsAddingMedia(false);
        }
    };

    const confirmDeleteMedia = async () => {
        if (mediaToDeleteId === null) return;
        const mediaId = mediaToDeleteId;
        setMediaToDeleteId(null); // Close modal

        // Keep a copy of previous media for rollback
        const previousMedia = item?.media ? [...item.media] : [];

        // Optimistically remove media from local state
        if (item) {
            setItem({
                ...item,
                media: (item.media || []).filter(m => m.id !== mediaId),
            });
        }

        try {
            await deletePortfolioMedia(mediaId);
        } catch (err) {
            console.error('[PortfolioEditPage] Failed to delete media:', err);
            // Rollback on error
            if (item) {
                setItem({
                    ...item,
                    media: previousMedia,
                });
            }
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

    const handleTabChange = (mode: 'upload' | 'url') => {
        if (mode === sourceMode) return;
        if (sourceMode === 'url' && mediaUrl.trim() !== '') {
            setPendingSourceMode(mode);
        } else {
            setSourceMode(mode);
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto space-y-6 px-4">
                <Skeleton className="h-12 w-1/4 rounded-xl" />
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="lg:col-span-2 space-y-8">
                        <Skeleton className="h-80 w-full rounded-2xl" />
                        <Skeleton className="h-60 w-full rounded-2xl" />
                    </div>
                    <Skeleton className="h-40 w-full rounded-2xl" />
                </div>
            </div>
        );
    }

    if (error || !item) {
        return (
            <div className="max-w-md mx-auto my-8">
                <Card className="border border-rose-200 bg-rose-50/50 p-6 text-center shadow-sm">
                    <h3 className="text-lg font-bold text-rose-800 mb-2">Error occurred</h3>
                    <p className="text-rose-700 text-sm mb-6">{error || 'Could not find the portfolio item.'}</p>
                    <Button
                        onClick={() => router.push(`/${locale}/provider/portfolio/`)}
                        className="bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl"
                    >
                        Back to Portfolio
                    </Button>
                </Card>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto space-y-6 px-4">
            {/* PageHeader style block */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-6 border border-slate-200 rounded-2xl shadow-sm">
                <div className="space-y-1">
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        {t('edit')}
                    </h1>
                    <p className="text-sm text-slate-500">
                        {locale === 'en' ? 'Manage project information and add media URL links.' : 'Управляйте деталями проекта и прикрепляйте ссылки на медиафайлы.'}
                    </p>
                </div>
                <Button
                    variant="outline"
                    onClick={() => router.push(`/${locale}/provider/portfolio/`)}
                    className="font-bold rounded-xl"
                >
                    Back to Portfolio
                </Button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                {/* Left Column: Form & Media Manager */}
                <div className="lg:col-span-2 space-y-8">
                    {/* Project Edit Form */}
                    <Card className="border border-slate-200 bg-white p-6 sm:p-8">
                        <form onSubmit={handleSave} className="space-y-6">
                            {saveSuccess && (
                                <div className="p-4 bg-emerald-50 text-emerald-800 text-sm rounded-xl border border-emerald-100 font-medium">
                                    {t('updated') || 'Portfolio item updated successfully!'}
                                </div>
                            )}
                            {saveError && (
                                <div className="p-4 bg-rose-50 text-rose-800 text-sm rounded-xl border border-rose-100 font-medium">
                                    {saveError}
                                </div>
                            )}
                            <div className="space-y-4">
                                <Input
                                    label="Title"
                                    id="title"
                                    type="text"
                                    required
                                    value={title}
                                    onChange={(e) => setTitle(e.target.value)}
                                    className="w-full"
                                />

                                <Textarea
                                    label="Description"
                                    id="description"
                                    rows={5}
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    className="w-full"
                                />
                            </div>

                            <div className="flex items-center justify-end pt-4 border-t border-slate-100">
                                <Button
                                    type="submit"
                                    disabled={isSaving}
                                    isLoading={isSaving}
                                    className="font-bold rounded-xl shadow-sm shadow-violet-100 min-w-[100px]"
                                >
                                    {t('save')}
                                </Button>
                            </div>
                        </form>
                    </Card>

                    {/* Media Manager Section */}
                    <Card className="border border-slate-200 bg-white p-6 sm:p-8 space-y-6">
                        <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">{t('media')}</h2>

                        {/* Add media source selection tabs */}
                        <div className="flex border-b border-slate-150 mb-6">
                            <button
                                type="button"
                                onClick={() => handleTabChange('upload')}
                                className={`px-4 py-2.5 text-sm font-bold border-b-2 transition-all ${
                                    sourceMode === 'upload'
                                        ? 'border-violet-600 text-violet-600'
                                        : 'border-transparent text-slate-500 hover:text-slate-700'
                                }`}
                            >
                                {t('media.uploadImage')}
                            </button>
                            <button
                                type="button"
                                onClick={() => handleTabChange('url')}
                                className={`px-4 py-2.5 text-sm font-bold border-b-2 transition-all ${
                                    sourceMode === 'url'
                                        ? 'border-violet-600 text-violet-600'
                                        : 'border-transparent text-slate-500 hover:text-slate-700'
                                }`}
                            >
                                {t('media.sourceExternalUrl')}
                            </button>
                        </div>

                        {sourceMode === 'upload' ? (
                            <div className="p-4 bg-slate-50 border border-slate-150 rounded-xl">
                                <PortfolioImageUploader
                                    itemId={itemId}
                                    onUploadSuccess={(newMedia) => {
                                        if (item) {
                                            setItem({
                                                ...item,
                                                media: [...(item.media || []), newMedia],
                                            });
                                        }
                                    }}
                                />
                            </div>
                        ) : (
                            <div className="p-4 bg-slate-50 border border-slate-150 rounded-xl space-y-4">
                                <div className="space-y-1">
                                    <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">{t('addMediaByUrl')}</h3>
                                    <p className="text-[11px] text-slate-500 leading-normal">{t('mediaUrlHelp')}</p>
                                </div>

                                <form onSubmit={handleAddMedia} className="space-y-4">
                                    {mediaError && (
                                        <div className="p-3 bg-rose-50 text-rose-800 text-xs rounded-lg border border-rose-100 font-medium">
                                            {mediaError}
                                        </div>
                                    )}

                                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                        <div className="sm:col-span-2">
                                            <Input
                                                id="mediaUrl"
                                                type="url"
                                                required
                                                value={mediaUrl}
                                                onChange={(e) => setMediaUrl(e.target.value)}
                                                placeholder={t('mediaUrlPlaceholder')}
                                                className="w-full bg-white"
                                            />
                                        </div>

                                        <div>
                                            <select
                                                id="mediaType"
                                                value={mediaType}
                                                onChange={(e) => setMediaType(e.target.value as any)}
                                                className="w-full px-3 py-2.5 border border-slate-200 hover:border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-600 text-slate-800 bg-white h-[42px] transition-all"
                                            >
                                                <option value="image">{t('image')}</option>
                                                <option value="video">{t('video')}</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div className="flex justify-end pt-2">
                                        <Button
                                            type="submit"
                                            disabled={isAddingMedia}
                                            isLoading={isAddingMedia}
                                            className="font-bold rounded-xl shadow-xs"
                                        >
                                            {t('addMedia')}
                                        </Button>
                                    </div>
                                </form>
                            </div>
                        )}

                        {/* Media Gallery Grid */}
                        <div className="space-y-3">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">{t('mediaGallery')}</h3>
                            {item.media && item.media.length > 0 ? (
                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                                    {item.media.map((media) => {
                                        const displayUrl = media.resolved_url || media.file_url || '';
                                        return (
                                            <div
                                                key={media.id}
                                                className="group relative aspect-square bg-slate-50 rounded-xl overflow-hidden border border-slate-200 flex items-center justify-center"
                                            >
                                                {isDirectVideoUrl(displayUrl) ? (
                                                    <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
                                                        <video src={displayUrl} className="h-full w-full object-cover opacity-85" muted />
                                                        <div className="absolute w-8 h-8 rounded-full bg-white/20 backdrop-blur flex items-center justify-center text-white">
                                                            <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                                                                <path d="M8 5v14l11-7z" />
                                                            </svg>
                                                        </div>
                                                    </div>
                                                ) : isDirectImageUrl(displayUrl) ? (
                                                    <img
                                                        src={displayUrl}
                                                        alt=""
                                                        className="h-full w-full object-cover"
                                                        onError={(e) => {
                                                            (e.target as HTMLElement).style.display = 'none';
                                                            const sib = (e.target as HTMLElement).nextSibling as HTMLElement;
                                                            if (sib) sib.style.display = 'flex';
                                                        }}
                                                    />
                                                ) : (
                                                    /* YouTube/Vimeo/Unknown Video Links Placeholder */
                                                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/5 p-3 text-center">
                                                        <div className="p-2 bg-white rounded-lg border border-slate-100 text-violet-600 mb-1.5 shadow-3xs">
                                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                                            </svg>
                                                        </div>
                                                        <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider truncate max-w-full">{media.media_type}</span>
                                                        <span className="text-[8px] text-slate-400 mt-0.5 truncate max-w-full">{displayUrl}</span>
                                                    </div>
                                                )}

                                                {/* Image error fallback placeholder inside media manager */}
                                                <div
                                                    style={{ display: 'none' }}
                                                    className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-slate-50 text-slate-400"
                                                >
                                                    <svg className="w-6 h-6 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                    </svg>
                                                    <span className="text-[10px] text-slate-400 font-medium">Broken link</span>
                                                </div>
                                                
                                                {/* Overlay hover replace & delete actions */}
                                                <div className="absolute inset-0 bg-slate-900/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3.5 z-10">
                                                    <Button
                                                        onClick={() => setMediaToReplaceId(media.id)}
                                                        variant="ghost"
                                                        size="sm"
                                                        className="p-2.5 bg-violet-600 hover:bg-violet-700 text-white rounded-full transition active:scale-95"
                                                        title={t('media.replaceImage')}
                                                    >
                                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                                        </svg>
                                                    </Button>
                                                    <Button
                                                        onClick={() => setMediaToDeleteId(media.id)}
                                                        variant="ghost"
                                                        size="sm"
                                                        className="p-2.5 bg-rose-600 hover:bg-rose-700 text-white rounded-full transition active:scale-95"
                                                        title={t('deleteMedia')}
                                                    >
                                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                        </svg>
                                                    </Button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <div className="text-center py-8 border border-dashed border-slate-200 rounded-xl text-slate-400">
                                    <span className="text-sm font-medium">No media uploaded yet.</span>
                                </div>
                            )}
                        </div>
                    </Card>

                    {/* Danger Zone */}
                    <Card className="border border-rose-200 bg-rose-50/25 p-6 sm:p-8 space-y-4">
                        <div className="space-y-1">
                            <h3 className="text-base font-extrabold text-rose-800 tracking-tight">{t('dangerZone')}</h3>
                            <p className="text-xs text-rose-700/80 leading-normal">
                                {locale === 'en' ? 'Deleting this project will permanently remove it and all of its associated media items.' : 'Удаление этого проекта навсегда сотрет его данные и связанные ссылки на медиафайлы.'}
                            </p>
                        </div>
                        <div className="flex justify-start">
                            <Button
                                onClick={() => setIsDeleteModalOpen(true)}
                                className="bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-xl"
                            >
                                {t('delete')}
                            </Button>
                        </div>
                    </Card>
                </div>

                {/* Right Column: Metadata Sidebar Card */}
                <div className="space-y-6">
                    <Card className="border border-slate-200 bg-white p-6 shadow-xs">
                        <h3 className="font-extrabold text-slate-900 text-base mb-4">Item Details</h3>
                        <div className="space-y-3.5 text-sm">
                            <div className="flex justify-between py-2 border-b border-slate-100">
                                <span className="text-slate-500">Created:</span>
                                <span className="text-slate-800 font-bold">
                                    {new Date(item.created_at).toLocaleDateString()}
                                </span>
                            </div>
                            <div className="flex justify-between py-2 border-b border-slate-100">
                                <span className="text-slate-500">Media Count:</span>
                                <span className="text-slate-800 font-bold">
                                    {item.media?.length || 0} / 10
                                </span>
                            </div>
                        </div>
                    </Card>

                    {/* Advisory card for URL inputs */}
                    <Card className="border border-amber-200 bg-amber-50/45 p-6 space-y-3">
                        <h4 className="font-bold text-slate-900 text-sm">{t('uploadFutureNote')}</h4>
                        <p className="text-xs text-slate-600 leading-relaxed">
                            {t('mediaUrlHelp')}
                        </p>
                    </Card>
                </div>
            </div>

            {/* Custom confirmation dialog replacing browser native confirm() for deleting the item */}
            <Modal
                isOpen={isDeleteModalOpen}
                onClose={() => setIsDeleteModalOpen(false)}
                title={t('delete')}
            >
                <div className="space-y-6 pt-2">
                    <p className="text-sm text-slate-600 leading-relaxed">
                        {t('deleteConfirm')}
                    </p>
                    <div className="flex items-center justify-end gap-3">
                        <Button
                            variant="outline"
                            onClick={() => setIsDeleteModalOpen(false)}
                            className="rounded-xl font-bold"
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={confirmDeleteItem}
                            className="bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-bold"
                        >
                            {t('delete')}
                        </Button>
                    </div>
                </div>
            </Modal>

            {/* Custom confirmation dialog replacing browser native confirm() for deleting media */}
            <Modal
                isOpen={mediaToDeleteId !== null}
                onClose={() => setMediaToDeleteId(null)}
                title={t('deleteMedia')}
            >
                <div className="space-y-6 pt-2">
                    <p className="text-sm text-slate-600 leading-relaxed">
                        {t('deleteMediaConfirm')}
                    </p>
                    <div className="flex items-center justify-end gap-3">
                        <Button
                            variant="outline"
                            onClick={() => setMediaToDeleteId(null)}
                            className="rounded-xl font-bold"
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={confirmDeleteMedia}
                            className="bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-bold"
                        >
                            {t('delete')}
                        </Button>
                    </div>
                </div>
            </Modal>

            {/* Custom confirmation modal for switching media source tabs */}
            <Modal
                isOpen={pendingSourceMode !== null}
                onClose={() => setPendingSourceMode(null)}
                title={t('media.switchSourceConfirmTitle')}
            >
                <div className="space-y-6 pt-2">
                    <p className="text-sm text-slate-600 leading-relaxed">
                        {t('media.switchSourceConfirmDescription')}
                    </p>
                    <div className="flex items-center justify-end gap-3">
                        <Button
                            variant="outline"
                            onClick={() => setPendingSourceMode(null)}
                            className="rounded-xl font-bold"
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={() => {
                                if (pendingSourceMode) {
                                    setSourceMode(pendingSourceMode);
                                    setMediaUrl('');
                                    setPendingSourceMode(null);
                                }
                            }}
                            className="bg-violet-600 hover:bg-violet-700 text-white rounded-xl font-bold"
                        >
                            Continue
                        </Button>
                    </div>
                </div>
            </Modal>

            {/* Custom replace media modal */}
            <Modal
                isOpen={mediaToReplaceId !== null}
                onClose={() => setMediaToReplaceId(null)}
                title={t('media.replaceImage')}
            >
                <div className="pt-2">
                    {mediaToReplaceId !== null && (
                        <PortfolioImageUploader
                            mediaId={mediaToReplaceId}
                            onUploadSuccess={(updatedMedia) => {
                                if (item) {
                                    setItem({
                                        ...item,
                                        media: (item.media || []).map((m) =>
                                            m.id === mediaToReplaceId ? updatedMedia : m
                                        ),
                                    });
                                }
                                setMediaToReplaceId(null);
                            }}
                            onCancel={() => setMediaToReplaceId(null)}
                        />
                    )}
                </div>
            </Modal>
        </div>
    );
}
