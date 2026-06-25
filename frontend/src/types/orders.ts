
import type { OrderQrCapabilities } from './marketplace';

export type OrderStatus =
    | 'confirmed'
    | 'in_progress'
    | 'completed'
    | 'cancelled'
    | 'disputed';

export type ProviderMin = {
    id: number;
    email: string;
    avatar_url: string | null;
};

export type PaymentStatus = 'unpaid' | 'paid' | 'failed';

export type OrderListItem = {
    id: number;
    status: OrderStatus;
    payment_status: PaymentStatus;
    price_agreed: string; // Decimal from backend
    provider: ProviderMin;
    client_email: string;
    created_at: string; // ISO date string
};

export type OrderDetail = OrderListItem & {
    service_snapshot?: {
        title: string;
        category_name: string;
        city: string;
    };
    checkin_at?: string | null;
    completed_at?: string | null;
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

export type QrCodeResponse = {
    token: string;
    expires_at: string; // ISO date string
};
