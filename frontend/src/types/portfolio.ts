export interface PortfolioMedia {
  id: number;
  file_url: string;
  media_type: "image" | "video";
  resolved_url?: string;
  uploaded_url?: string;
  external_url?: string;
  mime_type?: string;
  file_size?: number | null;
  width?: number | null;
  height?: number | null;
  created_at: string;
}

export interface PortfolioItem {
  id: number;
  provider_profile: number;
  title: string;
  description: string;
  media: PortfolioMedia[];
  cover_url?: string | null;
  created_at: string;
}
