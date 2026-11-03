import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { EquipmentSection } from "../components/equipment/EquipmentSection";
import * as equipmentApi from "../api/equipment";
import type { EquipmentItem } from "../types/equipment";

vi.mock("../api/equipment");

const mockItems: EquipmentItem[] = [
  {
    id: "eq-1",
    name: "Olympic Barbell 20kg",
    category: "barbell",
    serial_number: "OB-001",
    quantity: 2,
    min_qty_threshold: 3, // Low quantity!
    condition: "good",
    purchase_date: "2026-01-15",
    is_low_quantity: true,
    created_at: "2026-01-15T00:00:00Z",
    updated_at: "2026-01-15T00:00:00Z",
    maintenance_logs: [],
  },
  {
    id: "eq-2",
    name: "Rubber Hex Dumbbell Set",
    category: "dumbbells",
    serial_number: "DB-001",
    quantity: 10,
    min_qty_threshold: 5,
    condition: "needs_maintenance",
    purchase_date: "2026-02-10",
    is_low_quantity: false,
    created_at: "2026-02-10T00:00:00Z",
    updated_at: "2026-02-10T00:00:00Z",
    maintenance_logs: [
      {
        id: "log-1",
        equipment: "eq-2",
        reported_by: "user-1",
        reported_by_name: "Trainer Abebe",
        issue_reason: "worn_out",
        other_details: "Handle knurling worn smooth",
        reported_at: "2026-10-20T10:00:00Z",
        resolved_at: null,
        resolved_by: null,
        resolved_by_name: "",
        resolution_notes: "",
      },
    ],
  },
];

describe("Sprint 25: EquipmentSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(equipmentApi, "listEquipment").mockResolvedValue(mockItems);
  });

  it("renders equipment catalog and low stock alert for owner", async () => {
    render(<EquipmentSection userRole="owner" />);

    expect(await screen.findByText("Gym Equipment")).toBeInTheDocument();
    expect(await screen.findByText("Olympic Barbell 20kg")).toBeInTheDocument();
    expect(screen.getByText("Rubber Hex Dumbbell Set")).toBeInTheDocument();

    // Low stock alert
    expect(screen.getByText(/Low Quantity Alert:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Olympic Barbell 20kg/i).length).toBeGreaterThanOrEqual(1);

    // Owner controls
    expect(screen.getByRole("button", { name: /Add Equipment/i })).toBeInTheDocument();
  });

  it("does not show add or edit buttons for member role", async () => {
    render(<EquipmentSection userRole="member" />);

    expect(await screen.findByText("Gym Equipment")).toBeInTheDocument();
    expect(await screen.findByText("Olympic Barbell 20kg")).toBeInTheDocument();

    // Member should not see management buttons or low stock alert
    expect(screen.queryByRole("button", { name: /Add Equipment/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Edit/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Low Quantity Alert:/i)).not.toBeInTheDocument();
  });

  it("allows staff to open issue reporting modal and submit", async () => {
    vi.spyOn(equipmentApi, "reportEquipmentIssue").mockResolvedValue({
      id: "log-2",
      equipment: "eq-1",
      reported_by: "tr-1",
      reported_by_name: "Trainer",
      issue_reason: "broken",
      other_details: "Sleeve bearing seized",
      reported_at: "2026-11-02T10:00:00Z",
      resolved_at: null,
      resolved_by: null,
      resolved_by_name: "",
      resolution_notes: "",
    });

    render(<EquipmentSection userRole="trainer" />);

    expect(await screen.findByText("Olympic Barbell 20kg")).toBeInTheDocument();
    const reportBtns = screen.getAllByRole("button", { name: /Report Issue/i });
    fireEvent.click(reportBtns[0]);

    expect(await screen.findByText(/Report Issue: Olympic Barbell 20kg/i)).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: /Submit Report/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(equipmentApi.reportEquipmentIssue).toHaveBeenCalledWith("eq-1", {
        issue_reason: "broken",
        other_details: "",
      });
    });
  });

  it("shows categories registered note and total investment card to owner with prices", async () => {
    const pricedItems: EquipmentItem[] = [
      {
        ...mockItems[0],
        unit_purchase_price_etb: 15000,
      },
      {
        ...mockItems[1],
        unit_purchase_price_etb: null,
      },
    ];
    vi.spyOn(equipmentApi, "listEquipment").mockResolvedValue(pricedItems);

    render(<EquipmentSection userRole="owner" />);

    expect(await screen.findByText(/Categories registered: 2 of 12/i)).toBeInTheDocument();
    expect(screen.getByText("Total Investment")).toBeInTheDocument();
    // 15000 * 2 = 30,000.00 ETB
    expect(screen.getByText(/30,000.00 ETB/i)).toBeInTheDocument();
    expect(screen.getByText(/1 item.*no price/i)).toBeInTheDocument();
    expect(screen.getByText("Price (ETB)")).toBeInTheDocument();
  });

  it("hides total investment, prices, and serial numbers from member role", async () => {
    const pricedItems: EquipmentItem[] = [
      {
        ...mockItems[0],
        unit_purchase_price_etb: 15000,
      },
    ];
    vi.spyOn(equipmentApi, "listEquipment").mockResolvedValue(pricedItems);

    render(<EquipmentSection userRole="member" />);

    expect(await screen.findByText(/Categories registered: 1 of 12/i)).toBeInTheDocument();
    expect(screen.queryByText("Total Investment")).not.toBeInTheDocument();
    expect(screen.queryByText("Price (ETB)")).not.toBeInTheDocument();
    expect(screen.queryByText("Serial #")).not.toBeInTheDocument();
  });
});
