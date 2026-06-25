// frontend/src/types/marketplace.ts

export type EventRequestStatus = 'open' | 'offers' | 'confirmed' | 'completed' | 'cancelled';

export type EventRequest = {
    id: number;
    client: {
        id: number;
        email: string;
    };
    category: {
        id: number;
        name_ru: string;
        name_en: string;
        name_kz: string;
    };
    title: string;
    description: string;
    city: string;
    event_date: string; // ISO date
    event_start_at: string; // ISO datetime
    budget_min: number;
    budget_max: number;
    status: EventRequestStatus;
    created_at: string;
    offers_count: number;
};

export type OfferStatus = 'sent' | 'accepted' | 'rejected';

export type Offer = {
    id: number;
    provider: {
        id: number;
        user: {
            email: string;
            first_name?: string;
            last_name?: string;
        };
        rating_avg: number | null;
    };
    price: number;
    message: string;
    delivery_date: string;
    status: OfferStatus;
    created_at: string;
};

export type OrderStatus = 'pending_payment' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled' | 'disputed';
export type PaymentStatus = 'unpaid' | 'paid' | 'failed';

export interface OrderQrCapabilities {
    is_client_owner: boolean;
    is_assigned_provider: boolean;
    can_generate_start: boolean;
    can_generate_finish: boolean;
    can_check_in: boolean;
    can_complete: boolean;
}

export type Order = {
    id: number;
    status: OrderStatus;
    payment_status: PaymentStatus;
    price_agreed: string; // Decimal as string from backend
    provider: {
        id: number;
        user: {
            email: string;
            first_name?: string;
            last_name?: string;
        };
    };
    client_email: string;
    service_snapshot: any; // JSON snapshot of service
    checkin_at?: string;
    completed_at?: string;
    created_at: string;
    // Legacy fields (may be used in detail view)
    request?: {
        id: number;
        title: string;
        event_date: string;
    };
    event_date?: string;
    qr_code_url?: string;
    qr_token?: string;
    qr_capabilities?: OrderQrCapabilities;
    review?: {
        id: number;
        rating: number;
        text: string;
        provider_reply: string;
        client_name: string;
        created_at: string;
    } | null;
};

export type PaginatedResponse<T> = {
    count: number;
    next: string | null;
    previous: string | null;
    results: T[];
};

// Aliases to resolve legacy import references in chat components
import type { Chat, ChatMessage as ChatMessageOrig } from './chat';
export type ChatListItem = Chat;
export type ChatMessage = ChatMessageOrig;
