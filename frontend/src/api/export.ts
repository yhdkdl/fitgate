import { apiFetchBlob } from "./client";

export type ExportType = "members" | "payments" | "attendance";

export interface ExportParams {
  startDate?: string;
  endDate?: string;
}

export async function downloadGymExport(
  exportType: ExportType,
  params?: ExportParams
): Promise<void> {
  const query = new URLSearchParams();
  if (params?.startDate) query.set("start_date", params.startDate);
  if (params?.endDate) query.set("end_date", params.endDate);

  const queryString = query.toString() ? `?${query.toString()}` : "";
  const blob = await apiFetchBlob(
    `/api/gym/export/${exportType}/${queryString}`
  );

  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, "");
  const defaultFilename = `${exportType}_export_${dateStr}.csv`;

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = defaultFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
