import { apiFetch } from "./client";

export interface NotificationItem {
  id: string;
  type: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  unread_count: number;
  results: NotificationItem[];
}

export async function fetchNotifications(): Promise<NotificationListResponse> {
  return await apiFetch<NotificationListResponse>("/api/notifications/");
}

export async function markNotificationAsRead(
  id: string
): Promise<{ id: string; is_read: boolean }> {
  return await apiFetch<{ id: string; is_read: boolean }>(
    `/api/notifications/${id}/read/`,
    {
      method: "POST",
    }
  );
}

export async function markAllNotificationsAsRead(): Promise<{
  updated_count: number;
}> {
  return await apiFetch<{ updated_count: number }>(
    "/api/notifications/mark-all-read/",
    {
      method: "POST",
    }
  );
}
