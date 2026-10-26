import { apiFetch } from "./client";
import type { components } from "../types/api";

export type GymPaymentConfig = components["schemas"]["GymPaymentConfig"];
export type PatchedGymPaymentConfigUpdateRequest =
  components["schemas"]["PatchedGymPaymentConfigUpdateRequest"];
export type ChapaCheckoutResponse =
  components["schemas"]["ChapaCheckoutResponse"];

export async function getGymPaymentConfig(): Promise<GymPaymentConfig> {
  return apiFetch<GymPaymentConfig>("/api/gym/payment-config/");
}

export async function updateGymPaymentConfig(
  data: PatchedGymPaymentConfigUpdateRequest
): Promise<GymPaymentConfig> {
  return apiFetch<GymPaymentConfig>("/api/gym/payment-config/", {
    method: "PUT",
    body: JSON.stringify(data),
    headers: { "Content-Type": "application/json" },
  });
}

export async function testGymPaymentConfig(): Promise<{
  success: boolean;
  message: string;
  is_verified: boolean;
}> {
  return apiFetch<{
    success: boolean;
    message: string;
    is_verified: boolean;
  }>("/api/gym/payment-config/test/", {
    method: "POST",
  });
}

export async function initiateChapaCheckout(
  planId: string,
  memberId?: string
): Promise<ChapaCheckoutResponse> {
  return apiFetch<ChapaCheckoutResponse>("/api/payments/checkout/chapa/", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId, member_id: memberId }),
    headers: { "Content-Type": "application/json" },
  });
}

export interface DigitalReceipt {
  id: string;
  receipt_number: string;
  sequence_number: number;
  issued_at: string;
  issued_by_id: string | null;
  issued_by_name: string;
  amount_etb: string;
  currency: string;
  payment_method: string;
  member_name: string;
  member_phone: string;
  plan_name: string;
  plan_duration: string;
  notes: string;
  gym_name: string;
  gym_subdomain: string;
}

export interface RecordCashPaymentResponse {
  detail: string;
  payment_id: string;
  amount_etb: string;
  status: string;
  receipt: DigitalReceipt;
  subscription_id: string | null;
}

export interface PaymentListItem {
  id: string;
  created_at: string;
  payer_type: string;
  member_id: string | null;
  member_name: string;
  plan_id: string | null;
  plan_name: string;
  method: string;
  amount_etb: string;
  currency: string;
  status: string;
  confirmed_by_id: string | null;
  confirmed_by_name: string;
  receipt_number: string;
  notes: string;
}

export interface GymPaymentListResponse {
  count: number;
  total_confirmed_revenue_etb: string;
  results: PaymentListItem[];
}

export interface MemberPaymentHistoryItem {
  id: string;
  created_at: string;
  plan_name: string;
  method: string;
  amount_etb: string;
  currency: string;
  status: string;
  receipt_number: string;
  subscription_start_date: string | null;
  subscription_end_date: string | null;
}

export async function recordCashPayment(data: {
  member_id: string;
  plan_id: string;
  notes?: string;
  idempotency_key?: string;
}): Promise<RecordCashPaymentResponse> {
  return apiFetch<RecordCashPaymentResponse>("/api/gym/payments/cash/", {
    method: "POST",
    body: JSON.stringify(data),
    headers: { "Content-Type": "application/json" },
  });
}

export async function getGymPayments(params?: {
  start_date?: string;
  end_date?: string;
  method?: string;
  status?: string;
  member_id?: string;
}): Promise<GymPaymentListResponse> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.method) query.set("method", params.method);
  if (params?.status) query.set("status", params.status);
  if (params?.member_id) query.set("member_id", params.member_id);
  const qStr = query.toString();
  return apiFetch<GymPaymentListResponse>(
    `/api/gym/payments/${qStr ? `?${qStr}` : ""}`
  );
}

export async function getMemberPaymentHistory(): Promise<{
  results: MemberPaymentHistoryItem[];
}> {
  return apiFetch<{ results: MemberPaymentHistoryItem[] }>(
    "/api/payments/history/"
  );
}

export async function getReceiptDetail(
  receiptId: string
): Promise<DigitalReceipt> {
  return apiFetch<DigitalReceipt>(`/api/gym/receipts/${receiptId}/`);
}
