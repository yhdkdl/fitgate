import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { RequestDemoScreen } from "../screens/RequestDemoScreen";
import { DemoRequestSection } from "../components/superadmin/DemoRequestSection";
import * as demoApi from "../api/demoRequests";
import { ApiError } from "../api/client";

vi.mock("../api/demoRequests");

describe("Sprint 4a: Public Demo Requests and Super Admin Lead Section", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("RequestDemoScreen", () => {
    it("renders form inputs, honeypot, and direct contact details", () => {
      render(
        <BrowserRouter>
          <RequestDemoScreen />
        </BrowserRouter>
      );

      expect(
        screen.getByRole("heading", { name: /request a fitgate demo/i })
      ).toBeInTheDocument();
      expect(screen.getByLabelText(/^gym name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^contact person/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^phone number/i)).toBeInTheDocument();

      // Direct contact panel
      expect(screen.getByText(/\+251 911 234 567/i)).toBeInTheDocument();
      expect(screen.getByText(/@FitGateSupport/i)).toBeInTheDocument();
    });

    it("displays error when required fields are missing", async () => {
      render(
        <BrowserRouter>
          <RequestDemoScreen />
        </BrowserRouter>
      );

      const submitBtn = screen.getByRole("button", {
        name: /request live demo/i,
      });
      fireEvent.click(submitBtn);

      expect(
        await screen.findByText(
          /please fill in gym name, your name, and phone number/i
        )
      ).toBeInTheDocument();
      expect(demoApi.submitPublicDemoRequest).not.toHaveBeenCalled();
    });

    it("submits valid form and displays confirmation success card", async () => {
      vi.mocked(demoApi.submitPublicDemoRequest).mockResolvedValue({
        detail: "demo_request_received",
        id: "demo-uuid-123",
      });

      render(
        <BrowserRouter>
          <RequestDemoScreen />
        </BrowserRouter>
      );

      await userEvent.type(
        screen.getByLabelText(/^gym name/i),
        "Bole Fitness Center"
      );
      await userEvent.type(
        screen.getByLabelText(/^contact person/i),
        "Abebe Bikila"
      );
      await userEvent.type(
        screen.getByLabelText(/^phone number/i),
        "+251911223344"
      );
      await userEvent.type(
        screen.getByLabelText(/^city \/ location/i),
        "Addis Ababa"
      );
      await userEvent.type(
        screen.getByLabelText(/^email address/i),
        "abebe@bolefitness.com"
      );

      const submitBtn = screen.getByRole("button", {
        name: /request live demo/i,
      });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(demoApi.submitPublicDemoRequest).toHaveBeenCalledWith({
          gym_name: "Bole Fitness Center",
          contact_name: "Abebe Bikila",
          phone: "+251911223344",
          city: "Addis Ababa",
          email: "abebe@bolefitness.com",
          message: "",
          website: "",
        });
      });

      expect(
        await screen.findByRole("heading", {
          name: /demo request received!/i,
        })
      ).toBeInTheDocument();
    });

    it("displays friendly rate limiting message when API returns 429", async () => {
      vi.mocked(demoApi.submitPublicDemoRequest).mockRejectedValue(
        new ApiError(429, "Too Many Requests")
      );

      render(
        <BrowserRouter>
          <RequestDemoScreen />
        </BrowserRouter>
      );

      await userEvent.type(
        screen.getByLabelText(/^gym name/i),
        "Rapid Fitness"
      );
      await userEvent.type(
        screen.getByLabelText(/^contact person/i),
        "Contact"
      );
      await userEvent.type(
        screen.getByLabelText(/^phone number/i),
        "+251911000000"
      );

      fireEvent.click(
        screen.getByRole("button", { name: /request live demo/i })
      );

      expect(
        await screen.findByText(
          /too many requests\. please wait a few moments or contact our team directly/i
        )
      ).toBeInTheDocument();
    });
  });

  describe("DemoRequestSection", () => {
    const mockLeads = [
      {
        id: "lead-1",
        gym_name: "Arsho Gym",
        contact_name: "Arsho Lemma",
        phone: "+251911111111",
        city: "Addis Ababa",
        email: "arsho@example.com",
        message: "Need 2 biometric scanners.",
        status: "new" as const,
        notes: "",
        handled_by: null,
        handled_by_email: null,
        converted_gym: null,
        converted_gym_subdomain: null,
        created_at: "2026-10-10T12:00:00Z",
        updated_at: "2026-10-10T12:00:00Z",
      },
      {
        id: "lead-2",
        gym_name: "Lideta Fitness",
        contact_name: "Lideta Contact",
        phone: "+251922222222",
        city: "Lideta",
        email: "lideta@example.com",
        message: "",
        status: "contacted" as const,
        notes: "Called on Monday.",
        handled_by: "super-1",
        handled_by_email: "admin@fitgate.org",
        converted_gym: null,
        converted_gym_subdomain: null,
        created_at: "2026-10-09T10:00:00Z",
        updated_at: "2026-10-09T11:00:00Z",
      },
    ];

    it("renders lead list and filters by status", async () => {
      vi.mocked(demoApi.listDemoRequests).mockResolvedValue(mockLeads);

      render(<DemoRequestSection />);

      expect(await screen.findByText("Arsho Gym")).toBeInTheDocument();
      expect(screen.getByText("Lideta Fitness")).toBeInTheDocument();

      // Filter by Contacted
      const contactedTab = screen.getByRole("button", { name: "Contacted" });
      fireEvent.click(contactedTab);

      await waitFor(() => {
        expect(demoApi.listDemoRequests).toHaveBeenCalledWith("contacted");
      });
    });

    it("opens lead review modal, updates notes and status", async () => {
      vi.mocked(demoApi.listDemoRequests).mockResolvedValue(mockLeads);
      const updatedLead = {
        ...mockLeads[0],
        status: "contacted" as const,
        notes: "Scheduled presentation.",
        handled_by_email: "admin@fitgate.org",
      };
      vi.mocked(demoApi.updateDemoRequest).mockResolvedValue(updatedLead);

      render(<DemoRequestSection />);

      const reviewButtons = await screen.findAllByRole("button", {
        name: /review lead/i,
      });
      fireEvent.click(reviewButtons[0]);

      // Verify modal is open
      expect(
        screen.getByRole("heading", { name: /arsho gym/i })
      ).toBeInTheDocument();

      // Change status and notes
      const statusSelect = screen.getByLabelText(/lead status/i);
      fireEvent.change(statusSelect, { target: { value: "contacted" } });

      const notesTextarea = screen.getByLabelText(
        /internal notes & follow-up log/i
      );
      await userEvent.type(notesTextarea, "Scheduled presentation.");

      fireEvent.click(screen.getByRole("button", { name: /save notes/i }));

      await waitFor(() => {
        expect(demoApi.updateDemoRequest).toHaveBeenCalledWith("lead-1", {
          status: "contacted",
          notes: "Scheduled presentation.",
        });
      });
    });

    it("triggers conversion callback with pre-filled form data", async () => {
      vi.mocked(demoApi.listDemoRequests).mockResolvedValue(mockLeads);
      const convertData = {
        demo_request_id: "lead-1",
        name: "Arsho Gym",
        contact_name: "Arsho Lemma",
        contact_phone: "+251911111111",
        contact_email: "arsho@example.com",
        location: "Addis Ababa",
      };
      vi.mocked(demoApi.getDemoRequestConvertData).mockResolvedValue(
        convertData
      );

      const onConvertSpy = vi.fn();
      render(<DemoRequestSection onConvertToGym={onConvertSpy} />);

      const reviewButtons = await screen.findAllByRole("button", {
        name: /review lead/i,
      });
      fireEvent.click(reviewButtons[0]);

      const convertBtn = screen.getByRole("button", {
        name: /convert to gym/i,
      });
      fireEvent.click(convertBtn);

      await waitFor(() => {
        expect(demoApi.getDemoRequestConvertData).toHaveBeenCalledWith(
          "lead-1"
        );
        expect(onConvertSpy).toHaveBeenCalledWith(convertData);
      });
    });
  });
});
