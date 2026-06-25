"use client";

import React, { useRef, useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { uploadMyAvatar, deleteMyAvatar } from "@/lib/api/accounts";

interface AvatarUploaderProps {
    currentAvatarUrl?: string | null;
    initials?: string;
    onUploadSuccess: (updatedUser: any) => void;
    onRemoveSuccess: () => void;
}

export const AvatarUploader: React.FC<AvatarUploaderProps> = ({
    currentAvatarUrl,
    initials = "P",
    onUploadSuccess,
    onRemoveSuccess,
}) => {
    const t = useTranslations("provider.profile.avatar");

    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [progress, setProgress] = useState<number>(0);
    const [status, setStatus] = useState<"idle" | "selected" | "uploading" | "success" | "error">("idle");
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [isDragOver, setIsDragOver] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    const fileInputRef = useRef<HTMLInputElement>(null);

    // Cleanup object URL to prevent memory leaks
    const revokePreview = (url: string | null) => {
        if (url && url.startsWith("blob:")) {
            URL.revokeObjectURL(url);
        }
    };

    useEffect(() => {
        return () => {
            revokePreview(previewUrl);
        };
    }, [previewUrl]);

    const handleFileChange = (file: File | null) => {
        if (!file) return;

        // Frontend validation hints
        const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
        if (!allowedTypes.includes(file.type)) {
            setErrorMessage(t("invalidType"));
            setStatus("error");
            return;
        }

        const maxBytes = 5 * 1024 * 1024;
        if (file.size > maxBytes) {
            setErrorMessage(t("maxFileSize"));
            setStatus("error");
            return;
        }

        setErrorMessage(null);
        setSelectedFile(file);
        
        // Revoke the old preview URL before setting the new one
        revokePreview(previewUrl);

        const localUrl = URL.createObjectURL(file);
        setPreviewUrl(localUrl);
        setStatus("selected");
    };

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileChange(e.target.files[0]);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(true);
    };

    const handleDragLeave = () => {
        setIsDragOver(false);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileChange(e.dataTransfer.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setStatus("uploading");
        setProgress(0);
        setErrorMessage(null);

        const formData = new FormData();
        formData.append("avatar", selectedFile);

        try {
            const updatedUser = await uploadMyAvatar(formData, (progressEvent) => {
                const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                setProgress(percent);
            });
            
            setStatus("success");
            onUploadSuccess(updatedUser);
            
            // Revoke local blob preview since remote URL is now active
            revokePreview(previewUrl);
            setPreviewUrl(null);
            setSelectedFile(null);
        } catch (err: any) {
            console.error("Avatar upload failed:", err);
            setStatus("error");
            
            const detail = err.response?.data?.detail;
            if (detail) {
                setErrorMessage(detail);
            } else {
                setErrorMessage(t("uploadFailed"));
            }
        }
    };

    const handleDelete = async () => {
        setStatus("uploading");
        setErrorMessage(null);
        try {
            await deleteMyAvatar();
            setStatus("idle");
            setPreviewUrl(null);
            setSelectedFile(null);
            setShowDeleteConfirm(false);
            onRemoveSuccess();
        } catch (err: any) {
            console.error("Avatar deletion failed:", err);
            setStatus("error");
            const detail = err.response?.data?.detail;
            setErrorMessage(detail || t("uploadFailed"));
        }
    };

    const triggerFileSelect = () => {
        fileInputRef.current?.click();
    };

    const handleReset = () => {
        revokePreview(previewUrl);
        setPreviewUrl(null);
        setSelectedFile(null);
        setStatus("idle");
        setErrorMessage(null);
    };

    const displayUrl = previewUrl || currentAvatarUrl;

    return (
        <div className="flex flex-col items-center gap-6 p-6 bg-white border border-neutral-100 rounded-2xl shadow-xs max-w-sm mx-auto">
            <h3 className="text-base font-extrabold text-neutral-900 tracking-tight">{t("avatarTitle")}</h3>
            
            {/* Avatar Preview Ring */}
            <div 
                className={`relative w-32 h-32 rounded-full flex items-center justify-center bg-violet-50 text-violet-700 font-extrabold text-4xl border-2 transition-all ${
                    isDragOver ? "border-violet-500 scale-105" : "border-neutral-200"
                } overflow-hidden group select-none`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={triggerFileSelect}
                style={{ cursor: "pointer" }}
            >
                {displayUrl ? (
                    <img 
                        src={displayUrl} 
                        alt="Avatar Preview" 
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <span>{initials[0]?.toUpperCase()}</span>
                )}

                <div className="absolute inset-0 bg-neutral-900/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-semibold">
                    {t("chooseImage")}
                </div>
            </div>

            <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileInput}
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
            />

            <div className="text-center space-y-1">
                <p className="text-xs text-neutral-500">{t("supportedFormats")}</p>
                <p className="text-xs text-neutral-500">{t("maxFileSize")}</p>
            </div>

            {/* Error or Validation Message */}
            {errorMessage && (
                <div className="text-xs font-semibold text-rose-600 bg-rose-50 px-3 py-2 rounded-xl border border-rose-100 w-full text-center">
                    {errorMessage}
                </div>
            )}

            {/* Selection/Upload Actions */}
            <div className="w-full space-y-3">
                {status === "selected" && (
                    <div className="space-y-2">
                        <p className="text-xs text-neutral-600 truncate text-center font-medium">
                            {t("selectedFile")}: {selectedFile?.name}
                        </p>
                        <div className="flex gap-2">
                            <button
                                onClick={handleUpload}
                                className="flex-1 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-xl text-xs font-bold transition active:scale-95 shadow-md shadow-violet-100"
                            >
                                {t("uploadAvatar")}
                            </button>
                            <button
                                onClick={handleReset}
                                className="px-4 py-2 border border-neutral-200 hover:bg-neutral-50 text-neutral-600 rounded-xl text-xs font-bold transition active:scale-95"
                            >
                                {t("noAvatar")}
                            </button>
                        </div>
                    </div>
                )}

                {status === "uploading" && (
                    <div className="space-y-2">
                        <div className="w-full bg-neutral-100 h-1.5 rounded-full overflow-hidden">
                            <div 
                                className="bg-violet-600 h-full rounded-full transition-all duration-300"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                        <p className="text-xs text-neutral-600 text-center font-bold">
                            {t("uploadProgress", { percent: progress })}
                        </p>
                    </div>
                )}

                {status === "success" && (
                    <div className="text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-2 rounded-xl border border-emerald-100 w-full text-center">
                        {t("uploadSuccess")}
                    </div>
                )}

                {status === "error" && (
                    <button
                        onClick={selectedFile ? handleUpload : triggerFileSelect}
                        className="w-full px-4 py-2 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 rounded-xl text-xs font-bold transition active:scale-95"
                    >
                        {t("retryUpload")}
                    </button>
                )}

                {status === "idle" && (
                    <div className="flex flex-col gap-2">
                        <button
                            onClick={triggerFileSelect}
                            className="w-full px-4 py-2.5 bg-violet-50 hover:bg-violet-100 border border-violet-100 text-violet-700 rounded-xl text-xs font-bold transition active:scale-95"
                        >
                            {currentAvatarUrl ? t("replaceAvatar") : t("uploadAvatar")}
                        </button>
                        
                        {currentAvatarUrl && !showDeleteConfirm && (
                            <button
                                onClick={() => setShowDeleteConfirm(true)}
                                className="w-full px-4 py-2.5 text-rose-600 hover:bg-rose-50 rounded-xl text-xs font-bold transition active:scale-95"
                            >
                                {t("removeAvatar")}
                            </button>
                        )}
                    </div>
                )}

                {showDeleteConfirm && (
                    <div className="bg-rose-50/50 p-4 border border-rose-100 rounded-2xl space-y-3">
                        <h4 className="text-xs font-extrabold text-neutral-900">{t("removeConfirmTitle")}</h4>
                        <p className="text-[11px] text-neutral-600 leading-relaxed">{t("removeConfirmDescription")}</p>
                        <div className="flex gap-2">
                            <button
                                onClick={handleDelete}
                                className="flex-1 px-3 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition active:scale-95"
                            >
                                {t("removeAvatar")}
                            </button>
                            <button
                                onClick={() => setShowDeleteConfirm(false)}
                                className="px-3 py-2 bg-white border border-neutral-200 hover:bg-neutral-50 text-neutral-600 rounded-xl text-xs font-bold transition active:scale-95"
                            >
                                {t("noAvatar")}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
