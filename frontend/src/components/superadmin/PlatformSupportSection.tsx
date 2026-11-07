import React, { useEffect, useState } from "react";
import { listGyms, type GymTenantSummary } from "../../api/gyms";
import {
  getPlatformSupportRequestDetail,
  listPlatformSupportRequests,
  replyPlatformSupportRequest,
  updatePlatformSupportRequestStatus,
  type SupportCategory,
  type SupportRequest,
  type SupportStatus,
} from "../../api/support";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";

const CATEGORY_LABELS: Record<SupportCategory, string> = {
  system_problem: "System Problem",
  question: "Question",
  feature_request: "Feature Request",
  billing: "Billing",
  other: "Other",
};

const STATUS_VARIANTS: Record<SupportStatus, "warning" | "primary" | "success"> = {
  open: "warning",
  in_progress: "primary",
  resolved: "success",
};

export const PlatformSupportSection: React.FC = () => {
  const [requests, setRequests] = useState<SupportRequest[]>([]);
  const [gyms, setGyms] = useState<GymTenantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [gymFilter, setGymFilter] = useState<string>("all");

  // Selected thread
  const [activeRequest, setActiveRequest] = useState<SupportRequest | null>(null);
  const [replyText, setReplyText] = useState("");
  const [replying, setReplying] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchRequests = async () => {
    try {
      setLoading(true);
      setError(null);
      const [reqData, gymData] = await Promise.all([
        listPlatformSupportRequests({
          status: statusFilter,
          category: categoryFilter,
          gym_id: gymFilter,
        }),
        listGyms().catch(() => []),
      ]);
      setRequests(reqData);
      setGyms(gymData);
      if (activeRequest) {
        const updated = reqData.find((r) => r.id === activeRequest.id);
        if (updated) setActiveRequest(updated);
      }
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load platform support requests.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, [statusFilter, categoryFilter, gymFilter]);

  const handleSelectRequest = async (req: SupportRequest) => {
    try {
      const detail = await getPlatformSupportRequestDetail(req.id);
      setActiveRequest(detail);
      setReplyText("");
      setReplyError(null);
    } catch {
      setActiveRequest(req);
    }
  };

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRequest) return;
    setReplyError(null);
    setSuccessMsg(null);

    const trimmedReply = replyText.trim();
    if (!trimmedReply) {
      setReplyError("Please enter a reply message.");
      return;
    }
    if (trimmedReply.length > 1000) {
      setReplyError("Reply must be at most 1,000 characters.");
      return;
    }

    try {
      setReplying(true);
      const updated = await replyPlatformSupportRequest(
        activeRequest.id,
        trimmedReply
      );
      setActiveRequest(updated);
      setReplyText("");
      setSuccessMsg("Reply dispatched and notification sent to gym Owner and Manager.");
      await fetchRequests();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to send reply.";
      setReplyError(msg);
    } finally {
      setReplying(false);
    }
  };

  const handleStatusChange = async (newStatus: SupportStatus) => {
    if (!activeRequest) return;
    try {
      setStatusUpdating(true);
      const updated = await updatePlatformSupportRequestStatus(
        activeRequest.id,
        newStatus
      );
      setActiveRequest(updated);
      await fetchRequests();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to update request status.";
      setReplyError(msg);
    } finally {
      setStatusUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text">
          Platform Support Requests
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Review and respond to inquiries and issue tickets from gym staff.
        </p>
      </div>

      {successMsg && (
        <Alert variant="success" onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {error && <Alert variant="danger">{error}</Alert>}

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-surface p-3.5 rounded-lg border border-border">
        {/* Status Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted font-medium">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded border border-border bg-surface-2 px-2.5 py-1 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        {/* Category Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted font-medium">Type:</span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded border border-border bg-surface-2 px-2.5 py-1 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="all">All Types</option>
            <option value="system_problem">System Problem</option>
            <option value="question">Question</option>
            <option value="feature_request">Feature Request</option>
            <option value="billing">Billing</option>
            <option value="other">Other</option>
          </select>
        </div>

        {/* Gym Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted font-medium">Gym:</span>
          <select
            value={gymFilter}
            onChange={(e) => setGymFilter(e.target.value)}
            className="rounded border border-border bg-surface-2 px-2.5 py-1 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary max-w-xs"
          >
            <option value="all">All Gyms</option>
            {gyms.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} ({g.subdomain})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Content: List and Detail Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Requests List */}
        <div className="lg:col-span-5 space-y-3">
          <Card className="bg-surface border-border overflow-hidden p-0">
            <div className="p-3 bg-surface-2 border-b border-border flex items-center justify-between">
              <span className="text-xs font-semibold text-text uppercase tracking-wider">
                Support Requests ({requests.length})
              </span>
            </div>

            {loading ? (
              <div className="flex justify-center p-6">
                <Spinner size="md" />
              </div>
            ) : requests.length === 0 ? (
              <div className="p-6 text-center text-xs text-text-muted">
                No support requests match the selected filters.
              </div>
            ) : (
              <div className="divide-y divide-border/60 max-h-[600px] overflow-y-auto">
                {requests.map((req) => {
                  const isSelected = activeRequest?.id === req.id;
                  return (
                    <div
                      key={req.id}
                      onClick={() => handleSelectRequest(req)}
                      className={`p-3.5 cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-primary/10 border-l-4 border-primary"
                          : "hover:bg-surface-2/60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <div className="font-semibold text-xs text-text line-clamp-1">
                          {req.subject}
                        </div>
                        <Badge
                          variant={STATUS_VARIANTS[req.status] || "neutral"}
                          className="text-[10px] shrink-0 capitalize"
                        >
                          {req.status.replace("_", " ")}
                        </Badge>
                      </div>

                      <div className="text-[11px] font-medium text-primary mb-1">
                        {req.gym_name}
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-text-muted">
                        <Badge variant="neutral" className="text-[10px]">
                          {CATEGORY_LABELS[req.category] || req.category}
                        </Badge>
                        <span>
                          {req.messages?.length || 1} msg &bull;{" "}
                          {new Date(req.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        {/* Right: Active Thread Detail */}
        <div className="lg:col-span-7">
          {activeRequest ? (
            <Card className="bg-surface border-border p-5 space-y-4">
              <div className="border-b border-border pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-text">
                      {activeRequest.subject}
                    </h2>
                    <Badge
                      variant={STATUS_VARIANTS[activeRequest.status] || "neutral"}
                      className="text-[10px] capitalize"
                    >
                      {activeRequest.status.replace("_", " ")}
                    </Badge>
                  </div>
                  <p className="text-xs text-text-muted mt-0.5">
                    Gym: <strong>{activeRequest.gym_name}</strong> &bull; Category:{" "}
                    <strong>
                      {CATEGORY_LABELS[activeRequest.category] ||
                        activeRequest.category}
                    </strong>{" "}
                    &bull; Created by {activeRequest.created_by_name}
                  </p>
                </div>

                {/* Status Switcher Buttons */}
                <div className="flex items-center gap-1">
                  {(["open", "in_progress", "resolved"] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      disabled={statusUpdating || activeRequest.status === s}
                      onClick={() => handleStatusChange(s)}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium capitalize transition-colors ${
                        activeRequest.status === s
                          ? "bg-primary text-white"
                          : "bg-surface-2 text-text-muted hover:text-text hover:bg-surface-2/80"
                      }`}
                    >
                      {s.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>

              {/* Message Thread */}
              <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                {activeRequest.messages?.map((msg) => {
                  const isStaff = msg.sender_type === "gym";
                  return (
                    <div
                      key={msg.id}
                      className={`p-3 rounded-lg border text-xs space-y-1 ${
                        isStaff
                          ? "bg-surface-2 border-border mr-4"
                          : "bg-primary/10 border-primary/30 ml-4"
                      }`}
                    >
                      <div className="flex items-center justify-between text-text-muted font-medium">
                        <span className={isStaff ? "text-text font-semibold" : "text-primary font-semibold"}>
                          {isStaff ? `${msg.sender_name} (${activeRequest.gym_name})` : "FitGate Platform Support"}
                        </span>
                        <span className="text-[10px]">
                          {new Date(msg.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-text whitespace-pre-wrap leading-relaxed">
                        {msg.body}
                      </p>
                    </div>
                  );
                })}
              </div>

              {/* Reply Box */}
              <form onSubmit={handleSendReply} className="space-y-2 pt-2 border-t border-border">
                {replyError && <Alert variant="danger">{replyError}</Alert>}

                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type administrative reply (max 1,000 characters)..."
                  rows={3}
                  maxLength={1000}
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={replying}
                />

                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-text-muted">
                    {replyText.length}/1000 characters
                  </span>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={replying || !replyText.trim()}
                  >
                    {replying ? "Sending..." : "Dispatch Reply"}
                  </Button>
                </div>
              </form>
            </Card>
          ) : (
            <Card className="bg-surface border-border p-12 text-center text-text-muted text-xs">
              Select a support ticket from the list to view conversation history and reply.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
