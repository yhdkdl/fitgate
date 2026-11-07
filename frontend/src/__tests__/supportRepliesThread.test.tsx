import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContactFitGateSection } from "../components/support/ContactFitGateSection";
import * as supportApi from "../api/support";

vi.mock("../api/support", () => ({
  listGymSupportRequests: vi.fn(),
  getGymSupportRequestDetail: vi.fn(),
  createGymSupportRequest: vi.fn(),
  replyGymSupportRequest: vi.fn(),
}));

describe("Support Replies Thread Rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders support thread with sender labels, full text of replies, and timestamps in oldest-first order", async () => {
    const mockRequest: supportApi.SupportRequest = {
      id: "req-123",
      gym_id: "gym-1",
      gym_name: "Atlas Fitness Club",
      subject: "Help with domain TLS",
      category: "system_problem",
      status: "in_progress",
      created_by_name: "Abebe Bikila",
      created_by_role: "owner",
      created_at: "2026-11-05T10:00:00Z",
      updated_at: "2026-11-05T11:00:00Z",
      messages: [
        {
          id: "msg-1",
          request: "req-123",
          sender_name: "Abebe Bikila",
          sender_role: "owner",
          sender_type: "gym",
          sender_label: "Abebe Bikila (Owner)",
          message: "Need help with TLS certificate on custom domain.",
          body: "Need help with TLS certificate on custom domain.",
          created_at: "2026-11-05T10:00:00Z",
        },
        {
          id: "msg-2",
          request: "req-123",
          sender_name: "FitGate Administration",
          sender_role: "super_admin",
          sender_type: "platform",
          sender_label: "FitGate support",
          message: "We have provisioned and confirmed your SSL certificate successfully.",
          body: "We have provisioned and confirmed your SSL certificate successfully.",
          created_at: "2026-11-05T11:00:00Z",
        },
      ],
    };

    vi.mocked(supportApi.listGymSupportRequests).mockResolvedValue([mockRequest]);
    vi.mocked(supportApi.getGymSupportRequestDetail).mockResolvedValue(mockRequest);

    render(<ContactFitGateSection />);

    // Click on the request in the list to open the thread
    await waitFor(() => {
      expect(screen.getByText("Help with domain TLS")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Help with domain TLS"));

    // Wait for thread container to appear
    await waitFor(() => {
      expect(screen.getByTestId("support-messages-thread")).toBeInTheDocument();
    });

    // Verify sender labels are displayed
    expect(screen.getByText("Abebe Bikila (Owner)")).toBeInTheDocument();
    expect(screen.getByText("FitGate support")).toBeInTheDocument();

    // Verify full reply text is displayed
    expect(
      screen.getByText("Need help with TLS certificate on custom domain.")
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "We have provisioned and confirmed your SSL certificate successfully."
      )
    ).toBeInTheDocument();

    // Verify ordering: oldest first (msg-1 text appears before msg-2 text in thread container)
    const thread = screen.getByTestId("support-messages-thread");
    const text1Index = thread.innerHTML.indexOf("Need help with TLS certificate");
    const text2Index = thread.innerHTML.indexOf("We have provisioned and confirmed");
    expect(text1Index).toBeGreaterThan(-1);
    expect(text2Index).toBeGreaterThan(text1Index);
  });
});
