export const ENDPOINTS = {
    // Auth
    LOGIN: "/auth/login/",
    REGISTER: "/auth/register/",
    REFRESH: "/auth/refresh/",
    LOGOUT: "/auth/logout/",
    PROFILE_ME: "/profile/me/", // Standardized profile endpoint

    // Catalog
    CATEGORIES: "/categories/",
    SERVICES: "/services/",
    GEO_GEOCODE: "/geo/geocode/",
    GEO_REVERSE_GEOCODE: "/geo/reverse-geocode/",

    // Marketplace
    REQUESTS: "/requests/",
    OFFERS: "/offers/",
    ORDERS: "/orders/",
    CHATS: "/chats/",

    // Actions
    ORDER_REVIEW: (id: string | number) => `/orders/${id}/review/`,
    ORDER_REVIEW_REPLY: (id: string | number) => `/orders/${id}/review/reply/`,
    CHAT_MESSAGES: (id: string | number) => `/chats/${id}/messages/`,
    CHAT_MARK_READ: (id: string | number) => `/chats/${id}/mark-read/`,

    // Notifications
    NOTIFICATIONS: "/notifications/",
    NOTIFICATIONS_UNREAD_COUNT: "/notifications/unread-count/",
    NOTIFICATIONS_MARK_ALL_READ: "/notifications/mark-all-read/",
    NOTIFICATION_MARK_READ: (id: string | number) => `/notifications/${id}/mark-read/`,

    // Favorites
    FAVORITES: "/favorites/",
    FAVORITES_TOGGLE: "/favorites/toggle/",
    FAVORITES_CHECK: "/favorites/check/",

    // Portfolio
    PORTFOLIO_ITEMS: "/portfolio/items/",
    PORTFOLIO_MEDIA: "/portfolio/media/",
    PROVIDERS: "/providers/",
    COMMENTS: "/comments/",
    REPORTS: "/reports/",
    REPORTS_MY: "/reports/my/",

    // Availability
    AVAILABILITY: "/availability/",
    AVAILABILITY_MY: "/availability/my/",

    // Billing
    BILLING_PLANS: "/billing/plans/",
    BILLING_SUBSCRIPTION: "/billing/subscription/",
    BILLING_SUBSCRIPTION_CURRENT: "/billing/subscription/current/",
    BILLING_SUBSCRIBE: "/billing/subscribe/",
    BILLING_PROMO_VALIDATE: "/billing/promo/validate/",
    BILLING_MOCK_ACTIVATE: "/billing/subscription/mock-activate/",
    BILLING_CHECKOUT: "/billing/subscription/checkout/",
    BILLING_PAYMENTS: "/billing/subscription/payments/",
    BILLING_PAYMENT_STATUS: (paymentId: string | number) => `/billing/subscription/payments/${paymentId}/status/`,

    // AI
    AI_REQUEST_ASSISTANT: "/ai/request-assistant/",
    AI_OFFER_ASSISTANT: "/ai/offer-assistant/",

    // Payments
    PAYMENT_CREATE: (orderId: string | number) => `/payments/orders/${orderId}/create/`,
    PAYMENT_STATUS: (orderId: string | number) => `/payments/orders/${orderId}/status/`,
    PAYMENT_QUOTE: (orderId: string | number) => `/payments/orders/${orderId}/quote/`,

    // PayPal capture
    PAYPAL_ORDER_CAPTURE: "/payments/paypal/capture/",
    PAYPAL_BILLING_CAPTURE: "/billing/paypal/capture/",

    // Billing quote
    BILLING_SUBSCRIPTION_QUOTE: "/billing/subscription/quote/",
} as const;

// Type exports for compile-time safety
export type EndpointKey = keyof typeof ENDPOINTS;
export type EndpointValue = typeof ENDPOINTS[EndpointKey];

// Portfolio URL Helpers
export const portfolioItemUrl = (id: string | number) => `${ENDPOINTS.PORTFOLIO_ITEMS}${id}/`;
export const portfolioItemMediaAddUrl = (itemId: string | number) => `${ENDPOINTS.PORTFOLIO_ITEMS}${itemId}/media/`;
export const portfolioMediaDeleteUrl = (mediaId: string | number) => `${ENDPOINTS.PORTFOLIO_MEDIA}${mediaId}/`;
export const portfolioMediaReplaceUrl = (mediaId: string | number) => `${ENDPOINTS.PORTFOLIO_MEDIA}${mediaId}/replace/`;
export const providerPortfolioUrl = (providerId: string | number) => `/portfolio/providers/${providerId}/portfolio/`;

// Provider URL Helpers
export const providerUrl = (id: string | number) => `${ENDPOINTS.PROVIDERS}${id}/`;
export const providerReviewsUrl = (providerId: string | number) => `${ENDPOINTS.PROVIDERS}${providerId}/reviews/`;
export const providerBlockUrl = (id: string | number) => `${ENDPOINTS.PROVIDERS}${id}/block/`;
export const providerUnblockUrl = (id: string | number) => `${ENDPOINTS.PROVIDERS}${id}/unblock/`;

// Comments URL Helpers
export const serviceCommentsUrl = (serviceId: string | number) => `${ENDPOINTS.SERVICES}${serviceId}/comments/`;
export const commentUrl = (commentId: string | number) => `${ENDPOINTS.COMMENTS}${commentId}/`;

// Reports URL Helpers
export const reportStatusUrl = (id: string | number) => `${ENDPOINTS.REPORTS}${id}/status/`;
export const reportInReviewUrl = (id: string | number) => `${ENDPOINTS.REPORTS}${id}/set-in-review/`;
export const reportResolveUrl = (id: string | number) => `${ENDPOINTS.REPORTS}${id}/resolve/`;
export const reportRejectUrl = (id: string | number) => `${ENDPOINTS.REPORTS}${id}/reject/`;

// Billing URL Helpers
export const billingPlanUrl = (id: string | number) => `${ENDPOINTS.BILLING_PLANS}${id}/`;

// Chat URL Helpers
export const chatUrl = (id: string | number) => `${ENDPOINTS.CHATS}${id}/`;

// Services URL Helpers
export const serviceUrl = (id: string | number) => `${ENDPOINTS.SERVICES}${id}/`;
export const serviceCoverUrl = (serviceId: string | number) => `${ENDPOINTS.SERVICES}${serviceId}/cover/`;
export const userAvatarUrl = () => `${ENDPOINTS.PROFILE_ME}avatar/`;


// Orders URL Helpers
export const orderUrl = (id: string | number) => `${ENDPOINTS.ORDERS}${id}/`;
export const orderQrCodeUrl = (id: string | number) => `${ENDPOINTS.ORDERS}${id}/qr-code/`;

// Offers URL Helpers
export const offerAcceptUrl = (id: string | number) => `${ENDPOINTS.OFFERS}${id}/accept/`;

// Availability URL Helpers
export const availabilityUrl = (id: string | number) => `${ENDPOINTS.AVAILABILITY}${id}/`;

// Payment URL Helpers
export const paymentCreateUrl = (orderId: string | number) => ENDPOINTS.PAYMENT_CREATE(orderId);
export const paymentStatusUrl = (orderId: string | number) => ENDPOINTS.PAYMENT_STATUS(orderId);
export const billingPaymentStatusUrl = (paymentId: string | number) => ENDPOINTS.BILLING_PAYMENT_STATUS(paymentId);

