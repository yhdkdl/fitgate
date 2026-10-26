import { apiClient } from "./client";
import type { components } from "../types/api";

export type GymPaymentConfig = components["schemas"]["GymPaymentConfig"];
export type PatchedGymPaymentConfigUpdateRequest =
  components["schemas"]["PatchedGymPaymentConfigUpdateRequest"];
export type ChapaCheckoutResponse =
  components["schemas"]["ChapaCheckoutResponse"];

export async function getGymPaymentConfig(): Promise<GymPaymentConfig> {
  const res = await apiClient.get<GymPaymentConfig>("/api/gym/payment-config/");
  return res.data;
}

export async function updateGymPaymentConfig(
  data: PatchedGymPaymentConfigUpdateRequest
): Promise<GymPaymentConfig> {
  const res = await apiClient.put<GymPaymentConfig>(
    "/api/gym/payment-config/",
    data
  );
  return res.data;
}

export async function testGymPaymentConfig(): Promise<{
  success: boolean;
  message: string;
  is_verified: boolean;
}> {
  const res = await apiClient.post<{
    success: boolean;
    message: string;
    is_verified: boolean;
  }>("/api/gym/payment-config/test/");
  return res.data;
}

export async function initiateChapaCheckout(
  planId: string,
  memberId?: string
): Promise<ChapaCheckoutResponse> {
  const res = await apiClient.post<ChapaCheckoutResponse>(
    "/api/payments/checkout/chapa/",
    { plan_id: planId, member_id: memberId }
  );
  return res.data;
}
