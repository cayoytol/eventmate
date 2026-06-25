import { api } from '@/lib/api';
import {
    portfolioItemMediaAddUrl,
    portfolioMediaReplaceUrl,
    portfolioMediaDeleteUrl
} from './endpoints';

/**
 * Uploads a binary media file to a portfolio item.
 */
export async function uploadPortfolioMedia(
    itemId: number | string,
    formData: FormData,
    progressCallback?: (progressEvent: any) => void
) {
    const { data } = await api.post(
        portfolioItemMediaAddUrl(itemId),
        formData,
        {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            onUploadProgress: progressCallback,
        }
    );
    return data;
}

/**
 * Replaces an existing portfolio media item with a new binary upload.
 */
export async function replacePortfolioMedia(
    mediaId: number | string,
    formData: FormData,
    progressCallback?: (progressEvent: any) => void
) {
    const { data } = await api.patch(
        portfolioMediaReplaceUrl(mediaId),
        formData,
        {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            onUploadProgress: progressCallback,
        }
    );
    return data;
}

/**
 * Deletes a portfolio media item.
 */
export async function deletePortfolioMedia(mediaId: number | string) {
    const { data } = await api.delete(portfolioMediaDeleteUrl(mediaId));
    return data;
}
