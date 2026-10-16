import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as auditApi from "../api/audit";
import { AuditLogSection } from "../components/dashboard/AuditLogSection";

vi.mock("../api/audit", () => ({
  fetchGymAuditLogs: vi.fn(),
  fetchPlatformAuditLogs: vi.fn(),
}));

const mockAuditLogs: auditApi.AuditLogEntry[] = [
  {
    id: "log-uuid-1",
    gym_id: "gym-uuid-1",
    gym_name: "FitZone Bole",
    actor: {
      id: "actor-1",
      email: "owner@fitzone.com",
      full_name: "Abebe Bikila",
      role: "owner",
    },
    action_type: "member_registered",
    affected_record_type: "Member",
    affected_record_id: "mem-uuid-101",
    timestamp: "2026-10-15T14:30:00Z",
    metadata: {
      registration_type: "staff_assisted",
      plan_name: "Gold Monthly",
    },
  },
  {
    id: "log-uuid-2",
    gym_id: "gym-uuid-1",
    gym_name: "FitZone Bole",
    actor: {
      id: "actor-2",
      email: "reception@fitzone.com",
      full_name: "Hanna Girma",
      role: "reception",
    },
    action_type: "attendance_qr_scan",
    affected_record_type: "Attendance",
    affected_record_id: "att-uuid-202",
    timestamp: "2026-10-15T14:35:00Z",
    metadata: {
      scan_result: "success",
    },
  },
];

describe("Sprint 9a: Audit Log Viewer UI Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders audit log table with records, action badges, and actor details", async () => {
    vi.mocked(auditApi.fetchGymAuditLogs).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: mockAuditLogs,
    });

    render(<AuditLogSection userRole="owner" isPlatform={false} />);

    expect(screen.getByText("Audit Trail & Security Logs")).toBeInTheDocument();
    expect(await screen.findByText("member_registered")).toBeInTheDocument();
    expect(screen.getByText("attendance_qr_scan")).toBeInTheDocument();
    expect(screen.getByText("Abebe Bikila")).toBeInTheDocument();
    expect(screen.getByText("Hanna Girma")).toBeInTheDocument();
    expect(screen.getByText("mem-uuid-101")).toBeInTheDocument();
    expect(screen.getByText("att-uuid-202")).toBeInTheDocument();
  });

  it("filters logs by action type and search query", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.fetchGymAuditLogs).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: mockAuditLogs,
    });

    render(<AuditLogSection userRole="owner" isPlatform={false} />);

    await screen.findByText("member_registered");

    const searchInput = screen.getByPlaceholderText(
      "Actor, record ID, or query..."
    );
    await user.type(searchInput, "Abebe");

    const actionSelect = screen.getByRole("combobox");
    await user.selectOptions(actionSelect, "member_registered");

    const filterBtn = screen.getByRole("button", { name: /^Filter$/i });
    await user.click(filterBtn);

    expect(auditApi.fetchGymAuditLogs).toHaveBeenCalledWith(
      expect.objectContaining({
        search: "Abebe",
        action_type: "member_registered",
      })
    );
  });

  it("opens metadata inspector modal and displays payload", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.fetchGymAuditLogs).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: mockAuditLogs,
    });

    render(<AuditLogSection userRole="owner" isPlatform={false} />);

    const inspectButtons = await screen.findAllByRole("button", {
      name: /^Inspect$/i,
    });
    expect(inspectButtons.length).toBe(2);

    // Click first inspect button
    await user.click(inspectButtons[0]);

    expect(
      await screen.findByText("Audit Event Inspector")
    ).toBeInTheDocument();
    expect(screen.getByText("log-uuid-1")).toBeInTheDocument();
    expect(screen.getByText(/Gold Monthly/i)).toBeInTheDocument();

    // Close modal
    const closeBtn = screen.getByRole("button", { name: /^Close Inspector$/i });
    await user.click(closeBtn);

    await waitFor(() => {
      expect(
        screen.queryByText("Audit Event Inspector")
      ).not.toBeInTheDocument();
    });
  });

  it("renders platform columns when isPlatform is true", async () => {
    vi.mocked(auditApi.fetchPlatformAuditLogs).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: mockAuditLogs,
    });

    render(<AuditLogSection userRole="super_admin" isPlatform={true} />);

    expect(
      await screen.findByText(
        "Comprehensive platform-wide immutable event ledger",
        {
          exact: false,
        }
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Gym Tenant")).toBeInTheDocument();
    expect(screen.getAllByText("FitZone Bole").length).toBeGreaterThan(0);
  });

  it("handles pagination navigation", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.fetchGymAuditLogs).mockResolvedValue({
      count: 25,
      next: "http://localhost/api/gym/audit-logs/?page=2",
      previous: null,
      results: mockAuditLogs,
    });

    render(<AuditLogSection userRole="owner" isPlatform={false} />);

    await screen.findByText("member_registered");

    const nextBtn = screen.getByRole("button", { name: /^Next$/i });
    expect(nextBtn).not.toBeDisabled();

    await user.click(nextBtn);

    expect(auditApi.fetchGymAuditLogs).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 2,
      })
    );
  });

  it("displays error alert when API call fails", async () => {
    vi.mocked(auditApi.fetchGymAuditLogs).mockRejectedValue(
      new Error("Network error connecting to audit log service")
    );

    render(<AuditLogSection userRole="owner" isPlatform={false} />);

    expect(
      await screen.findByText("Error Loading Audit Trail")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Network error connecting to audit log service")
    ).toBeInTheDocument();
  });
});
