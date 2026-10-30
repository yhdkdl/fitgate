import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PaymentGatewaySection } from "../components/owner/PaymentGatewaySection";
import { MemberCheckoutCard } from "../components/member/MemberCheckoutCard";
import * as paymentsApi from "../api/payments";
import * as plansApi from "../api/plans";

vi.mock("../api/payments");
vi.mock("../api/plans");

describe("Sprint 11 - PaymentGatewaySection", () => {
  const mockConfig: paymentsApi.GymPaymentConfig = {
    is_configured: true,
    is_test_mode: true,
    is_verified: true,
    verified_at: "2026-10-25T10:00:00Z",
    masked_public_key: "CHAPUBK_TEST-****1234",
    has_secret_key: true,
    has_webhook_secret: true,
    use_mock: true,
    detected_mode: "Test",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders masked configuration and test mode badge", async () => {
    vi.mocked(paymentsApi.getGymPaymentConfig).mockResolvedValue(mockConfig);

    render(<PaymentGatewaySection />);

    await waitFor(() => {
      expect(screen.getByText("Chapa Payment Gateway")).toBeInTheDocument();
    });

    expect(screen.getByText("Test Mode")).toBeInTheDocument();
    expect(screen.getByText("Verified & Active")).toBeInTheDocument();
    expect(screen.getByText("CHAPUBK_TEST-****1234")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /test connection/i })
    ).toBeInTheDocument();
  });

  it("submits updated credentials on save", async () => {
    vi.mocked(paymentsApi.getGymPaymentConfig).mockResolvedValue(mockConfig);
    vi.mocked(paymentsApi.updateGymPaymentConfig).mockResolvedValue({
      ...mockConfig,
      masked_public_key: "CHAPUBK_TEST-****9999",
    });

    render(<PaymentGatewaySection />);

    await waitFor(() => {
      expect(screen.getByText("Chapa Payment Gateway")).toBeInTheDocument();
    });

    const pubInput = screen.getByPlaceholderText(
      /e\.g\. CHAPUBK_TEST-xxxxxxxxxxxx/i
    );
    fireEvent.change(pubInput, {
      target: { value: "CHAPUBK_TEST-newkey9999" },
    });

    const saveBtn = screen.getByRole("button", { name: /save credentials/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(paymentsApi.updateGymPaymentConfig).toHaveBeenCalledWith({
        public_key: "CHAPUBK_TEST-newkey9999",
      });
      expect(
        screen.getByText(/Chapa credentials encrypted and saved successfully/i)
      ).toBeInTheDocument();
    });
  });

  it("triggers test connection and shows success feedback", async () => {
    vi.mocked(paymentsApi.getGymPaymentConfig).mockResolvedValue(mockConfig);
    vi.mocked(paymentsApi.testGymPaymentConfig).mockResolvedValue({
      success: true,
      message: "Connection verified successfully.",
      is_verified: true,
    });

    render(<PaymentGatewaySection />);

    await waitFor(() => {
      expect(screen.getByText("Chapa Payment Gateway")).toBeInTheDocument();
    });

    const testBtn = screen.getByRole("button", { name: /test connection/i });
    fireEvent.click(testBtn);

    await waitFor(() => {
      expect(paymentsApi.testGymPaymentConfig).toHaveBeenCalled();
      expect(
        screen.getByText("Connection verified successfully.")
      ).toBeInTheDocument();
    });
  });
});

describe("Sprint 11 - MemberCheckoutCard", () => {
  const mockPlans: plansApi.MembershipPlan[] = [
    {
      id: "plan-monthly-1",
      name: "Monthly Pro",
      description: "Full gym access",
      price_etb: "1500.00",
      duration_value: 1,
      duration_unit: "months",
      is_active: true,
      trainer_inclusive: false,
      created_at: "2026-10-25T00:00:00Z",
      updated_at: "2026-10-25T00:00:00Z",
    },
    {
      id: "plan-annual-1",
      name: "Annual VIP",
      description: "Annual membership",
      price_etb: "15000.00",
      duration_value: 12,
      duration_unit: "months",
      is_active: true,
      trainer_inclusive: true,
      created_at: "2026-10-25T00:00:00Z",
      updated_at: "2026-10-25T00:00:00Z",
    },
  ];

  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, "location", {
      value: {
        ...originalLocation,
        assign: vi.fn(),
      },
      writable: true,
    });
  });

  it("renders active plans and initiates online checkout on click", async () => {
    vi.mocked(plansApi.getMembershipPlans).mockResolvedValue(mockPlans);
    vi.mocked(paymentsApi.initiateChapaCheckout).mockResolvedValue({
      checkout_url: "https://checkout.chapa.co/pay/mock-123",
      tx_ref: "FG-alpha-123",
      payment_id: "pay-1",
    });

    render(<MemberCheckoutCard memberStatus="pending" />);

    await waitFor(() => {
      expect(screen.getByText("Monthly Pro")).toBeInTheDocument();
      expect(screen.getByText("Annual VIP")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/1500\.00/i).length).toBeGreaterThanOrEqual(1);
    const payBtns = screen.getAllByRole("button", {
      name: /pay online \(chapa\)/i,
    });
    fireEvent.click(payBtns[0]);

    await waitFor(() => {
      expect(paymentsApi.initiateChapaCheckout).toHaveBeenCalledWith(
        "plan-monthly-1"
      );
      expect(window.location.assign).toHaveBeenCalledWith(
        "https://checkout.chapa.co/pay/mock-123"
      );
    });
  });
});
