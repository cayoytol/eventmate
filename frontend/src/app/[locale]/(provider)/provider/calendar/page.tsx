"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import MonthView from "@/components/calendar/MonthView";
import DayView from "@/components/calendar/DayView";

export default function ProviderCalendarPage() {
    const t = useTranslations("provider.calendar");
    const [view, setView] = useState<'month' | 'day'>('month');
    const [selectedDate, setSelectedDate] = useState<Date | null>(null);

    const handleDateSelect = (date: Date) => {
        setSelectedDate(date);
        setView('day');
    };

    const handleBack = () => {
        setView('month');
        setSelectedDate(null);
    };

    return (
        <div className="p-6">
            <h1 className="text-3xl font-bold mb-8">{t('title')}</h1>

            {view === 'month' ? (
                <MonthView onSelectDate={handleDateSelect} />
            ) : (
                selectedDate && <DayView date={selectedDate} onBack={handleBack} />
            )}
        </div>
    );
}
