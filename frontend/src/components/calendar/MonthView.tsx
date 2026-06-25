"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { Availability } from "@/types/availability";

interface MonthViewProps {
    onSelectDate: (date: Date) => void;
}

export default function MonthView({ onSelectDate }: MonthViewProps) {
    const locale = useLocale();
    const t = useTranslations("provider.calendar");

    const [currentMonth, setCurrentMonth] = useState(new Date());
    const [availabilities, setAvailabilities] = useState<Availability[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        fetchMonthAvailability();
    }, [currentMonth]);

    const fetchMonthAvailability = async () => {
        setIsLoading(true);
        try {
            // Get first and last day of month
            const year = currentMonth.getFullYear();
            const month = currentMonth.getMonth();
            const firstDay = new Date(year, month, 1);
            const lastDay = new Date(year, month + 1, 0);

            const fromStr = firstDay.toISOString().split('T')[0];
            const toStr = lastDay.toISOString().split('T')[0];

            const { data } = await api.get<Availability[]>(ENDPOINTS.AVAILABILITY_MY, {
                params: { from: fromStr, to: toStr }
            });
            setAvailabilities(data);
        } catch (error) {
            console.error("Failed to fetch month availability", error);
        } finally {
            setIsLoading(false);
        }
    };

    const changeMonth = (offset: number) => {
        const newDate = new Date(currentMonth);
        newDate.setMonth(currentMonth.getMonth() + offset);
        setCurrentMonth(newDate);
    };

    const getDaysInMonth = () => {
        const year = currentMonth.getFullYear();
        const month = currentMonth.getMonth();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const firstDayOfWeek = new Date(year, month, 1).getDay(); // 0 = Sun, 1 = Mon...

        // Adjust for Monday start (default usually Sunday) if needed
        // Assuming Monday start for Russian/European locale standards or consistency
        const startOffset = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;

        const days = [];
        // Empty slots for previous month
        for (let i = 0; i < startOffset; i++) {
            days.push(null);
        }
        // Days of current month
        for (let i = 1; i <= daysInMonth; i++) {
            days.push(new Date(year, month, i));
        }
        return days;
    };

    const hasAvailability = (date: Date) => {
        // Check if there are any slots for this day
        const dayStr = date.toISOString().split('T')[0];
        const slots = availabilities.filter(a => a.start_at.startsWith(dayStr));

        const hasBusy = slots.some(s => s.status === 'busy');
        const hasBlocked = slots.some(s => s.status === 'blocked');

        return { hasBusy, hasBlocked, count: slots.length };
    };

    const weekDays = [
        t('weekDays.mon'),
        t('weekDays.tue'),
        t('weekDays.wed'),
        t('weekDays.thu'),
        t('weekDays.fri'),
        t('weekDays.sat'),
        t('weekDays.sun')
    ];

    return (
        <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <button
                    onClick={() => changeMonth(-1)}
                    className="px-4 py-2 border rounded-lg hover:bg-gray-50"
                >
                    {t('prevMonth')}
                </button>
                <h2 className="text-xl font-bold capitalize">
                    {currentMonth.toLocaleDateString(locale, { month: 'long', year: 'numeric' })}
                </h2>
                <button
                    onClick={() => changeMonth(1)}
                    className="px-4 py-2 border rounded-lg hover:bg-gray-50"
                >
                    {t('nextMonth')}
                </button>
            </div>

            {/* Legend */}
            <div className="flex gap-6 mb-6 text-sm">
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border rounded bg-white"></div>
                    <span>{t('legendFree')}</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gray-200"></div>
                    <span>{t('legendBlocked')}</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-red-200"></div>
                    <span>{t('legendBusy')}</span>
                </div>
            </div>

            {/* Grid */}
            <div className="border rounded-xl overflow-hidden bg-white shadow-sm">
                {/* Header */}
                <div className="grid grid-cols-7 border-b bg-gray-50">
                    {weekDays.map(day => (
                        <div key={day} className="py-3 text-center text-sm font-medium text-gray-500 border-r last:border-r-0">
                            {day}
                        </div>
                    ))}
                </div>

                {/* Days */}
                <div className="grid grid-cols-7">
                    {getDaysInMonth().map((date, idx) => {
                        if (!date) {
                            return <div key={`empty-${idx}`} className="h-32 border-b border-r bg-gray-50/30"></div>;
                        }

                        const { hasBusy, hasBlocked } = hasAvailability(date);
                        const isToday = new Date().toDateString() === date.toDateString();

                        return (
                            <button
                                key={date.toISOString()}
                                onClick={() => onSelectDate(date)}
                                className={`h-32 border-b border-r p-2 text-left transition-colors hover:bg-gray-50 relative flex flex-col items-end
                                    ${hasBusy ? 'bg-red-50 hover:bg-red-100' : ''}
                                    ${!hasBusy && hasBlocked ? 'bg-gray-100 hover:bg-gray-200' : ''}
                                `}
                            >
                                <span className={`
                                    text-sm font-medium p-1 rounded-full w-7 h-7 flex items-center justify-center
                                    ${isToday ? 'bg-black text-white' : 'text-gray-700'}
                                `}>
                                    {date.getDate()}
                                </span>

                                <div className="mt-auto w-full flex flex-col gap-1 items-start">
                                    {hasBusy && (
                                        <span className="text-[10px] bg-red-100 text-red-800 px-1.5 py-0.5 rounded w-full truncate text-left">
                                            {t('legendBusy')}
                                        </span>
                                    )}
                                    {hasBlocked && (
                                        <span className="text-[10px] bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded w-full truncate text-left">
                                            {t('manualBlock')}
                                        </span>
                                    )}
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
