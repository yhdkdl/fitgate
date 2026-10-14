import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as staffApi from "../api/staff";
import { StaffManagementSection } from "../components/owner/StaffManagementSection";

vi.mock("../api/staff", () => ({
  listStaff: vi.fn(),
  inviteStaff: vi.fn(),
  deactivateStaff: vi.fn(),
  reactivateStaff: vi.fn(),
}));

let mockCurrentUser: { id: string; email: string; role: string; full_name?: string } | null = {
  id: "owner-1",
  email: "owner@apex-a.com",
  role: "owner",
  full_name: "Owner User",
};

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: mockCurrentUser,
    dashboardConfig: null,
    logout: vi.fn(),
  }),
}));

const mockStaffList: staffApi.StaffMember[] = [
  {
    id: "owner-1",
    email: "owner@apex-a.com",
    role: "owner",
    gym_id: "gym-1",
    full_name: "Owner User",
    phone: "+251911000001",
    is_active: true,
    email_verified_at: "2026-10-14T00:00:00Z",
    created_at: "2026-10-14T00:00:00Z",
  },
  {
    id: "mgr-1",
    email: "manager@apex-a.com",
    role: "manager",
    gym_id: "gym-1",
    full_name: "Manager User",
    phone: "+251911000002",
    is_active: true,
    email_verified_at: "2026-10-14T00:00:00Z",
    created_at: "2026-10-14T00:00:00Z",
  },
  {
    id: "trainer-1",
    email: "trainer@apex-a.com",
    role: "trainer",
    gym_id: "gym-1",
    full_name: "Trainer User",
    phone: "+251911000003",
    is_active: true,
    email_verified_at: "2026-10-14T00:00:00Z",
    created_at: "2026-10-14T00:00:00Z",
  },
  {
    id: "rec-1",
    email: "reception@apex-a.com",
    role: "reception",
    gym_id: "gym-1",
    full_name: "Reception User",
    phone: "+251911000004",
    is_active: false,
    email_verified_at: "2026-10-14T00:00:00Z",
    created_at: "2026-10-14T00:00:00Z",
  },
];

