export interface ProviderPublicProfile {
  id: number;
  username: string;
  avatar: string | null;
  avatar_url?: string | null;
  bio: string | null;
  city?: string | null;
  rating_avg: number | null;
  reviews_count: number;
  is_favorite: boolean;
}

export interface Review {
  id: number;
  client_email: string;
  rating: number;
  text: string;
  provider_reply: string | null;
  created_at: string;
}
