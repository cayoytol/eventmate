"use client";

import { use, useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS, chatUrl } from "@/lib/api/endpoints";
import { useAuthStore } from "@/store/useAuthStore";
import type { Chat, ChatMessage } from "@/types/chat";
import { Button } from "@/components/ui/Button";

const POLLING_INTERVAL = 3000;

export default function ProviderChatDetailPage(props: { params: Promise<{ id: string }> }) {
    const params = use(props.params);
    const { id } = params;

    const router = useRouter();
    const locale = useLocale();
    const t = useTranslations("dashboard.chatDetail");
    const { user } = useAuthStore();

    const [chat, setChat] = useState<Chat | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [newMessage, setNewMessage] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        if (!user) return;

        const initChat = async () => {
            try {
                await fetchChat();
                await fetchMessages();
            } catch (error) {
                console.error("Error initializing chat:", error);
            } finally {
                setIsLoading(false);
            }
        };

        initChat();

        pollingIntervalRef.current = setInterval(() => {
            fetchMessages(true);
        }, POLLING_INTERVAL);

        return () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, [id, user]);

    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages.length]);

    const fetchChat = async () => {
        const { data } = await api.get<Chat>(chatUrl(id));
        setChat(data);
    };

    const fetchMessages = async (silent = false) => {
        try {
            const { data } = await api.get<ChatMessage[]>(ENDPOINTS.CHAT_MESSAGES(id));

            setMessages(prev => {
                if (prev.length !== data.length) return data;
                if (prev.length > 0 && data.length > 0 && prev[prev.length - 1].id !== data[data.length - 1].id) return data;
                return prev.length === data.length ? prev : data;
            });

            if (!silent) {
                await api.post(ENDPOINTS.CHAT_MARK_READ(id));
            }
        } catch (err) {
            console.error("Failed to fetch messages:", err);
        }
    };

    const sendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newMessage.trim() || isSending) return;

        const tempContent = newMessage;
        setNewMessage("");
        setIsSending(true);

        try {
            await api.post(ENDPOINTS.CHAT_MESSAGES(id), {
                content: tempContent
            });
            await fetchMessages(true);
        } catch (err) {
            console.error("Failed to send:", err);
            setNewMessage(tempContent);
            alert(t("sendError"));
        } finally {
            setIsSending(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-[calc(100vh-150px)]">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
            </div>
        );
    }

    if (!chat) {
        return (
            <div className="flex items-center justify-center h-[calc(100vh-150px)] text-red-500 font-semibold">
                {t("notFound")}
            </div>
        );
    }

    const counterpartName = chat.client_email;

    return (
        <div className="flex flex-col h-[calc(100vh-110px)] bg-neutral-50/50 rounded-2xl border border-neutral-100 overflow-hidden shadow-sm">
            {/* Header */}
            <div className="bg-white border-b border-neutral-100 px-6 py-4 flex items-center justify-between z-10">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.push(`/${locale}/provider/chats`)}
                        className="p-2 hover:bg-neutral-50 rounded-full text-neutral-500 hover:text-neutral-800 transition"
                    >
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                        </svg>
                    </button>
                    <div className="w-10 h-10 rounded-full bg-violet-50 flex items-center justify-center text-violet-600 font-bold">
                        {counterpartName?.[0]?.toUpperCase() || ""}
                    </div>
                    <div>
                        <h1 className="font-bold text-neutral-900 leading-tight">{counterpartName}</h1>
                        {chat.order && (
                            <span
                                onClick={() => router.push(`/${locale}/provider/orders/${chat.order}`)}
                                className="text-xs text-violet-600 hover:text-violet-850 font-semibold hover:underline cursor-pointer transition mt-0.5 inline-block"
                            >
                                {t("viewOrder")} #{chat.order}
                            </span>
                        )}
                        {!chat.order && chat.request && (
                            <span
                                onClick={() => router.push(`/${locale}/provider/requests/${chat.request}`)}
                                className="text-xs text-violet-600 hover:text-violet-850 font-semibold hover:underline cursor-pointer transition mt-0.5 inline-block"
                            >
                                {t("viewRequest")} #{chat.request}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={messagesContainerRef}>
                {messages.length === 0 && (
                    <div className="text-center text-neutral-400 py-10 font-medium">
                        {t("startConversation")}
                    </div>
                )}

                {messages.map((msg) => {
                    const isSystem = msg.is_system;
                    const isMe = msg.sender === user?.id;

                    if (isSystem) {
                        return (
                            <div key={msg.id} className="flex justify-center my-4">
                                <span className="bg-neutral-100 border border-neutral-200/50 text-neutral-550 text-xs px-3 py-1 rounded-full font-medium">
                                    {msg.content}
                                </span>
                            </div>
                        );
                    }

                    return (
                        <div key={msg.id} className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[75%] px-4 py-2.5 rounded-2xl shadow-sm leading-relaxed ${isMe
                                    ? 'bg-violet-600 text-white rounded-br-none'
                                    : 'bg-white text-neutral-800 border border-neutral-100/80 rounded-bl-none'
                                }`}>
                                <p className="whitespace-pre-wrap break-words text-sm">{msg.content}</p>
                                <div className={`text-[10px] mt-1.5 text-right font-medium flex items-center justify-end gap-1 ${isMe ? 'text-violet-100' : 'text-neutral-400'
                                    }`}>
                                    <span>
                                        {new Date(msg.created_at).toLocaleTimeString(locale, {
                                            hour: '2-digit',
                                            minute: '2-digit'
                                        })}
                                    </span>
                                    {isMe && (
                                        <span>
                                            {msg.read_at ? '✓✓' : '✓'}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <form onSubmit={sendMessage} className="bg-white border-t border-neutral-100 p-4 flex gap-3 z-10">
                <input
                    type="text"
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    placeholder={t("placeholder")}
                    className="flex-1 border border-neutral-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500 transition-all outline-none text-sm placeholder-neutral-400"
                    disabled={isSending}
                />
                <Button
                    type="submit"
                    disabled={!newMessage.trim()}
                    isLoading={isSending}
                    className="!px-5 shrink-0"
                >
                    {!isSending && (
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                            <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                        </svg>
                    )}
                </Button>
            </form>
        </div>
    );
}