describe("Sprint 6: Staff Management UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCurrentUser = {
      id: "owner-1",
      email: "owner@apex-a.com",
      role: "owner",
      full_name: "Owner User",
    };
    vi.mocked(staffApi.listStaff).mockResolvedValue([...mockStaffList]);
  });

  it("renders staff members table with correct roles and statuses", async () => {
    render(
      <MemoryRouter>
        <StaffManagementSection />
      </MemoryRouter>
    );

    expect(await screen.findByText("Staff Management")).toBeInTheDocument();
    expect(await screen.findByText("manager@apex-a.com")).toBeInTheDocument();
    expect(screen.getByText("trainer@apex-a.com")).toBeInTheDocument();
    expect(screen.getByText("reception@apex-a.com")).toBeInTheDocument();

    // Check statuses
    expect(screen.getAllByText("Active").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Deactivated").length).toBeGreaterThanOrEqual(1);
  });

  it("filters staff list by role and status", async () => {
    render(
      <MemoryRouter>
        <StaffManagementSection />
      </MemoryRouter>
    );

    await screen.findByText("Staff Management");

    // Filter by role: trainer
    const roleSelect = screen.getByLabelText("Role:");
    fireEvent.change(roleSelect, { target: { value: "trainer" } });

    expect(screen.getByText("trainer@apex-a.com")).toBeInTheDocument();
    expect(screen.queryByText("manager@apex-a.com")).not.toBeInTheDocument();
    expect(screen.queryByText("reception@apex-a.com")).not.toBeInTheDocument();

    // Filter by status: active
    const statusSelect = screen.getByLabelText("Status:");
    fireEvent.change(statusSelect, { target: { value: "active" } });
    expect(screen.getByText("trainer@apex-a.com")).toBeInTheDocument();

    // Reset filters
    const resetBtn = screen.getByRole("button", { name: /Reset Filters/i });
    fireEvent.click(resetBtn);

    expect(screen.getByText("manager@apex-a.com")).toBeInTheDocument();
    expect(screen.getByText("trainer@apex-a.com")).toBeInTheDocument();
  });

  it("opens invite modal, allows Owner to choose Manager, and sends invitation", async () => {
    const user = userEvent.setup();
    const onUpdated = vi.fn();

    vi.mocked(staffApi.inviteStaff).mockResolvedValue({
      detail: "Staff member invited successfully.",
      user: {
        id: "new-mgr-1",
        email: "newmgr@apex-a.com",
        role: "manager",
        gym_id: "gym-1",
        full_name: "New Manager",
        phone: "+251911999999",
        is_active: true,
        email_verified_at: "2026-10-14T00:00:00Z",
        created_at: "2026-10-14T00:00:00Z",
      },
    });

    render(
      <MemoryRouter>
        <StaffManagementSection onStaffUpdated={onUpdated} />
      </MemoryRouter>
    );

    await screen.findByText("Staff Management");

    // Open invite modal
    const inviteBtn = screen.getByRole("button", {
      name: /Invite Staff Member/i,
    });
    await user.click(inviteBtn);

    expect(screen.getByText("Invite New Staff Member")).toBeInTheDocument();

    // Owner should see Manager option
    const roleSelect = screen.getByLabelText("Staff Role *") as HTMLSelectElement;
    const optionValues = Array.from(roleSelect.options).map((o) => o.value);
    expect(optionValues).toContain("manager");
    expect(optionValues).toContain("trainer");
    expect(optionValues).toContain("reception");

    // Fill in invite form
    await user.type(screen.getByLabelText("Email Address *"), "newmgr@apex-a.com");
    await user.selectOptions(roleSelect, "manager");
    await user.type(screen.getByLabelText("Full Name"), "New Manager");
    await user.type(screen.getByLabelText("Phone Number"), "+251911999999");

    // Submit
    const submitBtn = screen.getByRole("button", { name: /Send Invitation/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(staffApi.inviteStaff).toHaveBeenCalledWith({
        email: "newmgr@apex-a.com",
        role: "manager",
        full_name: "New Manager",
        phone: "+251911999999",
      });
    });

    expect(
      await screen.findByText("Staff invitation sent to newmgr@apex-a.com as manager.")
    ).toBeInTheDocument();
    expect(onUpdated).toHaveBeenCalled();
  });

  it("Manager cannot invite a Manager (Manager role is not in dropdown)", async () => {
    mockCurrentUser = {
      id: "mgr-1",
      email: "manager@apex-a.com",
      role: "manager",
      full_name: "Manager User",
    };

    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <StaffManagementSection />
      </MemoryRouter>
    );

    await screen.findByText("Staff Management");

    const inviteBtn = screen.getByRole("button", {
      name: /Invite Staff Member/i,
    });
    await user.click(inviteBtn);

    const roleSelect = screen.getByLabelText("Staff Role *") as HTMLSelectElement;
    const optionValues = Array.from(roleSelect.options).map((o) => o.value);
    expect(optionValues).not.toContain("manager");
    expect(optionValues).toContain("trainer");
    expect(optionValues).toContain("reception");
  });

  it("handles deactivating a staff member with confirmation", async () => {
    const user = userEvent.setup();
    const onUpdated = vi.fn();

    vi.mocked(staffApi.deactivateStaff).mockResolvedValue({
      detail: "Staff member deactivated successfully.",
      user: {
        ...mockStaffList[2],
        is_active: false,
      },
    });

    render(
      <MemoryRouter>
        <StaffManagementSection onStaffUpdated={onUpdated} />
      </MemoryRouter>
    );

    await screen.findByText("Staff Management");

    // Find Deactivate buttons
    const deactivateButtons = screen.getAllByRole("button", {
      name: "Deactivate",
    });
    expect(deactivateButtons.length).toBeGreaterThan(0);

    // Click deactivate on the trainer
    await user.click(deactivateButtons[1]); // trainer-1

    // Should prompt with Confirm and Cancel
    const confirmBtn = await screen.findByRole("button", { name: "Confirm" });
    const cancelBtn = screen.getByRole("button", { name: "Cancel" });

    // Cancel first
    await user.click(cancelBtn);
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();

    // Click Deactivate again and confirm
    const deactBtnAgain = screen.getAllByRole("button", { name: "Deactivate" })[1];
    await user.click(deactBtnAgain);

    const confirmBtnAgain = await screen.findByRole("button", { name: "Confirm" });
    await user.click(confirmBtnAgain);

    await waitFor(() => {
      expect(staffApi.deactivateStaff).toHaveBeenCalledWith("trainer-1");
    });

    expect(await screen.findByText("Deactivated trainer@apex-a.com.")).toBeInTheDocument();
    expect(onUpdated).toHaveBeenCalled();
  });

  it("handles reactivating a deactivated staff member", async () => {
    const user = userEvent.setup();
    const onUpdated = vi.fn();

    vi.mocked(staffApi.reactivateStaff).mockResolvedValue({
      detail: "Staff member reactivated successfully.",
      user: {
        ...mockStaffList[3],
        is_active: true,
      },
    });

    render(
      <MemoryRouter>
        <StaffManagementSection onStaffUpdated={onUpdated} />
      </MemoryRouter>
    );

    await screen.findByText("Staff Management");

    // Find Reactivate button on deactivated reception member
    const reactivateBtn = screen.getByRole("button", { name: "Reactivate" });
    await user.click(reactivateBtn);

    await waitFor(() => {
      expect(staffApi.reactivateStaff).toHaveBeenCalledWith("rec-1");
    });

    expect(await screen.findByText("Reactivated reception@apex-a.com.")).toBeInTheDocument();
    expect(onUpdated).toHaveBeenCalled();
  });

  it("prevents self-deactivation and Owner deactivation", async () => {
    render(
      <MemoryRouter>
        <StaffManagementSection />
      </MemoryRouter>
    );

    await screen.findByText("Staff Management");

    // Owner (self) row should show Protected, not a Deactivate button
    const protectedLabels = screen.getAllByText("Protected");
    expect(protectedLabels.length).toBeGreaterThanOrEqual(1);
  });
});
