"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS } from "@/lib/api/endpoints";
import type { ChatListItem } from "@/types/marketplace";

export default function ChatList({ basePath }: { basePath: string }) {
    const locale = useLocale();
    const t = useTranslations("chats");
    const [chats, setChats] = useState<ChatListItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchChats = async () => {
            try {
                // API might return array or PaginatedResponse, handling both
                const { data } = await api.get<ChatListItem[] | { results: ChatListItem[] }>(ENDPOINTS.CHATS);
                const list = Array.isArray(data) ? data : (data.results ?? []);
                setChats(list);
            } catch (err) {
                setError(t("error", { fallback: "Failed to load chats." }));
            } finally {
                setIsLoading(false);
            }
        };

        fetchChats();
    }, [t]);

    if (isLoading) {
        return (
            <div className="flex justify-center items-center py-12 text-neutral-500">
                {t("loading", { fallback: "Loading..." })}
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 text-red-700 p-4 rounded-xl mb-4">
                {error}
            </div>
        );
    }

    const safeChats = Array.isArray(chats) ? chats : [];

    if (safeChats.length === 0) {
        return (
            <div className="text-center py-12 bg-white rounded-2xl border">
                <div className="text-4xl mb-4">💬</div>
                <h3 className="text-lg font-medium text-neutral-900 mb-1">{t("empty", { fallback: "No chats yet" })}</h3>
                <p className="text-neutral-500">{t("noMessages", { fallback: "When you contact someone, your messages will appear here." })}</p>
            </div>
        );
    }

    const formatDate = (dateStr: string) => {
        if (!dateStr) return "—";
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return "—";
        return new Intl.DateTimeFormat(locale, {
            hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short'
        }).format(date);
    };

    return (
        <div className="bg-white rounded-2xl border overflow-hidden">
            <div className="divide-y">
                {safeChats.map(chat => (
                    <Link
                        key={chat.id}
                        href={`/${locale}${basePath}/${chat.id}`}
                        className="block p-4 hover:bg-neutral-50 transition"
                    >
                        <div className="flex justify-between items-start mb-1">
                            <h3 className="font-semibold text-neutral-900">
                                {chat.request ? `Request #${chat.request}` : `Order #${chat.order}`}
                                <span className="ml-2 font-normal text-sm text-neutral-500">
                                    {chat.provider_name || chat.provider_email}
                                </span>
                            </h3>
                            <div className="flex items-center gap-2 text-sm text-neutral-400">
                                {formatDate(chat.updated_at)}
                                {chat.unread_count > 0 && (
                                    <span className="bg-blue-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                                        {chat.unread_count}
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="text-sm text-neutral-600 truncate">
                            {chat.last_message ? (
                                <>
                                    <span className="font-medium mr-1">
                                        {chat.last_message.is_system ? 'System:' : `${chat.last_message.sender_email}:`}
                                    </span>
                                    {chat.last_message.content}
                                </>
                            ) : (
                                <span className="italic">{t("noMessages", { fallback: "No messages yet." })}</span>
                            )}
                        </div>
                    </Link>
                ))}
            </div>
        </div>
    );
}
