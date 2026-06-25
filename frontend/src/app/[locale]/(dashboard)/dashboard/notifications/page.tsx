// frontend/src/app/[locale]/(dashboard)/dashboard/notifications/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { Notification } from "@/types/notifications";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function NotificationsPage() {
    const locale = useLocale();
    const t = useTranslations("notifications");
    const tCommon = useTranslations("common");

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
                return "bg-emerald-50 text-emerald-700 border-emerald-100";
            case "new_offer":
            case "offer_accepted":
                return "bg-violet-50 text-violet-700 border-violet-100";
            case "new_request":
                return "bg-amber-50 text-amber-700 border-amber-100";
            case "new_review":
            case "provider_reply":
                return "bg-purple-50 text-purple-700 border-purple-100";
            case "offer_rejected":
                return "bg-rose-50 text-rose-700 border-rose-100";
            default:
                return "bg-slate-50 text-slate-600 border-slate-200";
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="max-w-4xl mx-auto py-12 px-4 text-center">
                <Card className="bg-red-50 text-red-800 p-6 border border-red-200 inline-block max-w-md rounded-2xl">
                    <p className="font-semibold mb-2">{error}</p>
                    <Button onClick={fetchNotifications} variant="outline" size="sm">
                        {tCommon("retry")}
                    </Button>
                </Card>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-white p-6 border border-slate-200 rounded-2xl shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">{t("title")}</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        {locale === 'en' ? 'Manage your updates, offers, payments, and event status changes.' : 'Управляйте вашими обновлениями, предложениями, платежами и изменениями статусов.'}
                    </p>
                </div>
                {notifications.some(n => !n.is_read) && (
                    <Button
                        onClick={handleMarkAllRead}
                        variant="outline"
                        size="sm"
                        className="shrink-0 self-start sm:self-auto"
                    >
                        {t("markAllRead")}
                    </Button>
                )}
            </div>

            {notifications.length === 0 ? (
                <EmptyState
                    title={t("empty")}
                    description={t("emptyDescription")}
                />
            ) : (
                <div className="grid grid-cols-1 gap-4">
                    {notifications.map(notif => (
                        <Card
                            key={notif.id}
                            className={`relative border border-slate-200 p-5 transition flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-2xl shadow-xs ${
                                !notif.is_read ? "border-l-4 border-l-violet-600 bg-violet-50/10" : "bg-white"
                            }`}
                        >
                            <div className="flex-1 min-w-0">
                                <div className="flex flex-wrap items-center gap-2.5 mb-2.5">
                                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 border rounded-full ${getBadgeStyle(notif.type)}`}>
                                        {t(`type.${notif.type}`)}
                                    </span>
                                    <span className="text-xs text-slate-450 font-semibold">
                                        {new Date(notif.created_at).toLocaleString(locale, {
                                            day: "numeric",
                                            month: "short",
                                            hour: "2-digit",
                                            minute: "2-digit"
                                        })}
                                    </span>
                                </div>
                                <h3 className="font-extrabold text-slate-900 mb-1 tracking-tight leading-tight">{notif.title}</h3>
                                <p className="text-sm text-slate-650 leading-relaxed">{notif.message}</p>
                            </div>

                            {!notif.is_read && (
                                <div className="flex items-center shrink-0">
                                    <Button
                                        onClick={() => handleMarkRead(notif.id)}
                                        variant="outline"
                                        size="sm"
                                        className="w-full md:w-auto"
                                    >
                                        {t("markRead")}
                                    </Button>
                                </div>
                            )}
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
