export interface ServiceComment {
  id: number;
  service: number;
  user: number;
  user_email: string;
  username: string;
  text: string;
  parent: number | null;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  replies: ServiceComment[];
  can_edit: boolean;
  can_reply: boolean;
}
