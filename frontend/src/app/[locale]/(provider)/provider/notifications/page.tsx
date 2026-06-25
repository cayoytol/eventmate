"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { Notification } from "@/types/notifications";

export default function ProviderNotificationsPage() {
    const locale = useLocale();
    const t = useTranslations("notifications");

    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchNotifications();
    }, []);

    const fetchNotifications = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const { data } = await api.get<Notification[]>(ENDPOINTS.NOTIFICATIONS);
            setNotifications(data);
        } catch (err) {
            console.error("Failed to fetch notifications:", err);
            setError(t("error"));
        } finally {
            setIsLoading(false);
        }
    };

    const handleMarkRead = async (id: number) => {
        try {
            await api.post(ENDPOINTS.NOTIFICATION_MARK_READ(id));
            setNotifications(prev =>
                prev.map(notif => (notif.id === id ? { ...notif, is_read: true } : notif))
            );
            // Dispatch event to update unread count in header
            window.dispatchEvent(new Event("notificationReadUpdate"));
        } catch (err) {
            console.error("Failed to mark notification as read:", err);
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await api.post(ENDPOINTS.NOTIFICATIONS_MARK_ALL_READ);
            setNotifications(prev => prev.map(notif => ({ ...notif, is_read: true })));
            // Dispatch event to update unread count in header
            window.dispatchEvent(new Event("notificationReadUpdate"));
        } catch (err) {
            console.error("Failed to mark all as read:", err);
        }
    };

    const getBadgeStyle = (type: Notification["type"]) => {
        switch (type) {
            case "order_paid":
            case "order_completed":
                return "bg-emerald-50 text-emerald-700 border-emerald-200";
            case "new_offer":
            case "offer_accepted":
                return "bg-blue-50 text-blue-700 border-blue-200";
            case "new_request":
                return "bg-amber-50 text-amber-700 border-amber-200";
            case "new_review":
            case "provider_reply":
                return "bg-purple-50 text-purple-700 border-purple-200";
            case "offer_rejected":
                return "bg-rose-50 text-rose-700 border-rose-200";
            default:
                return "bg-neutral-50 text-neutral-700 border-neutral-200";
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-12 text-center text-neutral-500">
                <div className="animate-pulse space-y-4 max-w-4xl mx-auto px-4">
                    <div className="h-8 bg-neutral-200 rounded w-1/4 mb-8"></div>
                    <div className="h-20 bg-neutral-100 rounded-xl"></div>
                    <div className="h-20 bg-neutral-100 rounded-xl"></div>
                    <div className="h-20 bg-neutral-100 rounded-xl"></div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="max-w-4xl mx-auto py-12 px-4 text-center">
                <div className="bg-red-50 text-red-800 rounded-xl p-6 border border-red-200 inline-block">
                    <p className="font-semibold mb-2">{error}</p>
                    <button onClick={fetchNotifications} className="text-sm underline font-medium">
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto py-6 px-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                <h1 className="text-2xl font-bold text-neutral-900">{t("title")}</h1>
                {notifications.some(n => !n.is_read) && (
                    <button
                        onClick={handleMarkAllRead}
                        className="text-sm font-medium text-neutral-600 hover:text-neutral-900 bg-neutral-50 hover:bg-neutral-100 border border-neutral-200 px-4 py-2 rounded-xl transition"
                    >
                        {t("markAllRead")}
                    </button>
                )}
            </div>

            {notifications.length === 0 ? (
                <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-neutral-200">
                    <div className="w-16 h-16 bg-neutral-50 rounded-full flex items-center justify-center mx-auto mb-4 border">
                        <svg className="w-8 h-8 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                        </svg>
                    </div>
                    <p className="text-neutral-500 font-medium">{t("empty")}</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {notifications.map(notif => (
                        <div
                            key={notif.id}
                            className={`relative bg-white border rounded-xl p-4 transition flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                                !notif.is_read ? "border-l-4 border-l-blue-600 shadow-sm bg-blue-50/10" : ""
                            }`}
                        >
                            <div className="flex-1 min-w-0">
                                <div className="flex flex-wrap items-center gap-2 mb-1.5">
                                    <span className={`text-xs font-semibold px-2 py-0.5 border rounded-full ${getBadgeStyle(notif.type)}`}>
                                        {t(`type.${notif.type}`)}
                                    </span>
                                    <span className="text-xs text-neutral-400">
                                        {new Date(notif.created_at).toLocaleString(locale, {
                                            day: "numeric",
                                            month: "short",
                                            hour: "2-digit",
                                            minute: "2-digit"
                                        })}
                                    </span>
                                </div>
                                <h3 className="font-semibold text-neutral-900 mb-0.5">{notif.title}</h3>
                                <p className="text-sm text-neutral-600 leading-relaxed">{notif.message}</p>
                            </div>

                            {!notif.is_read && (
                                <div className="flex items-center shrink-0">
                                    <button
                                        onClick={() => handleMarkRead(notif.id)}
                                        className="text-xs font-medium text-blue-600 hover:text-blue-700 border border-blue-200 hover:border-blue-300 bg-blue-50/20 px-3 py-1.5 rounded-lg transition"
                                    >
                                        {t("markRead")}
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
