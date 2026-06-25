import React from 'react';
import Link from 'next/link';
import FavoriteButton from '@/components/features/favorites/FavoriteButton';

interface ProviderInfo {
    id: number;
    username: string;
    rating_avg?: number | string | null;
    reviews_count?: number;
}

export interface ServiceCardProps {
    id: number | string;
    title: string;
    description?: string;
    city?: string;
    address?: string;
    price_amount?: string | number;
    price_type?: string;
    category_name?: string;
    provider?: ProviderInfo | number | null;
    rating?: number | string;
    cover?: string | null;
    href?: string;
    is_active?: boolean;
    locale?: string;
    className?: string;
    showFavoriteButton?: boolean;
    isFavorite?: boolean;
    onShowOnMap?: () => void;
    isSelected?: boolean;
    distance_m?: number;
}

export const ServiceCard: React.FC<ServiceCardProps> = ({
    id,
    title,
    description,
    city,
    address,
    price_amount,
    price_type = 'service',
    category_name,
    provider,
    rating,
    cover,
    href,
    is_active = true,
    locale = 'ru',
    className = '',
    showFavoriteButton = true,
    isFavorite = false,
    onShowOnMap,
    isSelected = false,
    distance_m,
}) => {
    // Resolve detail page URL
    const detailUrl = href || `/${locale}/service/${id}/`;

    // Resolve rating
    let displayRating = 0.0;
    let reviewsCount = 0;
    if (rating !== undefined) {
        displayRating = typeof rating === 'string' ? parseFloat(rating) : rating;
    } else if (provider && typeof provider === 'object') {
        displayRating = typeof provider.rating_avg === 'string' ? parseFloat(provider.rating_avg) : (provider.rating_avg || 0.0);
        reviewsCount = provider.reviews_count || 0;
    }

    const [imageFailed, setImageFailed] = React.useState(false);

    React.useEffect(() => {
        setImageFailed(false);
    }, [cover]);

    // Resolve price
    const resolvedPrice = typeof price_amount === 'string' ? parseFloat(price_amount) : (price_amount || 0);

    return (
        <div className={`group relative flex flex-col justify-between overflow-hidden rounded-2xl border transition-all duration-300 hover:shadow-md hover:-translate-y-0.5 ${
            isSelected 
                ? 'border-violet-500 ring-4 ring-violet-500/20 bg-violet-50/10' 
                : 'border-neutral-200 bg-white hover:border-violet-300'
        } ${className}`}>
            <div>
                {/* Image Section */}
                <div className="aspect-[16/10] w-full overflow-hidden bg-neutral-50 relative">
                    {cover && !imageFailed ? (
                        <img
                            src={cover}
                            alt={title}
                            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                            loading="lazy"
                            onError={() => setImageFailed(true)}
                        />
                    ) : (
                        <div className="absolute inset-0 bg-gradient-to-tr from-violet-600 via-indigo-600 to-fuchsia-600 text-white flex flex-col items-center justify-center p-4 text-center select-none overflow-hidden">
                            {/* Subtle decorative shapes */}
                            <div className="absolute -bottom-8 -right-8 w-24 h-24 rounded-full bg-white/5 border border-white/10 pointer-events-none" />
                            <div className="absolute -top-8 -left-8 w-20 h-20 rounded-full bg-white/5 pointer-events-none" />
                            
                            <span className="text-3xl font-black opacity-25 mb-1 tracking-wider uppercase select-none">
                                {category_name ? category_name.slice(0, 2).toUpperCase() : 'SR'}
                            </span>
                            <span className="text-[10px] font-black uppercase tracking-widest text-violet-100/95 max-w-full truncate px-2 select-none">
                                {category_name || 'Service'}
                            </span>
                        </div>
                    )}

                    {/* Active State Badge */}
                    {!is_active && (
                        <div className="absolute top-3 left-3 bg-neutral-900/80 backdrop-blur-sm text-white text-xs px-2.5 py-1 rounded-full font-semibold">
                            Inactive
                        </div>
                    )}

                    {/* Favorite Button overlay */}
                    {showFavoriteButton && (
                        <div className="absolute top-3 right-3 z-10">
                            <FavoriteButton
                                contentType="service"
                                objectId={Number(id)}
                                initialIsFavorite={isFavorite}
                                size="sm"
                            />
                        </div>
                    )}
                </div>

                {/* Content Section */}
                <div className="p-5">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-1.5">
                            {category_name && (
                                <span className="text-[10px] font-bold uppercase tracking-wider text-violet-600 bg-violet-50 px-2.5 py-0.5 rounded-full">
                                    {category_name}
                                </span>
                            )}
                            {distance_m !== undefined && distance_m !== null && Number.isFinite(distance_m) && (
                                <span className="text-[10px] font-extrabold text-violet-700 bg-violet-50 border border-violet-100 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                                    <svg className="w-3 h-3 text-violet-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                    </svg>
                                    {distance_m < 1000 ? `${Math.round(distance_m)} ${locale === 'en' ? 'm' : locale === 'kz' ? 'м' : 'м'}` : `${(distance_m / 1000).toFixed(1)} ${locale === 'en' ? 'km' : locale === 'kz' ? 'км' : 'км'}`}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center text-xs text-neutral-500">
                            <svg className="h-3.5 w-3.5 text-amber-400 mr-1" fill="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.977-2.888a1 1 0 00-1.176 0l-3.977 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                            </svg>
                            <span>
                                {displayRating.toFixed(1)} {reviewsCount > 0 ? `(${reviewsCount})` : ''}
                            </span>
                        </div>
                    </div>

                    <h3 className="text-base font-bold text-neutral-900 line-clamp-1 group-hover:text-violet-600 transition-colors">
                        {title}
                    </h3>

                    {/* Provider Info */}
                    {provider && typeof provider === 'object' && (
                        <div className="mt-1 flex items-center gap-1.5 text-xs text-neutral-500">
                            <svg className="w-3.5 h-3.5 text-neutral-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                            <span className="font-semibold truncate">{provider.username}</span>
                        </div>
                    )}

                    {description && (
                        <p className="mt-2 text-sm text-neutral-500 line-clamp-2 min-h-[40px] leading-relaxed">
                            {description}
                        </p>
                    )}

                    {/* Location label */}
                    {(address?.trim() || city?.trim()) && (
                        <div className="mt-2.5 flex items-center text-xs text-neutral-400 gap-1">
                            <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            <span>{address?.trim() || city?.trim()}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer / Price Section */}
            {price_amount !== undefined && (
                <div className="p-5 pt-0">
                    <div className="mt-3 pt-4 border-t border-neutral-100 flex items-center justify-between gap-2">
                        <div className="text-lg font-extrabold text-neutral-950 truncate">
                            ₸ {resolvedPrice.toLocaleString()}
                            <span className="text-xs font-normal text-neutral-500 ml-1">/{price_type}</span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                            {onShowOnMap && (
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        onShowOnMap();
                                    }}
                                    className="rounded-xl border border-neutral-200 bg-white px-2.5 py-2 text-xs font-bold text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 transition-all active:scale-95 shadow-2xs flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-violet-500"
                                    title={locale === 'en' ? 'Show on map' : locale === 'kz' ? 'Картада көрсету' : 'Показать на карте'}
                                >
                                    <svg className="w-3.5 h-3.5 text-violet-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                    </svg>
                                    <span className="hidden sm:inline">
                                        {locale === 'en' ? 'Map' : locale === 'kz' ? 'Карта' : 'На карте'}
                                    </span>
                                </button>
                            )}
                            <Link
                                href={detailUrl}
                                className="rounded-xl bg-violet-600 px-4 py-2 text-xs font-bold text-white transition-all hover:bg-violet-700 active:scale-95 shadow-sm hover:shadow-violet-100 hover:shadow-md shrink-0 focus:outline-none focus:ring-2 focus:ring-violet-500"
                            >
                                {locale === 'en' ? 'Details' : locale === 'kz' ? 'Толығырақ' : 'Подробнее'}
                            </Link>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
