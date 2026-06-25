"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS, availabilityUrl } from "@/lib/api/endpoints";
import { Availability } from "@/types/availability";

interface DayViewProps {
    date: Date;
    onBack: () => void;
}

export default function DayView({ date: selectedDate, onBack }: DayViewProps) {
    const locale = useLocale();
    const t = useTranslations("provider.calendar");

    // State
    const [availabilities, setAvailabilities] = useState<Availability[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Form State
    const [newBlock, setNewBlock] = useState({
        startTime: "10:00",
        endTime: "12:00"
    });
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (selectedDate) {
            fetchAvailability();
        }
    }, [selectedDate]);

    const fetchAvailability = async () => {
        setIsLoading(true);
        try {
            const dateStr = selectedDate.toISOString().split('T')[0];
            const { data } = await api.get<Availability[]>(ENDPOINTS.AVAILABILITY_MY, {
                params: { from: dateStr, to: dateStr }
            });
            // Sort by start time
            const sorted = data.sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());
            setAvailabilities(sorted);
        } catch (error) {
            console.error("Failed to fetch availability", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleAddBlock = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const dateStr = selectedDate.toISOString().split('T')[0];
            const startAt = new Date(`${dateStr}T${newBlock.startTime}:00`).toISOString();
            const endAt = new Date(`${dateStr}T${newBlock.endTime}:00`).toISOString();

            if (startAt >= endAt) {
                alert(t('errorTime'));
                return;
            }

            const { data } = await api.post<Availability>(ENDPOINTS.AVAILABILITY, {
                start_at: startAt,
                end_at: endAt,
                status: 'blocked'
            });

            // Add to list and sort
            setAvailabilities(prev => [...prev, data].sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()));
        } catch (error: any) {
            console.error("Failed to create block", error);
            const msg = error.response?.data?.non_field_errors?.[0] ||
                error.response?.data?.detail ||
                t('errorCreate');
            alert(msg);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm(t('confirmDelete'))) return;
        try {
            await api.delete(availabilityUrl(id));
            setAvailabilities(prev => prev.filter(a => a.id !== id));
        } catch (error) {
            console.error("Failed to delete", error);
            alert(t('errorDelete'));
        }
    };

    const formatDate = (date: Date) => {
        return date.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    };

    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
    };

    // Grouping logic for visualization
    const groupedSlots = Object.values(availabilities.reduce((acc, slot) => {
        const key = `${slot.start_at}-${slot.end_at}`;
        if (!acc[key]) {
            acc[key] = {
                start_at: slot.start_at,
                end_at: slot.end_at,
                slots: []
            };
        }
        acc[key].slots.push(slot);
        return acc;
    }, {} as Record<string, { start_at: string, end_at: string, slots: Availability[] }>)).sort((a, b) =>
        new Date(a.start_at).getTime() - new Date(b.start_at).getTime()
    );

    return (
        <div className="max-w-4xl mx-auto">
            <div className="flex items-center gap-4 mb-6">
                <button
                    onClick={onBack}
                    className="p-2 hover:bg-gray-100 rounded-lg text-sm font-medium"
                >
                    {t('prevMonth')}
                </button>
                <h1 className="text-2xl font-bold">{formatDate(selectedDate)}</h1>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Form Section */}
                <div className="md:col-span-1">
                    <div className="bg-white p-5 rounded-xl border shadow-sm sticky top-6">
                        <h3 className="font-semibold mb-4">{t('addBlockTitle')}</h3>
                        <form onSubmit={handleAddBlock} className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-700 mb-1">{t('startTime')}</label>
                                <input
                                    type="time"
                                    required
                                    value={newBlock.startTime}
                                    onChange={e => setNewBlock({ ...newBlock, startTime: e.target.value })}
                                    className="w-full border rounded-lg p-2"
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-700 mb-1">{t('endTime')}</label>
                                <input
                                    type="time"
                                    required
                                    value={newBlock.endTime}
                                    onChange={e => setNewBlock({ ...newBlock, endTime: e.target.value })}
                                    className="w-full border rounded-lg p-2"
                                />
                            </div>
                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className="w-full bg-black text-white py-2 rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50"
                            >
                                {isSubmitting ? t('blocking') : t('blockButton')}
                            </button>
                            <p className="text-xs text-gray-500 mt-2">
                                {t('blockDesc')}
                            </p>
                        </form>
                    </div>
                </div>

                {/* Slots List Section */}
                <div className="md:col-span-2">
                    <div className="bg-white p-5 rounded-xl border shadow-sm min-h-[400px]">
                        <h3 className="font-semibold mb-4">{t('scheduleTitle')}</h3>

                        {isLoading ? (
                            <div className="text-center py-10 text-gray-500">{t('loading')}</div>
                        ) : availabilities.length === 0 ? (
                            <div className="text-center py-10 text-gray-400 bg-gray-50 rounded-lg border border-dashed">
                                {t('empty')}
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {groupedSlots.map((group) => {
                                    const firstSlot = group.slots[0];
                                    const isBusy = group.slots.some(s => s.status === 'busy');
                                    // Use first slot's capacity for now, assuming same service or similar logic. 
                                    const capacity = firstSlot.order_capacity || 1;
                                    const busyCount = group.slots.filter(s => s.status === 'busy').length;

                                    // Determine Color
                                    let borderColor = 'border-gray-200';
                                    let bgColor = 'bg-gray-50';
                                    let textColor = 'text-gray-800';

                                    if (isBusy) {
                                        if (busyCount >= capacity) {
                                            borderColor = 'border-red-200';
                                            bgColor = 'bg-red-50';
                                            textColor = 'text-red-900';
                                        } else if (busyCount > 0) {
                                            borderColor = 'border-yellow-200';
                                            bgColor = 'bg-yellow-50';
                                            textColor = 'text-yellow-900';
                                        } else {
                                            borderColor = 'border-green-200';
                                            bgColor = 'bg-green-50';
                                            textColor = 'text-green-900';
                                        }
                                    }

                                    return (
                                        <div
                                            key={`${group.start_at}-${group.end_at}`}
                                            className={`p-4 rounded-lg border flex items-center justify-between ${bgColor} ${borderColor} ${textColor}`}
                                        >
                                            <div>
                                                <div className="font-bold text-lg">
                                                    {formatTime(group.start_at)} - {formatTime(group.end_at)}
                                                </div>
                                                <div className="text-sm opacity-80 flex items-center gap-2">
                                                    <span className={`w-2 h-2 rounded-full ${isBusy ? (busyCount >= capacity ? 'bg-red-500' : 'bg-yellow-500') : 'bg-gray-500'}`}></span>
                                                    {isBusy
                                                        ? <span className="font-medium">Busy: {busyCount} / {capacity}</span>
                                                        : t('manualBlock')
                                                    }
                                                </div>
                                                {isBusy && group.slots.map(s => s.service_title).filter(Boolean).length > 0 && (
                                                    <div className="text-xs mt-1 opacity-70">
                                                        {Array.from(new Set(group.slots.map(s => s.service_title).filter(Boolean))).join(', ')}
                                                    </div>
                                                )}
                                            </div>

                                            {!isBusy && (
                                                <button
                                                    onClick={() => handleDelete(firstSlot.id)}
                                                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-white rounded-lg transition-colors border border-transparent hover:border-gray-200"
                                                    title={t('delete')}
                                                >
                                                    ✕
                                                </button>
                                            )}
                                            {isBusy && (
                                                <div className="p-2 opacity-50 cursor-not-allowed" title={t('locked')}>
                                                    🔒
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
