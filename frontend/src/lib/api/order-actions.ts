import { ENDPOINTS } from "./endpoints";

/**
 * Builds the URL for checking in an order (Provider scans Start QR)
 */
export const orderCheckInUrl = (id: number | string) =>
    `${ENDPOINTS.ORDERS}${id}/actions/check-in/`;

/**
 * Builds the URL for completing an order (Provider scans Finish QR)
 */
export const orderCompleteUrl = (id: number | string) =>
    `${ENDPOINTS.ORDERS}${id}/actions/complete/`;

/**
 * Builds the URL for cancellation
 */
export const orderCancelUrl = (id: number | string) =>
    `${ENDPOINTS.ORDERS}${id}/actions/cancel/`;

/**
 * Builds the URL for mock payment (DEV ONLY)
 */
export const orderMockPayUrl = (id: number | string) =>
    `${ENDPOINTS.ORDERS}${id}/actions/mock-pay/`;
