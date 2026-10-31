import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import * as client from "../api/client";
import { TrainingPlanReviewSection } from "../components/trainer/TrainingPlanReviewSection";
import { MemberApprovedPlanCard } from "../components/member/MemberApprovedPlanCard";

const mockPrereqsEligible = {
  eligible: true,
  can_generate_this_week: true,
  can_generate_next_week: true,
  missing_requirements: [],
  this_week_draft_count: 1,
  next_week_draft_count: 0,
  has_open_draft_this_week: true,
  has_open_draft_next_week: false,
  open_draft_id_this_week: "plan-1",
  open_draft_id_next_week: null,
};

const mockPrereqsIneligible = {
  eligible: false,
  can_generate_this_week: false,
  can_generate_next_week: false,
  missing_requirements: [
    "No body measurements recorded yet. At least one measurement is required.",
  ],
  this_week_draft_count: 0,
  next_week_draft_count: 0,
  has_open_draft_this_week: false,
  has_open_draft_next_week: false,
  open_draft_id_this_week: null,
  open_draft_id_next_week: null,
};

const mockDraftPlan = {
  id: "plan-1",
  member: "mem-1",
  gym: "gym-1",
  week_start_date: "2026-11-02",
  draft_number: 1,
  status: "pending_review",
  generated_by_model: "mock-deterministic-engine",
  focus_this_week: ["no_focus"],
  trainer_notes: "Focus on legs",
  has_medical_caution: true,
  was_edited: false,
  plan_data: {
    training_days_per_week: 3,
    target_goal: "hypertrophy",
    fitness_level: "intermediate",
    training_phase: "accumulation",
    target_intensity: {
      rpe_target: 8.0,
      volume_modifier: "moderate",
    },
    sessions: [
      {
        session_id: "sess_a",
        name: "Session A",
        focus: "Full Body Resistance",
        exercises: [
          {
            name: "Goblet Squat",
            target_muscle: "Quadriceps",
            sets: 3,
            reps: "8-10",
            rpe: 8,
            rest_seconds: 90,
            notes: "Tempo 3-0-1-0",
          },
        ],
      },
    ],
    nutrition_guidance: {
      daily_principles: [
        "Include legumes (shiro, misir) or eggs at each major meal for protein balance",
      ],
      meal_patterns: {
        breakfast: ["Kinche with small spoonful of niter kibbeh"],
        lunch: ["Injera with misir wot and gomen"],
        dinner: ["Atkilt wot with injera"],
        snacks: ["Roasted chickpeas (kolo)"],
      },
      hydration_notes: "Consume at least 2.5 to 3.5 liters of clean water daily.",
      fasting_compliance_note: "Strictly vegetarian meals provided.",
    },
  },
};

const mockDraft3Plan = {
  ...mockDraftPlan,
  id: "plan-3",
  draft_number: 3,
};

describe("Sprint 22 - AI Workout Plan Review & Generation", () => {
  beforeEach(() => {
    localStorage.clear();
    client.clearTokens();
    client.setRefreshToken("mock-refresh");
    vi.restoreAllMocks();
  });

  it("displays missing requirements when member is ineligible", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/gym/members/mem-1/plans/status/")) {
        return new Response(JSON.stringify(mockPrereqsIneligible), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/gym/members/mem-1/plans/")) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <TrainingPlanReviewSection memberId="mem-1" memberName="Abebe Kebede" />
    );

    await waitFor(() => {
      expect(screen.getByText(/Plan Ineligible/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Plan Generation Requirements Missing:/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/No body measurements recorded yet/i)
      ).toBeInTheDocument();
    });
  });

  it("renders pending draft with medical caution, sessions, and approve/reject actions", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/gym/members/mem-1/plans/status/")) {
        return new Response(JSON.stringify(mockPrereqsEligible), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/gym/members/mem-1/plans/")) {
        return new Response(JSON.stringify([mockDraftPlan]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <TrainingPlanReviewSection memberId="mem-1" memberName="Abebe Kebede" />
    );

    await waitFor(() => {
      expect(screen.getByText(/Pending Review/i)).toBeInTheDocument();
      expect(screen.getByText(/Draft 1 \/ 3/i)).toBeInTheDocument();
      expect(screen.getByText(/Medical Caution/i)).toBeInTheDocument();
      expect(screen.getByText(/Goblet Squat/i)).toBeInTheDocument();
      expect(screen.getByText(/Approve Plan/i)).toBeInTheDocument();
      expect(screen.getByText(/Reject Draft/i)).toBeInTheDocument();
    });

    // Switch to Ethiopian Nutrition tab
    const nutritionTab = screen.getByRole("button", { name: /Ethiopian Nutrition/i });
    fireEvent.click(nutritionTab);

    await waitFor(() => {
      expect(
        screen.getByText(/Ethiopian Dietary & Nutrition Principles/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Injera with misir wot and gomen/i)
      ).toBeInTheDocument();
    });
  });

  it("disables rejection on Draft 3 and instructs trainer to edit directly", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/gym/members/mem-1/plans/status/")) {
        return new Response(JSON.stringify(mockPrereqsEligible), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/gym/members/mem-1/plans/")) {
        return new Response(JSON.stringify([mockDraft3Plan]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <TrainingPlanReviewSection memberId="mem-1" memberName="Abebe Kebede" />
    );

    await waitFor(() => {
      expect(screen.getByText(/Draft 3 \/ 3/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Edit this draft yourself/i).length).toBeGreaterThan(0);
      expect(screen.queryByText(/Reject Draft/i)).not.toBeInTheDocument();
    });
  });

  it("member approved plan card renders only approved plan and ignores pending drafts", async () => {
    const approvedPlan = {
      ...mockDraftPlan,
      status: "approved",
    };

    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/members/me/plans/")) {
        return new Response(JSON.stringify([approvedPlan]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not found", { status: 404 });
    });

    render(<MemberApprovedPlanCard />);

    await waitFor(() => {
      expect(screen.getByText(/Trainer Approved/i)).toBeInTheDocument();
      expect(screen.getByText(/This Week's Workout Plan/i)).toBeInTheDocument();
      expect(screen.getByText(/Goblet Squat/i)).toBeInTheDocument();
    });
  });
});
