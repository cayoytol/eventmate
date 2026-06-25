import { api } from '@/lib/api';
import { userAvatarUrl } from './endpoints';

/**
 * Uploads or replaces the current user's avatar.
 */
export async function uploadMyAvatar(
    formData: FormData,
    progressCallback?: (progressEvent: any) => void
) {
    const { data } = await api.post(
        userAvatarUrl(),
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
 * Deletes the current user's avatar.
 */
export async function deleteMyAvatar() {
    const { data } = await api.delete(userAvatarUrl());
    return data;
}
