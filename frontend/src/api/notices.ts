import { apiFetch } from "./client";
import type { GymNotice, NoticeCreatePayload, TelegramTestResponse } from "../types/notice";

export async function listNotices(): Promise<GymNotice[]> {
  return apiFetch<GymNotice[]>("/api/gym/notices/");
}

export async function createNotice(payload: NoticeCreatePayload): Promise<GymNotice> {
  return apiFetch<GymNotice>("/api/gym/notices/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteNotice(id: string): Promise<void> {
  await apiFetch<void>(`/api/gym/notices/${id}/`, {
    method: "DELETE",
  });
}

export async function testTelegramBroadcast(): Promise<TelegramTestResponse> {
  return apiFetch<TelegramTestResponse>("/api/gym/settings/telegram/test/", {
    method: "POST",
  });
}
