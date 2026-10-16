import React, { useState, useEffect, useCallback } from "react";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { Spinner } from "../ui/Spinner";
import { Alert } from "../ui/Alert";
import {
  fetchGymAuditLogs,
  fetchPlatformAuditLogs,
  type AuditLogEntry,
  type AuditLogFilters,
} from "../../api/audit";

interface AuditLogSectionProps {
  userRole?: string;
  isPlatform?: boolean;
}

const ACTION_TYPE_OPTIONS = [
  { value: "", label: "All Action Types" },
  { value: "user_login", label: "User Login" },
  { value: "logout", label: "User Logout" },
  { value: "password_changed", label: "Password Changed" },
  { value: "staff_provisioned", label: "Staff Provisioned" },
  { value: "staff_deactivated", label: "Staff Deactivated" },
  { value: "staff_reactivated", label: "Staff Reactivated" },
  { value: "member_registered", label: "Member Registered" },
  { value: "attendance_qr_scan", label: "QR Check-in Scan" },
  { value: "attendance_manual_override", label: "Manual Check-in Override" },
  { value: "super_admin_created", label: "Super Admin Created" },
  { value: "gym_created", label: "Gym Created" },
];

export const AuditLogSection: React.FC<AuditLogSectionProps> = ({
  userRole: _userRole,
  isPlatform = false,
}) => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters state
  const [search, setSearch] = useState<string>("");
  const [actionType, setActionType] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);

  const pageSize = 15;

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    const filters: AuditLogFilters = {
      page: currentPage,
      page_size: pageSize,
    };

    if (search.trim()) filters.search = search.trim();
    if (actionType) filters.action_type = actionType;
    if (dateFrom) filters.date_from = dateFrom;
    if (dateTo) filters.date_to = dateTo;

    try {
      const response = isPlatform
        ? await fetchPlatformAuditLogs(filters)
        : await fetchGymAuditLogs(filters);

      setLogs(response.results);
      setTotalCount(response.count);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to load audit logs. Please try again.";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, isPlatform, search, actionType, dateFrom, dateTo]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleApplyFilter = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    loadLogs();
  };

  const handleResetFilters = () => {
    setSearch("");
    setActionType("");
    setDateFrom("");
    setDateTo("");
    setCurrentPage(1);
  };

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  const getActionBadgeVariant = (action: string) => {
    if (
      action.includes("login") ||
      action.includes("logout") ||
      action.includes("password")
    ) {
      return "primary";
    }
    if (action.includes("staff")) {
      return "secondary";
    }
    if (action.includes("attendance")) {
      return "success";
    }
    if (action.includes("created") || action.includes("admin")) {
      return "warning";
    }
    return "secondary";
  };

  const formatTimestamp = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <Card className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-xl font-bold text-text flex items-center gap-2">
            <span>Audit Trail & Security Logs</span>
            <span className="text-xs font-normal text-text-muted bg-surface-2 px-2 py-0.5 rounded border border-border">
              Read-Only
            </span>
          </h2>
          <p className="text-sm text-text-muted mt-1">
            {isPlatform
              ? "Comprehensive platform-wide immutable event ledger across all tenants and operations."
              : "Cryptographically verified, immutable operational event ledger for your gym."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={loadLogs}
            disabled={isLoading}
            className="min-h-[44px]"
          >
            {isLoading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      </div>

      {errorMessage && (
        <Alert variant="danger" title="Error Loading Audit Trail">
          {errorMessage}
        </Alert>
      )}

      {/* Filter Controls Bar */}
      <form
        onSubmit={handleApplyFilter}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 p-4 bg-surface-2/40 border border-border rounded-input"
      >
        <div className="space-y-1">
          <label className="text-xs font-semibold text-text-muted">
            Search
          </label>
          <input
            type="text"
            placeholder="Actor, record ID, or query..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:border-primary min-h-[44px]"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold text-text-muted">
            Action Type
          </label>
          <select
            value={actionType}
            onChange={(e) => {
              setActionType(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:border-primary min-h-[44px]"
          >
            {ACTION_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold text-text-muted">
            Date From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:border-primary min-h-[44px]"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold text-text-muted">
            Date To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:border-primary min-h-[44px]"
          />
        </div>

        <div className="flex items-end gap-2 pt-1">
          <Button
            type="submit"
            variant="primary"
            size="md"
            className="flex-1 min-h-[44px]"
          >
            Filter
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={handleResetFilters}
            className="min-h-[44px]"
          >
            Clear
          </Button>
        </div>
      </form>

      {/* Main Table / Data View */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-12 space-y-3">
          <Spinner size="lg" />
          <span className="text-sm text-text-muted">
            Querying immutable audit logs...
          </span>
        </div>
      ) : logs.length === 0 ? (
        <div className="p-8 text-center bg-surface-2/20 border border-dashed border-border rounded-card">
          <p className="text-base font-medium text-text">
            No audit entries found
          </p>
          <p className="text-xs text-text-muted mt-1">
            No activity matches the selected filter parameters.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="overflow-x-auto border border-border rounded-card bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-2/60 border-b border-border text-xs uppercase font-semibold text-text-muted">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Actor</th>
                  {isPlatform && <th className="py-3 px-4">Gym Tenant</th>}
                  <th className="py-3 px-4">Affected Record</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="hover:bg-surface-2/30 transition-colors"
                  >
                    <td className="py-3 px-4 whitespace-nowrap text-text font-mono text-xs">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <Badge variant={getActionBadgeVariant(log.action_type)}>
                        {log.action_type}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">
                      {log.actor ? (
                        <div>
                          <div className="font-medium text-text">
                            {log.actor.full_name || log.actor.email}
                          </div>
                          <div className="text-xs text-text-muted">
                            {log.actor.role}
                          </div>
                        </div>
                      ) : (
                        <span className="text-text-muted italic">
                          System / Anonymous
                        </span>
                      )}
                    </td>
                    {isPlatform && (
                      <td className="py-3 px-4 whitespace-nowrap">
                        {log.gym_name ? (
                          <span className="font-medium text-text">
                            {log.gym_name}
                          </span>
                        ) : (
                          <span className="text-xs text-primary font-semibold">
                            Apex Platform
                          </span>
                        )}
                      </td>
                    )}
                    <td className="py-3 px-4">
                      <div className="font-medium text-text">
                        {log.affected_record_type}
                      </div>
                      <div className="text-xs font-mono text-text-muted truncate max-w-[140px]">
                        {log.affected_record_id}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSelectedLog(log)}
                        className="min-h-[36px]"
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-2 py-2">
            <span className="text-xs text-text-muted">
              Showing page <strong className="text-text">{currentPage}</strong>{" "}
              of <strong className="text-text">{totalPages}</strong> (
              {totalCount} total events)
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1 || isLoading}
                className="min-h-[44px]"
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  setCurrentPage((p) => Math.min(totalPages, p + 1))
                }
                disabled={currentPage >= totalPages || isLoading}
                className="min-h-[44px]"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Metadata Inspector Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-surface border border-border rounded-card max-w-lg w-full p-6 space-y-4 max-h-[85vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-lg font-bold text-text">
                Audit Event Inspector
              </h3>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-text-muted hover:text-text p-1 min-w-[44px] min-h-[44px] flex items-center justify-center"
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-border/50 py-1.5">
                <span className="text-text-muted">Event ID:</span>
                <span className="font-mono text-xs text-text">
                  {selectedLog.id}
                </span>
              </div>
              <div className="flex justify-between border-b border-border/50 py-1.5">
                <span className="text-text-muted">Action Type:</span>
                <span className="font-semibold text-primary">
                  {selectedLog.action_type}
                </span>
              </div>
              <div className="flex justify-between border-b border-border/50 py-1.5">
                <span className="text-text-muted">Timestamp:</span>
                <span className="font-mono text-xs text-text">
                  {formatTimestamp(selectedLog.timestamp)}
                </span>
              </div>
              <div className="flex justify-between border-b border-border/50 py-1.5">
                <span className="text-text-muted">Affected Record:</span>
                <span className="text-text font-medium">
                  {selectedLog.affected_record_type} (
                  {selectedLog.affected_record_id})
                </span>
              </div>
              <div className="flex justify-between border-b border-border/50 py-1.5">
                <span className="text-text-muted">Actor:</span>
                <span className="text-text font-medium">
                  {selectedLog.actor
                    ? `${selectedLog.actor.email} (${selectedLog.actor.role})`
                    : "System / Anonymous"}
                </span>
              </div>
              {selectedLog.gym_name && (
                <div className="flex justify-between border-b border-border/50 py-1.5">
                  <span className="text-text-muted">Gym:</span>
                  <span className="text-text font-medium">
                    {selectedLog.gym_name}
                  </span>
                </div>
              )}

              <div className="pt-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-text-muted block mb-1">
                  Metadata Payload (Sanitized)
                </label>
                <pre className="bg-surface-2 p-3 rounded-input text-xs font-mono text-text overflow-x-auto border border-border">
                  {selectedLog.metadata
                    ? JSON.stringify(selectedLog.metadata, null, 2)
                    : "null (no additional payload)"}
                </pre>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <Button
                variant="primary"
                size="md"
                onClick={() => setSelectedLog(null)}
                className="min-h-[44px]"
              >
                Close Inspector
              </Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};
