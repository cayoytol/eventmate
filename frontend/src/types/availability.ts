export interface Availability {
    id: number;
    provider: number;
    start_at: string; // ISO datetime
    end_at: string;   // ISO datetime
    status: 'busy' | 'blocked';
    order?: number | null;
    order_capacity?: number;
    service_title?: string;
}
