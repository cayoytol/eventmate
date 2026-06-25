'use client';

import { useState, useRef, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/Button';
import { uploadPortfolioMedia, replacePortfolioMedia } from '@/lib/api/portfolio';

interface PortfolioImageUploaderProps {
    itemId?: number;
    mediaId?: number;
    onUploadSuccess: (media: any) => void;
    onCancel?: () => void;
}

export function PortfolioImageUploader({
    itemId,
    mediaId,
    onUploadSuccess,
    onCancel,
}: PortfolioImageUploaderProps) {
    const t = useTranslations('portfolio');
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [isDragActive, setIsDragActive] = useState(false);

    const fileInputRef = useRef<HTMLInputElement>(null);

    // Clean up local object URL previews to prevent memory leaks
    useEffect(() => {
        return () => {
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }
        };
    }, [previewUrl]);

    const handleFileChange = (file: File) => {
        setError(null);
        setProgress(0);

        // Client side validation
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            setError(t('media.invalidType'));
            return;
        }

        const maxSize = 5 * 1024 * 1024; // 5 MB
        if (file.size > maxSize) {
            setError(t('media.fileTooLarge'));
            return;
        }

        setSelectedFile(file);

        // Revoke the old preview URL
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }

        // Create new preview URL
        const objectUrl = URL.createObjectURL(file);
        setPreviewUrl(objectUrl);
    };

    const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            handleFileChange(e.target.files[0]);
        }
    };

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setIsDragActive(true);
        } else if (e.type === 'dragleave') {
            setIsDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileChange(e.dataTransfer.files[0]);
        }
    };

    const triggerFileSelect = () => {
        fileInputRef.current?.click();
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setIsUploading(true);
        setError(null);
        setProgress(0);

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            let data;
            const progressCallback = (progressEvent: any) => {
                if (progressEvent.total) {
                    const percentCompleted = Math.round(
                        (progressEvent.loaded * 100) / progressEvent.total
                    );
                    setProgress(percentCompleted);
                }
            };

            if (mediaId !== undefined) {
                data = await replacePortfolioMedia(mediaId, formData, progressCallback);
            } else if (itemId !== undefined) {
                data = await uploadPortfolioMedia(itemId, formData, progressCallback);
            } else {
                throw new Error('Either itemId or mediaId must be specified.');
            }

            // Successfully uploaded, revoke local preview
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
                setPreviewUrl(null);
            }
            setSelectedFile(null);
            setProgress(100);
            onUploadSuccess(data);
        } catch (err: any) {
            console.error('[PortfolioImageUploader] Upload failed:', err);
            const status = err.response?.status;
            const detail = err.response?.data?.detail;

            if (status === 429) {
                setError(t('error') + ' (Too many requests. Limit 10/min)');
            } else if (detail) {
                // If it is a validation error containing object/dict details, format them
                if (typeof detail === 'object') {
                    setError(JSON.stringify(detail));
                } else {
                    setError(detail);
                }
            } else {
                setError(t('media.uploadFailed'));
            }
        } finally {
            setIsUploading(false);
        }
    };

    const handleRemoveSelected = () => {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            setPreviewUrl(null);
        }
        setSelectedFile(null);
        setError(null);
        setProgress(0);
    };

    return (
        <div className="space-y-4">
            {!previewUrl ? (
                <div
                    onDragEnter={handleDrag}
                    onDragOver={handleDrag}
                    onDragLeave={handleDrag}
                    onDrop={handleDrop}
                    onClick={triggerFileSelect}
                    className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 ${
                        isDragActive
                            ? 'border-violet-500 bg-violet-50/50'
                            : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/30'
                    }`}
                >
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={onInputChange}
                        accept="image/jpeg,image/png,image/webp"
                        className="hidden"
                        disabled={isUploading}
                    />
                    <div className="p-4 bg-violet-50 text-violet-600 rounded-2xl mb-4">
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                            />
                        </svg>
                    </div>
                    <h3 className="text-sm font-bold text-slate-700">{t('media.chooseFile')}</h3>
                    <p className="text-xs text-slate-400 mt-1">{t('media.dragDrop')}</p>
                    <div className="mt-4 flex flex-col gap-1 text-[10px] text-slate-400 font-semibold tracking-wider uppercase">
                        <span>{t('media.supportedFormats')}</span>
                        <span>{t('media.maxFileSize')}</span>
                    </div>
                </div>
            ) : (
                <div className="border border-slate-200 rounded-2xl p-5 bg-slate-50 space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                        <div className="min-w-0 flex-1">
                            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                                {t('media.selectedFile')}
                            </span>
                            <span className="text-sm font-bold text-slate-700 truncate block mt-0.5">
                                {selectedFile?.name}
                            </span>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            disabled={isUploading}
                            onClick={handleRemoveSelected}
                            className="text-rose-600 hover:bg-rose-50/50 hover:text-rose-700 rounded-xl"
                        >
                            {t('media.removeImage')}
                        </Button>
                    </div>

                    <div className="aspect-[16/10] w-full bg-slate-200 rounded-xl overflow-hidden relative border border-slate-150">
                        {previewUrl && (
                            <img
                                src={previewUrl}
                                alt="Upload Preview"
                                className="h-full w-full object-cover"
                            />
                        )}
                        {isUploading && (
                            <div className="absolute inset-0 bg-slate-900/60 flex flex-col items-center justify-center text-white p-4">
                                <div className="w-full max-w-[200px] bg-white/20 h-2 rounded-full overflow-hidden mb-3">
                                    <div
                                        style={{ width: `${progress}%` }}
                                        className="bg-violet-500 h-full rounded-full transition-all duration-300"
                                    />
                                </div>
                                <span className="text-xs font-bold uppercase tracking-wider">
                                    {t('media.uploadProgress', { percent: progress })}
                                </span>
                            </div>
                        )}
                    </div>

                    {!isUploading && (
                        <div className="flex items-center justify-end gap-3">
                            {onCancel && (
                                <Button
                                    variant="outline"
                                    onClick={onCancel}
                                    className="rounded-xl font-bold"
                                >
                                    Cancel
                                </Button>
                            )}
                            <Button
                                onClick={handleUpload}
                                className="bg-violet-600 hover:bg-violet-700 text-white rounded-xl font-bold shadow-md shadow-violet-100 min-w-[120px]"
                            >
                                {mediaId !== undefined ? t('media.replaceImage') : t('media.upload')}
                            </Button>
                        </div>
                    )}
                </div>
            )}

            {error && (
                <div className="p-3 bg-rose-50 border border-rose-100 rounded-xl text-rose-700 text-xs font-medium flex items-center justify-between">
                    <span>{error}</span>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleUpload}
                        disabled={isUploading || !selectedFile}
                        className="border-rose-200 text-rose-700 hover:bg-rose-100/30 rounded-lg text-[10px] py-1 h-7"
                    >
                        {t('media.retryUpload')}
                    </Button>
                </div>
            )}
        </div>
    );
}
