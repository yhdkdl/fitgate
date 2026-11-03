export interface GymNotice {
  id: string;
  title: string;
  body: string;
  posted_by: string | null;
  posted_by_name: string;
  created_at: string;
  updated_at: string;
  telegram_sent?: boolean;
  telegram_note?: string;
}

export interface NoticeCreatePayload {
  title: string;
  body: string;
}

export interface TelegramTestResponse {
  success: boolean;
  detail: string;
}
