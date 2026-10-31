import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as freezeApi from "../api/freeze";
import * as membersApi from "../api/members";
import { MemberFreezeSection } from "../components/member/MemberFreezeSection";

vi.mock("../api/freeze", async (importOriginal) => {
  const actual = await importOriginal<typeof freezeApi>();
  return {
    ...actual,
    getMemberFreezeAllowance: vi.fn(),
    getMyFreezes: vi.fn(),
    requestFreeze: vi.fn(),
  };
});

vi.mock("../api/members", () => ({
  getMemberProfileMe: vi.fn(),
}));

describe("Member Freeze Request Section & Error Handling", () => {
  const mockProfile: membersApi.Member = {
    id: "mem-1",
    full_name: "Abebe Bikila",
    phone: "+251911223344",
    email: "abebe@example.com",
    status: "active",
    joined_at: "2026-10-01T00:00:00Z",
    waiver_accepted_at: "2026-10-01T00:00:00Z",
    photo_url: undefined,
    is_on_trainer_plan: false,
  };

  const mockAllowance: freezeApi.MemberFreezeAllowance = {
    total_allowed: 30,
    used_days: 7,
    remaining_days: 23,
    freeze_allowed: true,
    has_active_subscription: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(membersApi.getMemberProfileMe).mockResolvedValue(mockProfile);
    vi.mocked(freezeApi.getMemberFreezeAllowance).mockResolvedValue(mockAllowance);
    vi.mocked(freezeApi.getMyFreezes).mockResolvedValue([]);
  });

  it("formatApiErrorMessage cleanly unpacks field objects and arrays without producing [object Object]", () => {
    // 1. Nested detail with field array
    const nestedDetail = {
      detail: { start_date: ["Freeze start date cannot be in the past."] },
    };
    expect(freezeApi.formatApiErrorMessage(nestedDetail, "Fallback")).toBe(
      "Freeze start date cannot be in the past."
    );

    // 2. Direct field array
    const directField = {
      start_date: ["Freeze start date cannot be in the past."],
    };
    expect(freezeApi.formatApiErrorMessage(directField, "Fallback")).toBe(
      "Freeze start date cannot be in the past."
    );

    // 3. Simple string detail
    const stringDetail = { detail: "Starter gyms cannot use membership freeze." };
    expect(freezeApi.formatApiErrorMessage(stringDetail, "Fallback")).toBe(
      "Starter gyms cannot use membership freeze."
    );

    // 4. Array detail
    const arrayDetail = { detail: ["Exceeds remaining allowance."] };
    expect(freezeApi.formatApiErrorMessage(arrayDetail, "Fallback")).toBe(
      "Exceeds remaining allowance."
    );
  });

  it("renders dedicated MemberFreezeSection with allowance details and opens request modal", async () => {
    render(
      <MemoryRouter>
        <MemberFreezeSection />
      </MemoryRouter>
    );

    const requestBtn = await screen.findByRole("button", {
      name: /request freeze/i,
    });
    expect(requestBtn).toBeInTheDocument();

    // Check allowance display
    expect(screen.getByText(/23\s+Days/i)).toBeInTheDocument();
    expect(screen.getByText("Remaining Days")).toBeInTheDocument();

    // Click request freeze
    fireEvent.click(requestBtn);

    // Modal opens
    expect(
      screen.getByRole("heading", { name: "Request Membership Freeze" })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
  });

  it("displays proper error message when API rejects with past start date error (not [object Object])", async () => {
    const errorData = {
      detail: "Freeze start date cannot be in the past.",
      start_date: ["Freeze start date cannot be in the past."],
    };
    const apiError = new freezeApi.ApiError(400, "Freeze start date cannot be in the past.", errorData);
    vi.mocked(freezeApi.requestFreeze).mockRejectedValueOnce(apiError);

    render(
      <MemoryRouter>
        <MemberFreezeSection />
      </MemoryRouter>
    );

    // Wait for card to finish loading
    const requestBtn = await screen.findByRole("button", {
      name: /request freeze/i,
    });
    fireEvent.click(requestBtn);

    // Fill in valid reason
    const reasonInput = screen.getByLabelText(/reason/i);
    fireEvent.change(reasonInput, { target: { value: "Traveling for conference" } });

    // Submit form
    const submitBtn = screen.getByRole("button", { name: /submit freeze request/i });
    fireEvent.click(submitBtn);

    // Error is displayed as text, strictly NOT "[object Object]"
    await waitFor(() => {
      expect(
        screen.getByText("Freeze start date cannot be in the past.")
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/\[object object\]/i)).not.toBeInTheDocument();
  });

  it("ensures MemberSelfSection on membership view does not render freeze request card", async () => {
    const { MemberSelfSection } = await import("../components/dashboard/MemberSelfSection");
    render(
      <MemoryRouter>
        <MemberSelfSection view="membership" />
      </MemoryRouter>
    );

    // Profile loads
    await waitFor(() => {
      expect(screen.getByText(/Abebe Bikila/i)).toBeInTheDocument();
    });

    // Freeze card and its buttons are strictly absent from My membership page
    expect(screen.queryByRole("button", { name: /request freeze/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/membership freeze/i)).not.toBeInTheDocument();
  });
});
