'use client';

import { FormEvent, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { Service } from '@/types/catalog';
import { useAuthStore } from '@/store/useAuthStore';
import { api } from '@/lib/api';
import { ENDPOINTS } from '@/lib/api/endpoints';

interface ContactModalProps {
    service: Service;
    isOpen: boolean;
    onClose: () => void;
    locale: string;
}

export default function ContactModal({
    service,
    isOpen,
    onClose,
    locale,
}: ContactModalProps) {
    const t = useTranslations('contactModal');
    const router = useRouter();
    const { user } = useAuthStore();  // ✅ Single source of truth

    const [formData, setFormData] = useState({
        description: '',
        event_date: '',
        city: service.city || '',
        budget_min: '',
        budget_max: '',
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errors, setErrors] = useState<Record<string, string>>({});

    if (!isOpen) return null;

    // ✅ Correct ownership check using provider_profile_id
    const isOwnService =
        user?.role === 'provider' &&
        user.provider_profile_id != null &&
        service.provider?.id === user.provider_profile_id;

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();

        setIsSubmitting(true);
        setErrors({});

        try {
            const payload = {
                target_service_id: service.id,
                title: t('requestFor', { service: service.title }),
                description: formData.description,
                event_date: new Date(formData.event_date).toISOString(), // Keep for backwards compatibility if needed
                event_start_at: new Date(formData.event_date).toISOString(),
                city: formData.city,
                ...(formData.budget_min && { budget_min: parseFloat(formData.budget_min) }),
                ...(formData.budget_max && { budget_max: parseFloat(formData.budget_max) }),
            };

            const response = await api.post(ENDPOINTS.REQUESTS, payload);

            // Success - navigate to chat if available, else request detail
            if (response.data.chat_id) {
                router.push(`/${locale}/dashboard/chats/${response.data.chat_id}`);
            } else {
                router.push(`/${locale}/dashboard/requests/${response.data.id}`);
            }

            onClose();
        } catch (error: any) {
            if (error.response?.status === 400 && error.response?.data) {
                // Validation errors from API
                const apiErrors: Record<string, string> = {};
                Object.keys(error.response.data).forEach((key) => {
                    const errorMsg = error.response.data[key];
                    apiErrors[key] = Array.isArray(errorMsg) ? errorMsg[0] : errorMsg;
                });
                setErrors(apiErrors);
            } else {
                setErrors({ general: t('errorGeneral') });
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
                {/* Header */}
                <div className="mb-6 flex items-center justify-between">
                    <h2 className="text-2xl font-bold text-gray-900">{t('title')}</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                        aria-label={t('close')}
                    >
                        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Service Info */}
                <div className="mb-6 rounded-lg bg-gray-50 p-4">
                    <p className="text-sm font-semibold text-gray-900">{service.title}</p>
                    <p className="text-sm text-gray-600">{service.category_name}</p>
                </div>

                {/* Role Validation Messages */}
                {isOwnService ? (
                    <div className="mb-4 rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800">
                        {t('ownServiceMessage')}
                    </div>
                ) : user?.role === 'provider' ? (
                    <div className="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800">
                        {t('providerRoleMessage')}
                    </div>
                ) : null}

                {/* Form */}
                <form onSubmit={handleSubmit}>
                    {/* Description */}
                    <div className="mb-4">
                        <label htmlFor="description" className="mb-2 block text-sm font-semibold text-gray-700">
                            {t('descriptionLabel')} <span className="text-red-500">*</span>
                        </label>
                        <textarea
                            id="description"
                            rows={4}
                            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                            placeholder={t('descriptionPlaceholder')}
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            required
                            disabled={isOwnService || user?.role === 'provider'}
                        />
                        {errors.description && (
                            <p className="mt-1 text-xs text-red-600">{errors.description}</p>
                        )}
                    </div>

                    {/* Event Date */}
                    <div className="mb-4">
                        <label htmlFor="event_date" className="mb-2 block text-sm font-semibold text-gray-700">
                            {t('eventDateLabel')} <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="datetime-local"
                            id="event_date"
                            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                            value={formData.event_date}
                            onChange={(e) => setFormData({ ...formData, event_date: e.target.value })}
                            required
                            disabled={isOwnService || user?.role === 'provider'}
                        />
                        {errors.event_date && (
                            <p className="mt-1 text-xs text-red-600">{errors.event_date}</p>
                        )}
                    </div>

                    {/* City */}
                    <div className="mb-4">
                        <label htmlFor="city" className="mb-2 block text-sm font-semibold text-gray-700">
                            {t('cityLabel')} <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            id="city"
                            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                            placeholder={t('cityPlaceholder')}
                            value={formData.city}
                            onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                            required
                            disabled={isOwnService || user?.role === 'provider'}
                        />
                        {errors.city && (
                            <p className="mt-1 text-xs text-red-600">{errors.city}</p>
                        )}
                    </div>

                    {/* Budget (Optional) */}
                    <div className="mb-6 grid grid-cols-2 gap-4">
                        <div>
                            <label htmlFor="budget_min" className="mb-2 block text-sm font-semibold text-gray-700">
                                {t('budgetMinLabel')}
                            </label>
                            <input
                                type="number"
                                id="budget_min"
                                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                                placeholder="10000"
                                value={formData.budget_min}
                                onChange={(e) => setFormData({ ...formData, budget_min: e.target.value })}
                                disabled={isOwnService || user?.role === 'provider'}
                            />
                        </div>
                        <div>
                            <label htmlFor="budget_max" className="mb-2 block text-sm font-semibold text-gray-700">
                                {t('budgetMaxLabel')}
                            </label>
                            <input
                                type="number"
                                id="budget_max"
                                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                                placeholder="50000"
                                value={formData.budget_max}
                                onChange={(e) => setFormData({ ...formData, budget_max: e.target.value })}
                                disabled={isOwnService || user?.role === 'provider'}
                            />
                        </div>
                    </div>

                    {/* General Error */}
                    {errors.general && (
                        <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">
                            {errors.general}
                        </div>
                    )}

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={isSubmitting || isOwnService || user?.role === 'provider'}
                        className="w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-bold text-white transition-colors hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                    >
                        {isSubmitting ? t('submitting') : t('submitButton')}
                    </button>
                </form>
            </div>
        </div>
    );
}
