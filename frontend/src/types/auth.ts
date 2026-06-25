export type UserRole = 'client' | 'provider' | 'admin';

export interface User {
  id: number;
  email: string;
  username: string;
  role: UserRole;
  phone?: string;
  avatar?: string;
  avatar_url?: string | null;
  email_verified: boolean;
  phone_verified: boolean;
  language: 'ru' | 'en' | 'kz';
  provider_profile_id?: number | null;  // For ownership checks
  is_staff?: boolean;
  is_superuser?: boolean;
}

export interface AuthResponse {
  access: string;
  user: User;
}

export interface RefreshResponse {
  access: string;
}
