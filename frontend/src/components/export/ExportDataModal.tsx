import React, { useState } from "react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Alert";
import { downloadGymExport, type ExportType } from "../../api/export";

interface ExportDataModalProps {
  isOpen: boolean;
  onClose: () => void;
  exportType: ExportType;
  title?: string;
}

export const ExportDataModal: React.FC<ExportDataModalProps> = ({
  isOpen,
  onClose,
  exportType,
  title,
}) => {
  const [filterMode, setFilterMode] = useState<"all" | "range">("all");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const displayTitle =
    title ||
    (exportType === "members"
      ? "Export Members CSV"
      : exportType === "payments"
      ? "Export Payments CSV"
      : "Export Attendance CSV");

  const getDescription = () => {
    switch (exportType) {
      case "members":
        return "Exports member contact info, plan, status, and subscription dates. Personal health, measurement, workout, and photo data are strictly excluded.";
      case "payments":
        return "Exports payment history with receipt numbers, gross, credit, net received, upgrade status, bank references, and confirmation staff.";
      case "attendance":
        return "Exports member check-in history with exact date and time, member names, and verification methods (QR or manual override).";
    }
  };

  const handleDownload = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    let start = "";
    let end = "";

    if (filterMode === "range") {
      if (!startDate && !endDate) {
        setErrorMessage("Please select at least a start date or an end date.");
        return;
      }
      if (startDate && endDate) {
        if (startDate > endDate) {
          setErrorMessage("Start date cannot be after end date.");
          return;
        }
        const d1 = new Date(startDate);
        const d2 = new Date(endDate);
        const diffDays = Math.round(
          Math.abs((d2.getTime() - d1.getTime()) / (1000 * 60 * 60 * 24))
        );
        if (diffDays > 366) {
          setErrorMessage("Export date range cannot exceed 1 year.");
          return;
        }
      }
      start = startDate;
      end = endDate;
    }

    setIsLoading(true);
    try {
      await downloadGymExport(exportType, {
        startDate: start || undefined,
        endDate: end || undefined,
      });
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Failed to export data. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={displayTitle}>
      <form onSubmit={handleDownload} className="space-y-4">
        {errorMessage && (
          <Alert variant="danger">
            {errorMessage}
          </Alert>
        )}

        <p className="text-sm text-gray-600 dark:text-gray-300">
          {getDescription()}
        </p>

        <div className="space-y-3 pt-2">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
            Date range
          </label>
          <div className="flex items-center space-x-4">
            <label className="inline-flex items-center text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input
                type="radio"
                name="filterMode"
                value="all"
                checked={filterMode === "all"}
                onChange={() => setFilterMode("all")}
                className="mr-2 text-primary-600 focus:ring-primary-500"
              />
              All records
            </label>
            <label className="inline-flex items-center text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input
                type="radio"
                name="filterMode"
                value="range"
                checked={filterMode === "range"}
                onChange={() => setFilterMode("range")}
                className="mr-2 text-primary-600 focus:ring-primary-500"
              />
              Filter by date
            </label>
          </div>

          {filterMode === "range" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div>
                <label
                  htmlFor="export-start-date"
                  className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1"
                >
                  Start date
                </label>
                <input
                  id="export-start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label
                  htmlFor="export-end-date"
                  className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1"
                >
                  End date
                </label>
                <input
                  id="export-end-date"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
          )}
        </div>

        <div className="bg-gray-50 dark:bg-gray-800/60 p-3 rounded-md text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <div>✓ Excel UTF-8 with BOM (supports Amharic script).</div>
          <div>✓ Formula injection protection automatically applied.</div>
          <div>✓ Maximum date filter span is 1 year (366 days).</div>
        </div>

        <div className="flex justify-end space-x-3 pt-3 border-t border-gray-200 dark:border-gray-700">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isLoading}>
            {isLoading ? "Generating CSV..." : "Download CSV"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
