export type ReportContentType = "service" | "provider" | "review" | "comment";
export type ReportReason = "spam" | "fraud" | "abuse" | "inappropriate" | "other";
export type ReportStatus = "open" | "in_review" | "resolved" | "rejected";

export interface Report {
  id: number;
  reporter: number;
  reporter_email: string;
  content_type: ReportContentType;
  object_id: number;
  reason: ReportReason;
  message: string;
  status: ReportStatus;
  created_at: string;
  resolution_note?: string;
  object_summary?: string;
  object_missing?: boolean;
}
