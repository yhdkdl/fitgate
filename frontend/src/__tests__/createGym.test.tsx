import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GymManagementSection } from "../components/superadmin/GymManagementSection";
import * as gymsApi from "../api/gyms";

vi.mock("../api/gyms", () => ({
  listGyms: vi.fn(),
  createGym: vi.fn(),
  proposeSubdomain: vi.fn(),
  confirmGymTls: vi.fn(),
}));

describe("GymManagementSection", () => {
  const mockGyms: gymsApi.GymTenantSummary[] = [
    {
      id: "gym-1",
      name: "Bole Power Fitness",
      subdomain: "bole-power",
      url: "https://bole-power.fitgate.com",
      status: "active",
      tier: "growth",
      currency: "ETB",
      location: "Bole Atlas",
      contact_name: "Abebe Bikila",
      contact_phone: "+251911223344",
      contact_email: "abebe@bolepower.com",
      owner_email: "abebe@bolepower.com",
      subscription_expires_at: null,
      tls_confirmed_at: null,
      created_at: "2026-10-11T10:00:00Z",
      updated_at: "2026-10-11T10:00:00Z",
    },
    {
      id: "gym-2",
      name: "Apex Elite Club",
      subdomain: "apex-elite",
      url: "https://apex-elite.fitgate.com",
      status: "active",
      tier: "pro",
      currency: "ETB",
      location: "Kazanchis",
      contact_name: "Haile G",
      contact_phone: "+251922334455",
      contact_email: "haile@apexelite.com",
      owner_email: "haile@apexelite.com",
      subscription_expires_at: "2027-10-11T10:00:00Z",
      tls_confirmed_at: "2026-10-11T10:00:00Z",
      created_at: "2026-10-10T10:00:00Z",
      updated_at: "2026-10-11T10:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(gymsApi.listGyms).mockResolvedValue(mockGyms);
  });

  it("renders gym table with status, subdomains, and TLS security badges", async () => {
    render(<GymManagementSection />);

    expect(await screen.findByText("Bole Power Fitness")).toBeInTheDocument();
    expect(screen.getByText("bole-power")).toBeInTheDocument();
    expect(screen.getByText("GROWTH")).toBeInTheDocument();
    expect(screen.getByText("Securing...")).toBeInTheDocument();

    expect(screen.getByText("Apex Elite Club")).toBeInTheDocument();
    expect(screen.getByText("apex-elite")).toBeInTheDocument();
    expect(screen.getByText("PRO")).toBeInTheDocument();
    expect(screen.getByText("Secured")).toBeInTheDocument();
  });

  it("proposes subdomain when suggest button is clicked", async () => {
    vi.mocked(gymsApi.proposeSubdomain).mockResolvedValue("fit-zone-addis");

    render(<GymManagementSection />);
    const openBtn = screen.getByRole("button", { name: /\+ create new gym/i });
    fireEvent.click(openBtn);

    const nameInput = screen.getByLabelText(/gym name/i);
    await userEvent.type(nameInput, "Fit Zone Addis");

    const suggestBtn = screen.getByRole("button", { name: /suggest/i });
    fireEvent.click(suggestBtn);

    await waitFor(() => {
      expect(gymsApi.proposeSubdomain).toHaveBeenCalledWith("Fit Zone Addis");
      const subdomainInput = screen.getByLabelText(/subdomain/i);
      expect(subdomainInput).toHaveValue("fit-zone-addis");
    });
  });

  it("submits gym creation form and displays generated invite link", async () => {
    const mockCreatedResponse: gymsApi.CreateGymResponse = {
      gym: {
        id: "gym-new",
        name: "Olympic Gym",
        subdomain: "olympic-gym",
        url: "https://olympic-gym.fitgate.com",
        status: "active",
        tier: "starter",
        currency: "ETB",
        location: "Piazza",
        contact_name: "Derartu Tulu",
        contact_phone: "+251933445566",
        contact_email: "derartu@olympic.com",
        owner_email: "derartu@olympic.com",
        subscription_expires_at: null,
        tls_confirmed_at: null,
        created_at: "2026-10-11T12:00:00Z",
        updated_at: "2026-10-11T12:00:00Z",
      },
      config: {
        tier: "pro",
        has_trainer_module: false,
        has_ai_plans: false,
        has_analytics: false,
        has_group_classes: false,
        has_multi_branch: false,
        freeze_days_cap: 30,
        freeze_days_allowed: 0,
        payment_grace_days: 7,
        subscription_reminder_days: [14, 7],
        member_reminder_days: [7, 2],
        brand_color: null,
        logo: null,
        show_unavailable_equipment: false,
        first_run_dismissed_at: null,
      },
      owner: {
        id: "owner-1",
        email: "derartu@olympic.com",
        role: "owner",
        gym_id: "gym-new",
        full_name: "Derartu Tulu",
        phone: "+251933445566",
        must_change_password: false,
      },
      payment_id: "pay-1",
    };

    vi.mocked(gymsApi.createGym).mockResolvedValue(mockCreatedResponse);

    render(<GymManagementSection />);
    fireEvent.click(screen.getByRole("button", { name: /\+ create new gym/i }));

    await userEvent.type(screen.getByLabelText(/gym name/i), "Olympic Gym");
    await userEvent.type(screen.getByLabelText(/subdomain/i), "olympic-gym");
    await userEvent.type(
      screen.getByLabelText(/^owner email/i),
      "derartu@olympic.com"
    );
    await userEvent.type(
      screen.getByLabelText(/confirm owner email/i),
      "derartu@olympic.com"
    );
    await userEvent.type(
      screen.getByLabelText(/bank reference/i),
      "CBE-REF-001"
    );

    fireEvent.click(screen.getByRole("button", { name: /provision gym/i }));

    await waitFor(() => {
      expect(gymsApi.createGym).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Olympic Gym",
          subdomain: "olympic-gym",
          owner_email: "derartu@olympic.com",
          payment_reference: "CBE-REF-001",
          payment_method: "bank_transfer",
        })
      );
    });

    expect(
      await screen.findByText(
        /gym successfully created & subdomain provisioned!/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/owner set-password invite email sent/i)
    ).toBeInTheDocument();
  });

  it("confirms TLS certificate when action button is clicked", async () => {
    vi.mocked(gymsApi.confirmGymTls).mockResolvedValue({
      gym: {
        ...mockGyms[0],
        tls_confirmed_at: "2026-10-11T12:00:00Z",
      },
      message: "TLS certificate confirmed.",
    });

    render(<GymManagementSection />);

    const confirmBtn = await screen.findByRole("button", {
      name: /confirm tls/i,
    });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(gymsApi.confirmGymTls).toHaveBeenCalledWith("gym-1");
    });
  });
});
