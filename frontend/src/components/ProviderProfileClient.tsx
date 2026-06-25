'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Link } from '@/routing';
import { useTranslations } from 'next-intl';
import { api } from '@/lib/api';
import {
  providerUrl,
  providerReviewsUrl,
  providerPortfolioUrl,
  ENDPOINTS
} from '@/lib/api/endpoints';
import { useAuthStore } from '@/store/useAuthStore';
import FavoriteButton from '@/components/features/favorites/FavoriteButton';
import ReportButton from '@/components/features/reports/ReportButton';
import { ProviderPublicProfile, Review } from '@/types/providers';
import { PortfolioItem } from '@/types/portfolio';
import { Service, PaginatedResponse } from '@/types/catalog';
import { ServiceCard } from '@/components/shared/ServiceCard';
import { Card } from '@/components/ui/Card';

function formatSafeDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString();
}

interface ProviderProfileClientProps {
  id: string;
  locale: string;
}

type TabType = 'services' | 'portfolio' | 'reviews';

export default function ProviderProfileClient({ id, locale }: ProviderProfileClientProps) {
  const t = useTranslations('providers');
  const router = useRouter();
  const { user } = useAuthStore();

  const [activeTab, setActiveTab] = useState<TabType>('services');
  const [profile, setProfile] = useState<ProviderPublicProfile | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    setImageFailed(false);
  }, [id, profile?.avatar_url, profile?.avatar]);

  // Check ownership
  const providerProfileId = user?.provider_profile_id ?? (user as any)?.provider_profile?.id;
  const isOwner = providerProfileId === Number(id);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      setIsError(false);
      try {
        // Fetch public profile detail
        const profileRes = await api.get<ProviderPublicProfile>(providerUrl(id));
        setProfile(profileRes.data);

        // Fetch services (active only)
        const servicesRes = await api.get<PaginatedResponse<Service> | Service[]>(ENDPOINTS.SERVICES, {
          params: { provider: id, is_active: true }
        });
        const servicesData = Array.isArray(servicesRes.data)
          ? servicesRes.data
          : servicesRes.data.results || [];
        setServices(servicesData);

        // Fetch portfolio items
        const portfolioRes = await api.get<PortfolioItem[]>(providerPortfolioUrl(id));
        setPortfolio(portfolioRes.data || []);

        // Fetch reviews
        const reviewsRes = await api.get<PaginatedResponse<Review> | Review[]>(providerReviewsUrl(id));
        const reviewsData = Array.isArray(reviewsRes.data)
          ? reviewsRes.data
          : (reviewsRes.data as any).results || [];
        setReviews(reviewsData);

      } catch (err) {
        console.error('Error loading provider data:', err);
        setIsError(true);
      } finally {
        setIsLoading(false);
      }
    }

    if (id) {
      loadData();
    }
  }, [id]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-violet-600 mb-4"></div>
        <p className="text-neutral-500 font-medium text-sm">{t('loading')}</p>
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 px-4">
        <div className="h-16 w-16 bg-rose-50 rounded-full flex items-center justify-center mx-auto text-rose-500 mb-4 border border-rose-100">
          <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-2xl font-black text-neutral-900 mb-2">
          {!profile ? t('notFound') : t('error')}
        </h2>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 px-6 py-2.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl font-bold transition active:scale-95 shadow-md shadow-violet-100 text-sm"
        >
          {t('loading')}
        </button>
      </div>
    );
  }

  const initialLetter = profile.username?.[0]?.toUpperCase() || 'P';

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Premium Glassmorphism Header */}
      <div className="relative bg-gradient-to-r from-violet-50 via-white to-indigo-50 rounded-3xl p-6 md:p-8 border border-neutral-150 shadow-xs mb-8 overflow-hidden">
        {/* Decorative background blur shapes */}
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-72 h-72 rounded-full bg-violet-200/30 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -ml-16 -mb-16 w-72 h-72 rounded-full bg-indigo-200/30 blur-3xl pointer-events-none" />

        <div className="relative flex flex-col md:flex-row items-center md:items-start justify-between gap-6">
          <div className="flex flex-col md:flex-row items-center md:items-start gap-6 text-center md:text-left">
            {/* Avatar container */}
            <div className="relative h-28 w-28 rounded-3xl border-4 border-white shadow-md bg-violet-100 flex items-center justify-center text-violet-750 font-black text-4xl overflow-hidden shrink-0">
              {(profile.avatar_url || profile.avatar) && !imageFailed ? (
                <img
                  src={profile.avatar_url || profile.avatar || undefined}
                  alt={profile.username}
                  className="h-full w-full object-cover"
                  onError={() => setImageFailed(true)}
                />
              ) : (
                initialLetter
              )}
            </div>

            {/* Profile Info */}
            <div className="pt-2">
              <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 mb-2">
                <h1 className="text-3xl font-black text-neutral-900 leading-tight">{profile.username}</h1>
                
                {profile.city && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-violet-50 text-violet-700 border border-violet-100 shadow-3xs">
                    <svg className="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {profile.city}
                  </span>
                )}
              </div>

              {/* Rating summary */}
              <div className="flex items-center justify-center md:justify-start text-xs font-semibold text-neutral-500 mb-4 gap-2">
                <div className="flex items-center">
                  <svg className="h-4.5 w-4.5 text-amber-400 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  <span className="font-bold text-neutral-900 text-sm">{profile.rating_avg !== null ? profile.rating_avg : '0.0'}</span>
                </div>
                <span>•</span>
                <span>{profile.reviews_count} {t('reviewsCount')}</span>
              </div>

              {/* Bio card */}
              {profile.bio && (
                <div className="max-w-2xl bg-white/60 backdrop-blur-sm rounded-2xl p-4 border border-neutral-150 text-left text-neutral-600 text-sm leading-relaxed">
                  <p className="font-bold text-neutral-850 mb-1">{t('bio')}</p>
                  {profile.bio}
                </div>
              )}
            </div>
          </div>

          {/* Action block (Favorite and Report Buttons) */}
          {!isOwner && (
            <div className="pt-2 shrink-0 flex items-center gap-2">
              <FavoriteButton
                contentType="provider"
                objectId={profile.id}
                initialIsFavorite={profile.is_favorite}
                size="md"
              />
              <ReportButton
                contentType="provider"
                objectId={profile.id}
                variant="button"
                className="h-10"
              />
            </div>
          )}
        </div>
      </div>

      {/* Modern Tab Navigation */}
      <div className="border-b border-neutral-200 mb-8">
        <div className="flex gap-8">
          {(['services', 'portfolio', 'reviews'] as const).map((tab) => {
            const isActive = activeTab === tab;
            let label = '';
            let count = 0;
            if (tab === 'services') {
              label = t('services');
              count = services.length;
            } else if (tab === 'portfolio') {
              label = t('portfolio');
              count = portfolio.length;
            } else if (tab === 'reviews') {
              label = t('reviews');
              count = reviews.length;
            }

            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`relative pb-4 font-bold text-sm transition-colors focus:outline-none ${
                  isActive ? 'text-violet-600' : 'text-neutral-400 hover:text-neutral-600'
                }`}
              >
                <span className="flex items-center gap-1.5">
                  {label}
                  <span className={`inline-flex items-center justify-center px-2 py-0.5 rounded-full text-2xs font-bold ${
                    isActive ? 'bg-violet-50 text-violet-750' : 'bg-neutral-100 text-neutral-500'
                  }`}>
                    {count}
                  </span>
                </span>
                {isActive && (
                  <span className="absolute bottom-0 left-0 w-full h-0.5 bg-violet-600 rounded-full" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Contents */}
      <div className="min-h-[300px]">
        {/* SERVICES TAB */}
        {activeTab === 'services' && (
          <div>
            {services.length === 0 ? (
              <div className="text-center py-16 bg-neutral-50 rounded-3xl border border-dashed border-neutral-200 p-8">
                <svg className="h-12 w-12 text-neutral-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 13a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v7zM12 17v4m-3 0h6" />
                </svg>
                <p className="text-neutral-500 font-medium text-sm">{t('noServices')}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {services.map((service) => (
                  <ServiceCard
                    key={service.id}
                    id={service.id}
                    title={service.title}
                    description={service.description}
                    city={service.city}
                    price_amount={service.price_amount}
                    price_type={service.price_type}
                    category_name={service.category_name}
                    provider={profile}
                    cover={service.cover}
                    isFavorite={!!service.is_favorite}
                    locale={locale}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* PORTFOLIO TAB */}
        {activeTab === 'portfolio' && (
          <div>
            {portfolio.length === 0 ? (
              <div className="text-center py-16 bg-neutral-50 rounded-3xl border border-dashed border-neutral-200 p-8">
                <svg className="h-12 w-12 text-neutral-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="text-neutral-500 font-medium text-sm">{t('noPortfolio')}</p>
              </div>
            ) : (
              <div className="space-y-8">
                {portfolio.map((item) => (
                  <Card key={item.id} className="p-6 md:p-8">
                    <div className="mb-6">
                      <h3 className="text-xl font-black text-neutral-900 mb-2">{item.title}</h3>
                      <p className="text-neutral-600 leading-relaxed text-sm max-w-3xl">{item.description}</p>
                    </div>

                    {/* Media grid */}
                    {item.media && item.media.length > 0 && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                        {item.media.map((mediaItem) => (
                          <div key={mediaItem.id} className="aspect-video bg-neutral-50 rounded-2xl border border-neutral-150 overflow-hidden relative group">
                            {mediaItem.media_type === 'image' ? (
                              <img
                                src={mediaItem.resolved_url || mediaItem.file_url}
                                alt={item.title}
                                className="h-full w-full object-cover group-hover:scale-103 transition duration-300"
                              />
                            ) : (
                              <video
                                src={mediaItem.resolved_url || mediaItem.file_url}
                                controls
                                className="h-full w-full object-cover"
                              />
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* REVIEWS TAB */}
        {activeTab === 'reviews' && (
          <div>
            {reviews.length === 0 ? (
              <div className="text-center py-16 bg-neutral-50 rounded-3xl border border-dashed border-neutral-200 p-8">
                <svg className="h-12 w-12 text-neutral-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p className="text-neutral-500 font-medium text-sm">{t('noReviews')}</p>
              </div>
            ) : (
              <div className="space-y-6 max-w-4xl">
                {reviews.map((review) => {
                  const clientInitial = review.client_email?.[0]?.toUpperCase() || 'C';
                  
                  return (
                    <div key={review.id} className="bg-white rounded-2xl border border-neutral-150 p-6 flex flex-col md:flex-row gap-5 shadow-3xs">
                      {/* Client Avatar placeholder */}
                      <div className="h-12 w-12 rounded-2xl bg-neutral-100 flex items-center justify-center text-neutral-500 font-bold shrink-0">
                        {clientInitial}
                      </div>

                      {/* Content */}
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                          <div>
                            <span className="font-bold text-neutral-900 text-sm block">{review.client_email}</span>
                            <span className="text-3xs text-neutral-400">{formatSafeDate(review.created_at)}</span>
                          </div>

                           {/* Rating stars and Report */}
                          <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1 bg-amber-50 border border-amber-100 px-2 py-0.5 rounded-lg text-amber-600 font-bold text-xs">
                              <svg className="h-3.5 w-3.5 fill-current" viewBox="0 0 20 20">
                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                              </svg>
                              {review.rating}.0
                            </div>

                            {(!user || user.email !== review.client_email) && (
                              <ReportButton
                                contentType="review"
                                objectId={review.id}
                                variant="icon"
                              />
                            )}
                          </div>
                        </div>

                        {/* Review text */}
                        <p className="text-neutral-600 leading-relaxed text-sm mb-4">
                          {review.text}
                        </p>

                        {/* Provider nested reply */}
                        {review.provider_reply ? (
                          <div className="bg-neutral-50 rounded-2xl p-4 border border-neutral-150 mt-2 text-sm leading-relaxed text-neutral-600 relative">
                            <div className="flex items-center gap-1.5 text-xs font-bold text-violet-600 mb-1">
                              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                              </svg>
                              <span>{t('profile') || "Ответ исполнителя"}</span>
                            </div>
                            <p>{review.provider_reply}</p>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
