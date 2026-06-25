// frontend/src/app/[locale]/(dashboard)/dashboard/chats/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { Chat } from "@/types/chat";
import { useAuthStore } from "@/store/useAuthStore";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

export default function ChatsPage() {
    const router = useRouter();
    const locale = useLocale();
    const t = useTranslations("dashboard.chats");
    const { user } = useAuthStore();

    const [chats, setChats] = useState<Chat[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        if (user) {
            fetchChats();
        }
    }, [user]);

    const fetchChats = async () => {
        try {
            const { data } = await api.get<Chat[]>(ENDPOINTS.CHATS);
            setChats(data);
        } catch (err) {
            console.error("Failed to load chats:", err);
        } finally {
            setIsLoading(false);
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-12 flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-white p-6 border border-slate-200 rounded-2xl shadow-xs">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">{t("title")}</h1>
                <p className="text-sm text-slate-500 mt-1">
                    {locale === 'en' ? 'Discuss your events, requests, and bookings with service providers.' : 'Обсуждайте ваши мероприятия, запросы и бронирования с исполнителями.'}
                </p>
            </div>

            {chats.length === 0 ? (
                <EmptyState
                    title={t("empty")}
                    description={locale === 'en' ? 'Start a conversation with a service provider to discuss your requests.' : 'Начните диалог с исполнителем для обсуждения деталей.'}
                />
            ) : (
                <div className="grid grid-cols-1 gap-4">
                    {chats.map(chat => {
                        const isClient = user?.role === 'client';
                        const counterpartName = isClient ? chat.provider_name || chat.provider_email : chat.client_email;

                        return (
                            <Card
                                key={chat.id}
                                onClick={() => router.push(`/${locale}/dashboard/chats/${chat.id}`)}
                                className="hover:border-violet-200 cursor-pointer transition flex items-center gap-4 p-5 rounded-2xl border border-slate-200 bg-white hover:shadow-md duration-200"
                            >
                                <div className="w-12 h-12 rounded-2xl bg-violet-50 flex items-center justify-center text-lg font-extrabold text-violet-600 shrink-0 border border-violet-100">
                                    {counterpartName?.[0]?.toUpperCase() || '?'}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex justify-between items-start mb-1.5">
                                        <h3 className="font-extrabold text-slate-900 tracking-tight truncate pr-2">
                                            {counterpartName}
                                        </h3>
                                        {chat.last_message && (
                                            <span className="text-xs text-slate-400 font-semibold whitespace-nowrap">
                                                {new Date(chat.last_message.created_at).toLocaleDateString(locale, {
                                                    day: 'numeric',
                                                    month: 'short'
                                                })}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex justify-between items-center gap-4">
                                        <div className="text-sm text-slate-500 truncate flex-1">
                                            {chat.last_message ? (
                                                chat.last_message.is_system ?
                                                    <span className="italic text-slate-400 bg-slate-50 border border-slate-100 px-2 py-0.5 rounded text-xs">System: {chat.last_message.content}</span> :
                                                    chat.last_message.content
                                            ) : (
                                                <span className="text-slate-400 italic">{t("noMessages")}</span>
                                            )}
                                        </div>
                                        {chat.unread_count > 0 && (
                                            <span className="bg-violet-600 text-white text-xs font-bold px-2.5 py-0.5 rounded-full min-w-[22px] text-center shadow-sm shadow-violet-100">
                                                {chat.unread_count}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
