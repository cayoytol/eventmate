export interface Notification {
    id: number;
    title: string;
    message: string;
    type: 'new_request' | 'new_offer' | 'offer_accepted' | 'offer_rejected' | 'order_created' | 'order_paid' | 'order_completed' | 'new_review' | 'provider_reply';
    payload: Record<string, any>;
    is_read: boolean;
    created_at: string;
}

export interface UnreadCountResponse {
    unread_count: number;
}
