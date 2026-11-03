import { apiFetch } from "./client";

export interface ExpiringMembership {
  member_id: string;
  member_name: string;
  member_phone: string;
  plan_name: string;
  end_date: string;
  days_remaining: number;
}

export interface PlanRevenue {
  plan_id: string;
  plan_name: string;
  revenue: string;
  payment_count: number;
}

export interface GymAnalyticsOverview {
  active_members: number;
  frozen_members: number;
  today_checkins: number;
  monthly_net_revenue: string;
  currency: string;
  expiring_memberships_count: number;
  expiring_memberships: ExpiringMembership[];
  has_analytics: boolean;
  upgrade_prompt?: string | null;
  revenue_by_plan?: PlanRevenue[] | null;
  server_date: string;
}

export async function getGymAnalyticsOverview(): Promise<GymAnalyticsOverview> {
  return apiFetch<GymAnalyticsOverview>("/api/gym/analytics/overview/");
}
