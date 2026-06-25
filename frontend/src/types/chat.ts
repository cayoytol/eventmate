export interface Chat {
    id: number;
    request: number | null;
    order: number | null;
    client: number;
    client_email: string;
    provider: number;
    provider_email: string;
    provider_name: string;
    created_at: string;
    updated_at: string;
    last_message: {
        content: string;
        created_at: string;
        sender_email: string;
        is_system: boolean;
    } | null;
    unread_count: number;
}

export interface ChatMessage {
    id: number;
    chat: number;
    sender: number | null;
    sender_email: string | null;
    content: string;
    attachment_url: string;
    is_system: boolean;
    read_at: string | null;
    created_at: string;
}
