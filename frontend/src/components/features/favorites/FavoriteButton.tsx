'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useAuthStore } from '@/store/useAuthStore';
import { api } from '@/lib/api';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { FavoriteToggleResponse } from '@/types/favorites';

interface FavoriteButtonProps {
    contentType: 'service' | 'provider';
    objectId: number;
    initialIsFavorite?: boolean;
    disabled?: boolean;
    size?: 'sm' | 'md';
    onChange?: (isFavorite: boolean) => void;
}

export default function FavoriteButton({
    contentType,
    objectId,
    initialIsFavorite = false,
    disabled = false,
    size = 'md',
    onChange,
}: FavoriteButtonProps) {
    const locale = useLocale();
    const router = useRouter();
    const { isAuthenticated, user } = useAuthStore();
    const t = useTranslations('favorites');

    const [isFavorite, setIsFavorite] = useState(!!initialIsFavorite);
    const [isLoading, setIsLoading] = useState(false);

    // Synchronize local state with props when they change
    useEffect(() => {
        setIsFavorite(!!initialIsFavorite);
    }, [initialIsFavorite]);

    // If authenticated and the user is a provider, return null (do not show the button)
    if (isAuthenticated && user?.role === 'provider') {
        return null;
    }

    const handleToggle = async (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();

        if (isLoading || disabled) return;

        // If user is guest, redirect to login page with next param preserving trailingSlash
        if (!isAuthenticated) {
            const nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
            router.push(`/${locale}/login/?next=${nextUrl}`);
            return;
        }

        // Only clients can toggle favorites
        if (user?.role !== 'client') {
            return;
        }

        const previousState = isFavorite;
        
        // Optimistic UI update
        setIsFavorite(!previousState);
        setIsLoading(true);

        try {
            const { data } = await api.post<FavoriteToggleResponse>(
                ENDPOINTS.FAVORITES_TOGGLE,
                {
                    content_type: contentType,
                    object_id: objectId,
                }
            );

            const nextState = data.status === 'added';
            setIsFavorite(nextState);
            if (onChange) {
                onChange(nextState);
            }
        } catch (error) {
            console.error('[FavoriteButton] Failed to toggle favorite status:', error);
            // Rollback optimistic update on error
            setIsFavorite(previousState);
        } finally {
            setIsLoading(false);
        }
    };

    const isSmall = size === 'sm';
    const iconSize = isSmall ? 'h-4 w-4' : 'h-5 w-5';
    const padding = isSmall ? 'p-1.5' : 'p-2.5';

    return (
        <button
            onClick={handleToggle}
            disabled={disabled || isLoading}
            className={`relative rounded-full transition-all duration-300 shadow-sm border bg-white/90 backdrop-blur focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${padding} ${
                isFavorite
                    ? 'border-red-100 text-red-500 hover:bg-red-50'
                    : 'border-neutral-200 text-neutral-400 hover:text-red-500 hover:border-red-100 hover:bg-red-50/50'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} group`}
            title={isFavorite ? t('remove') : t('add')}
        >
            {isLoading ? (
                // Smooth spinner/loading state
                <svg
                    className={`animate-spin ${iconSize} text-red-500`}
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                >
                    <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                    />
                    <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                </svg>
            ) : isFavorite ? (
                // Filled heart with subtle scale animation on hover
                <svg
                    className={`${iconSize} fill-current transition-transform duration-300 group-hover:scale-110`}
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
                </svg>
            ) : (
                // Outline heart
                <svg
                    className={`${iconSize} stroke-current transition-transform duration-300 group-hover:scale-110`}
                    fill="none"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                    strokeWidth="2"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
                    />
                </svg>
            )}
        </button>
    );
}
