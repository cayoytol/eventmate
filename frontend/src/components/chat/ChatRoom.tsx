"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { ENDPOINTS, chatUrl } from "@/lib/api/endpoints";
import type { ChatMessage, ChatListItem, PaginatedResponse } from "@/types/marketplace";
import { useAuthStore } from "@/store/useAuthStore";

function normalizeMessages(data: ChatMessage[] | PaginatedResponse<ChatMessage>): ChatMessage[] {
    return Array.isArray(data) ? data : (data.results ?? []);
}

export default function ChatRoom({ id, basePath }: { id: string, basePath: string }) {
    const locale = useLocale();
    const user = useAuthStore((s) => s.user);
    const t = useTranslations("chats");
    const [chat, setChat] = useState<ChatListItem | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputText, setInputText] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [isSending, setIsSending] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Initial load
    useEffect(() => {
        let isMounted = true;
        const fetchChat = async () => {
            try {
                const chatRes = await api.get<ChatListItem>(chatUrl(id));
                if (!isMounted) return;
                setChat(chatRes.data);
                
                const msgsRes = await api.get<ChatMessage[] | PaginatedResponse<ChatMessage>>(ENDPOINTS.CHAT_MESSAGES(id));
                if (!isMounted) return;
                
                const msgList = normalizeMessages(msgsRes.data);
                setMessages(msgList);
                
                // Mark read
                await api.post(ENDPOINTS.CHAT_MARK_READ(id));
            } catch (err) {
                console.error("Failed to load chat", err);
            } finally {
                if (isMounted) setIsLoading(false);
            }
        };

        fetchChat();

        return () => { isMounted = false; };
    }, [id]);

    // Polling every 3 seconds
    useEffect(() => {
        if (isLoading) return;
        const interval = setInterval(async () => {
            try {
                const msgsRes = await api.get<ChatMessage[] | PaginatedResponse<ChatMessage>>(ENDPOINTS.CHAT_MESSAGES(id));
                const msgList = normalizeMessages(msgsRes.data);
                setMessages(msgList);
                
                // If there are unread, mark read
                const hasUnread = msgList.some(m => !m.read_at && m.sender_email !== user?.email);
                if (hasUnread) {
                     await api.post(ENDPOINTS.CHAT_MARK_READ(id));
                }
            } catch (err) {
                // Ignore polling errors
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [id, isLoading, chat, user?.email]);

    // Scroll to bottom on messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async () => {
        if (!inputText.trim()) return;
        setIsSending(true);
        try {
            await api.post(ENDPOINTS.CHAT_MESSAGES(id), { content: inputText.trim() });
            setInputText("");
            
            // Refetch immediately
            const msgsRes = await api.get<ChatMessage[] | PaginatedResponse<ChatMessage>>(ENDPOINTS.CHAT_MESSAGES(id));
            const msgList = normalizeMessages(msgsRes.data);
            setMessages(msgList);
        } catch (err) {
            console.error("Failed to send message", err);
        } finally {
            setIsSending(false);
        }
    };


    if (isLoading) {
        return <div className="text-center py-12 text-neutral-500">{t("loading", { fallback: "Loading chat..." })}</div>;
    }

    if (!chat) {
        return <div className="text-center py-12 text-red-500">{t("error", { fallback: "Chat not found." })}</div>;
    }

    // A hack to know if a message is ours (simplified by checking if we are client or provider in this scope, but let's check email)
    // Wait, backend doesn't send "is_mine". We'll just compare with our profile?
    // Actually, we can get current user email from global auth state or token, but let's just use a trick:
    // We can infer my email if I am the one sending the message, or we can use `useAuthStore` to get current user.
    return (
        <div className="flex flex-col h-[70vh] bg-white rounded-2xl border">
            {/* Header */}
            <div className="p-4 border-b flex items-center justify-between">
                <div>
                    <h2 className="font-bold text-lg">
                        {chat.request ? `Request #${chat.request}` : `Order #${chat.order}`}
                    </h2>
                    <div className="text-sm text-neutral-500">
                        {chat.provider_name || chat.provider_email}
                    </div>
                </div>
                <Link href={`/${locale}${basePath}`} className="text-sm text-neutral-500 hover:text-black transition">
                    {t("back", { fallback: "Back to chats" })}
                </Link>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {(() => {
                    const safeMessages = Array.isArray(messages) ? messages : [];
                    if (safeMessages.length === 0) {
                        return (
                            <div className="text-center text-neutral-500 h-full flex items-center justify-center">
                                {t("noMessages", { fallback: "No messages yet. Say hi!" })}
                            </div>
                        );
                    }
                    return safeMessages.map((msg) => {
                        if (msg.is_system) {
                            return (
                                <div key={msg.id} className="text-center text-xs text-neutral-400 my-2">
                                    {msg.content}
                                </div>
                            );
                        }
                        // Compare message sender email with current logged-in user email if available, otherwise fall back to view-type detection
                        const isClientView = basePath.includes("/dashboard");
                        const isMine = user?.email
                            ? msg.sender_email === user.email
                            : (isClientView 
                                ? msg.sender_email === chat.client_email 
                                : msg.sender_email === chat.provider_email);

                        return (
                            <div key={msg.id} className={`flex flex-col ${isMine ? "items-end" : "items-start"}`}>
                                <div className="text-xs text-neutral-500 mb-1">{msg.sender_email}</div>
                                <div className={`px-4 py-2 rounded-2xl max-w-[80%] ${isMine ? "bg-black text-white rounded-tr-sm" : "bg-neutral-100 text-neutral-900 rounded-tl-sm"}`}>
                                    {msg.content}
                                </div>
                                <div className="text-[10px] text-neutral-400 mt-1">
                                    {(() => {
                                        if (!msg.created_at) return "—";
                                        const d = new Date(msg.created_at);
                                        if (isNaN(d.getTime())) return "—";
                                        return d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
                                    })()}
                                    {isMine && (msg.read_at ? " ✓✓" : " ✓")}
                                </div>
                            </div>
                        );
                    });
                })()}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t bg-neutral-50">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder={t("typeMessage", { fallback: "Type a message..." })}
                        className="flex-1 rounded-xl border border-neutral-300 px-4 py-2 focus:ring-2 focus:ring-black outline-none text-sm"
                        disabled={isSending}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!inputText.trim() || isSending}
                        className="bg-black text-white px-6 py-2 rounded-xl font-medium text-sm disabled:opacity-50 transition"
                    >
                        {isSending ? "..." : t("send", { fallback: "Send" })}
                    </button>
                </div>
            </div>
        </div>
    );
}
