// frontend/src/types/billing.ts

// Limits from Plan.limits_json
export interface BillingLimits {
    max_services: number;
    offers_per_month: number;
    [key: string]: number; // Allow unknown limits
}

// Plan from backend PlanSerializer
export interface Plan {
    id: number;
    code: string;
    name: string; // Resolved name from Accept-Language
    name_ru: string;
    name_en: string;
    name_kz: string;
    price: number;
    duration_days: number;
    limits_json: BillingLimits;
    is_active: boolean;
}

// Subscription from backend SubscriptionSerializer
export interface Subscription {
    id: number;
    provider: number;
    plan: Plan;
    status: string;
    effective_status: string;
    starts_at: string;
    ends_at: string;
    cancelled_at: string | null;
    auto_renew: boolean;
    remaining_days: number;
    is_active: boolean;
    is_currently_active: boolean;
    created_at: string;
}

// Response from GET /api/v1/billing/subscription/current/
export interface CurrentSubscriptionResponse {
    subscription: Subscription | null;
    plan: Plan;
    current_plan: Plan; // Compatibility alias
    entitlements: {
        max_active_services: number;
        max_portfolio_items: number;
        analytics: boolean;
        ai_features: boolean;
        featured_placement: boolean;
        offers_per_month: number;
    };
    is_fallback: boolean;
}

// PromoCode from backend PromoCodeSerializer
export interface PromoCode {
    id: number;
    code: string;
    discount_percent: number;
    max_uses: number;
    used_count: number;
    expires_at: string | null;
    is_active: boolean;
    is_valid: boolean;
    created_at: string;
}

// Input for promo validation
export interface PromoCodeValidationRequest {
    code: string;
}

// Error response shape
export interface BillingError {
    detail?: string;
    code?: string[];
    [key: string]: unknown;
}
