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

export default function ProviderChatsPage() {
    const router = useRouter();
    const locale = useLocale();
    const t = useTranslations("dashboard.chats"); // Re-using dashboard translations
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
            <div>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-neutral-900 tracking-tight">{t("title")}</h1>
            </div>

            {chats.length === 0 ? (
                <EmptyState
                    title={t("empty")}
                    description={locale === 'en' ? 'Direct messages from clients regarding event requests and active orders will appear here.' : 'Здесь будут отображаться сообщения от клиентов касательно заказов или предложений.'}
                />
            ) : (
                <div className="grid grid-cols-1 gap-3">
                    {chats.map(chat => {
                        const counterpartName = chat.client_email;

                        return (
                            <Card
                                key={chat.id}
                                onClick={() => router.push(`/${locale}/provider/chats/${chat.id}`)}
                                className="hover:border-violet-100 cursor-pointer transition flex items-center gap-4 p-4 !shadow-sm"
                                hoverable
                            >
                                <div className="w-12 h-12 rounded-full bg-violet-50 flex items-center justify-center text-lg font-bold text-violet-600 shrink-0">
                                    {counterpartName?.[0]?.toUpperCase() || '?'}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex justify-between items-start mb-1">
                                        <h3 className="font-semibold text-neutral-850 truncate pr-2">
                                            {counterpartName}
                                        </h3>
                                        {chat.last_message && (
                                            <span className="text-xs text-neutral-400 font-medium whitespace-nowrap">
                                                {new Date(chat.last_message.created_at).toLocaleDateString(locale, {
                                                    day: 'numeric',
                                                    month: 'short'
                                                })}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex justify-between items-end">
                                        <p className="text-sm text-neutral-500 truncate pr-4">
                                            {chat.last_message ? (
                                                chat.last_message.is_system ?
                                                    <span className="italic text-neutral-450">System: {chat.last_message.content}</span> :
                                                    chat.last_message.content
                                            ) : (
                                                <span className="text-neutral-400 italic">{t("noMessages")}</span>
                                            )}
                                        </p>
                                        {chat.unread_count > 0 && (
                                            <span className="bg-violet-600 text-white text-xs font-bold px-2 py-0.5 rounded-full min-w-[20px] text-center">
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

