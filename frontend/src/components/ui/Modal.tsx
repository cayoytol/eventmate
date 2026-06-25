import React, { useEffect } from 'react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    children: React.ReactNode;
    className?: string;
}

export const Modal: React.FC<ModalProps> = ({
    isOpen,
    onClose,
    title,
    children,
    className = '',
}) => {
    // Disable body scroll when open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [isOpen]);

    // Handle Escape key press
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onClose]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            />

            {/* Content Container */}
            <div className={`relative w-full max-w-lg bg-white rounded-3xl shadow-xl border border-neutral-150 transform transition-all p-6 z-10 animate-in fade-in zoom-in-95 duration-200 ${className}`}>
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                    {title ? (
                        <h3 className="text-lg font-bold text-neutral-900">{title}</h3>
                    ) : (
                        <div />
                    )}
                    <button
                        onClick={onClose}
                        className="p-1 text-neutral-400 hover:text-neutral-600 rounded-lg hover:bg-neutral-50 transition"
                        aria-label="Close"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="max-h-[75vh] overflow-y-auto">{children}</div>
            </div>
        </div>
    );
};
