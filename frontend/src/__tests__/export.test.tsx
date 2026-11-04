import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ExportDataModal } from "../components/export/ExportDataModal";
import * as exportApi from "../api/export";

describe("ExportDataModal", () => {
  const downloadSpy = vi.spyOn(exportApi, "downloadGymExport");

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders export modal with correct title and options", () => {
    render(
      <ExportDataModal isOpen={true} onClose={vi.fn()} exportType="members" />
    );

    expect(screen.getByText("Export Members CSV")).toBeInTheDocument();
    expect(
      screen.getByText(
        /personal health, measurement, workout, and photo data are strictly excluded/i
      )
    ).toBeInTheDocument();
    expect(screen.getByText("All records")).toBeInTheDocument();
    expect(screen.getByText("Filter by date")).toBeInTheDocument();
  });

  it("validates date range > 1 year on submit", async () => {
    render(
      <ExportDataModal isOpen={true} onClose={vi.fn()} exportType="payments" />
    );

    // Click filter by date
    fireEvent.click(screen.getByLabelText(/filter by date/i));

    const startInput = screen.getByLabelText(/start date/i);
    const endInput = screen.getByLabelText(/end date/i);

    fireEvent.change(startInput, { target: { value: "2024-01-01" } });
    fireEvent.change(endInput, { target: { value: "2025-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /download csv/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/export date range cannot exceed 1 year/i)
      ).toBeInTheDocument();
    });
    expect(downloadSpy).not.toHaveBeenCalled();
  });

  it("calls downloadGymExport for valid submission", async () => {
    downloadSpy.mockResolvedValueOnce(undefined);
    const onClose = vi.fn();

    render(
      <ExportDataModal
        isOpen={true}
        onClose={onClose}
        exportType="attendance"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /download csv/i }));

    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledWith("attendance", {
        startDate: undefined,
        endDate: undefined,
      });
      expect(onClose).toHaveBeenCalled();
    });
  });
});
