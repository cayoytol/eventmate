import { api } from '@/lib/api';
import { serviceCoverUrl } from './endpoints';

/**
 * Uploads a service cover image file.
 */
export async function uploadServiceCover(
    serviceId: number | string,
    formData: FormData,
    progressCallback?: (progressEvent: any) => void
) {
    const { data } = await api.post(
        serviceCoverUrl(serviceId),
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
 * Deletes a service cover image.
 */
export async function deleteServiceCover(serviceId: number | string) {
    const { data } = await api.delete(serviceCoverUrl(serviceId));
    return data;
}
