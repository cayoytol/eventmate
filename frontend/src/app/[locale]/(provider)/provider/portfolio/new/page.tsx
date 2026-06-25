'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { api } from '@/lib/api';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';

export default function PortfolioNewPage() {
    const locale = useLocale();
    const router = useRouter();
    const t = useTranslations('portfolio');

    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);

    // Selected image/file states
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [createdItemId, setCreatedItemId] = useState<number | null>(null);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [isUploading, setIsUploading] = useState(false);

    // Clean up local preview URL object on unmount to prevent memory leaks
    useEffect(() => {
        return () => {
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }
        };
    }, [previewUrl]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];

            // Client side validation matching PortfolioImageUploader limits
            const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
            if (!allowedTypes.includes(file.type)) {
                setFormError(t('media.invalidType'));
                return;
            }

            const maxSize = 5 * 1024 * 1024; // 5 MB
            if (file.size > maxSize) {
                setFormError(t('media.fileTooLarge'));
                return;
            }

            setSelectedFile(file);
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }
            setPreviewUrl(URL.createObjectURL(file));
            setFormError(null);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setFormError(null);

        const cleanTitle = title.trim();
        if (!cleanTitle) {
            setFormError('Title cannot be empty');
            return;
        }

        setIsSubmitting(true);
        let itemId = createdItemId;

        try {
            // Step 1: Create PortfolioItem metadata first if not already created
            if (!itemId) {
                const { data } = await api.post(ENDPOINTS.PORTFOLIO_ITEMS, {
                    title: cleanTitle,
                    description: description.trim() || '',
                });
                itemId = data.id;
                setCreatedItemId(itemId);
            }

            // Step 2: Upload selected file using the newly retrieved project ID
            if (selectedFile && itemId) {
                setIsUploading(true);
                const formData = new FormData();
                formData.append('file', selectedFile);

                const { uploadPortfolioMedia } = await import('@/lib/api/portfolio');
                await uploadPortfolioMedia(
                    itemId,
                    formData,
                    (progressEvent) => {
                        if (progressEvent.total) {
                            setUploadProgress(
                                Math.round((progressEvent.loaded * 100) / progressEvent.total)
                            );
                        }
                    }
                );
            }

            // Redirect to list on complete success
            router.push(`/${locale}/provider/portfolio/`);
        } catch (err: any) {
            console.error('[PortfolioNewPage] Submit failed:', err);
            const detail = err.response?.data?.detail;
            
            if (itemId) {
                // Meta created successfully, but file upload failed
                if (typeof detail === 'object') {
                    setFormError(t('media.uploadFailed') + ': ' + JSON.stringify(detail));
                } else if (detail) {
                    setFormError(t('media.uploadFailed') + ': ' + detail);
                } else {
                    setFormError(t('media.uploadFailed') + ' - You can retry here or upload later from the edit page.');
                }
            } else {
                setFormError(t('error'));
            }
        } finally {
            setIsSubmitting(false);
            setIsUploading(false);
        }
    };

    return (
        <div className="max-w-xl mx-auto space-y-6 px-4">
            <Card className="border border-slate-200 bg-white p-6 sm:p-8">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-slate-900 mb-1">
                        {t('create')}
                    </h1>
                    <p className="text-slate-500 text-sm">
                        {locale === 'en'
                            ? 'Create a project to showcase your events and services.'
                            : locale === 'kz'
                            ? 'Іс-шараларыңыз бен қызметтеріңізді көрсету үшін жаңа жоба жасаңыз.'
                            : 'Создайте проект, чтобы продемонстрировать свои мероприятия и услуги.'}
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    {formError && (
                        <div className="p-4 bg-rose-50 text-rose-800 text-sm rounded-xl border border-rose-100 font-medium">
                            {formError}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl space-y-2">
                            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                {t('projectBasics')}
                            </h3>
                            <Input
                                id="title"
                                type="text"
                                required
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder="e.g., Wedding Decor in Almaty"
                                className="w-full"
                                disabled={isSubmitting || isUploading}
                            />
                        </div>

                        <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl space-y-2">
                            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                {t('description')}
                            </h3>
                            <Textarea
                                id="description"
                                rows={5}
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Describe the project, your role, and the results achieved..."
                                className="w-full"
                                disabled={isSubmitting || isUploading}
                            />
                        </div>

                        {/* Device Image Selector */}
                        <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl space-y-4">
                            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                {t('media.uploadImage')}
                            </h3>
                            {!previewUrl ? (
                                <div
                                    className="border-2 border-dashed border-slate-200 rounded-xl p-6 flex flex-col items-center justify-center text-center bg-white cursor-pointer hover:bg-slate-50/50 transition-colors"
                                    onClick={() => document.getElementById('image-select-input')?.click()}
                                >
                                    <input
                                        id="image-select-input"
                                        type="file"
                                        onChange={handleFileChange}
                                        accept="image/jpeg,image/png,image/webp"
                                        className="hidden"
                                        disabled={isSubmitting || isUploading}
                                    />
                                    <svg className="w-8 h-8 text-slate-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                    <span className="text-xs font-bold text-slate-600">{t('media.chooseFile')}</span>
                                    <div className="mt-2 text-[10px] text-slate-400 font-semibold tracking-wider uppercase flex flex-col gap-0.5">
                                        <span>{t('media.supportedFormats')}</span>
                                        <span>{t('media.maxFileSize')}</span>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    <div className="aspect-[16/10] w-full bg-slate-200 rounded-xl overflow-hidden relative border border-slate-150">
                                        <img src={previewUrl} className="h-full w-full object-cover" alt="Preview" />
                                        {isUploading && (
                                            <div className="absolute inset-0 bg-slate-900/60 flex flex-col items-center justify-center text-white p-4">
                                                <div className="w-full max-w-[200px] bg-white/20 h-2 rounded-full overflow-hidden mb-3">
                                                    <div
                                                        style={{ width: `${uploadProgress}%` }}
                                                        className="bg-violet-500 h-full rounded-full transition-all duration-300"
                                                    />
                                                </div>
                                                <span className="text-xs font-bold uppercase tracking-wider">
                                                    {t('media.uploadProgress', { percent: uploadProgress })}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-slate-500 font-medium truncate max-w-[200px]">{selectedFile?.name}</span>
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => {
                                                setSelectedFile(null);
                                                setPreviewUrl(null);
                                            }}
                                            disabled={isSubmitting || isUploading}
                                            className="text-rose-600 hover:bg-rose-50/50 hover:text-rose-700 rounded-xl"
                                        >
                                            {t('media.removeImage')}
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Advisory info banner */}
                        <div className="p-4 bg-amber-50/50 border border-amber-100 rounded-xl flex items-start gap-3 text-amber-800">
                            <svg className="w-5 h-5 shrink-0 text-amber-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <div className="space-y-1">
                                <p className="text-xs font-bold leading-normal">
                                    {t('addMediaByUrl')}
                                </p>
                                <p className="text-[11px] text-slate-600 leading-relaxed">
                                    {t('mediaUrlHelp')}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center justify-end gap-4 pt-4 border-t border-slate-100">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => router.push(`/${locale}/provider/portfolio/`)}
                            className="font-bold rounded-xl"
                            disabled={isSubmitting || isUploading}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={isSubmitting || isUploading}
                            isLoading={isSubmitting || isUploading}
                            className="font-bold rounded-xl shadow-sm shadow-violet-100 min-w-[100px]"
                        >
                            {selectedFile && createdItemId ? t('media.retryUpload') : t('save')}
                        </Button>
                    </div>
                </form>
            </Card>
        </div>
    );
}
