export type Category = {
  id: number;
  name: string;
  name_ru: string;
  name_en: string;
  name_kz: string;
  slug: string;
  parent: number | null;
  children?: Category[];
};

export interface Service {
  id: number;
  title: string;
  description: string;
  price_amount: string;
  price_type: 'fixed' | 'hourly' | 'range';
  city: string;
  category: number;
  category_name: string;
  cover?: string;
  provider: {
    id: number;
    username: string;
    avatar?: string;
    rating_avg: number;
    reviews_count: number;
    user: {
      first_name: string;
      last_name: string;
    };
    is_favorite?: boolean;
  };
  is_favorite: boolean;
  is_active: boolean;
  address?: string;
  latitude?: number | null;
  longitude?: number | null;
  distance_m?: number;
  created_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
