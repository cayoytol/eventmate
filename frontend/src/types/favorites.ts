export type FavoriteContentType = "service" | "provider";

export interface FavoriteItem {
  id: number;
  content_type: FavoriteContentType;
  object_id: number;
  object_data: {
    id: number;
    title?: string; // service only
    price_amount?: string; // service only
    price_type?: string; // service only
    city?: string; // service or provider
    category_name?: string; // service only
    provider?: {
      id: number;
      username: string;
    }; // service only
    is_active?: boolean; // service only
    email?: string; // provider only
    username?: string; // provider only
    rating_avg?: number; // provider only
    reviews_count?: number; // provider only
    avatar?: string | null; // provider only
    is_blocked?: boolean; // provider only
  } | null;
  created_at: string;
}

export interface FavoriteToggleResponse {
  status: "added" | "removed";
}

export interface FavoriteCheckResponse {
  is_favorite: boolean;
}
