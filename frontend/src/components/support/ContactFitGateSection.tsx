import React, { useEffect, useState } from "react";
import {
  createGymSupportRequest,
  getGymSupportRequestDetail,
  listGymSupportRequests,
  replyGymSupportRequest,
  type SupportCategory,
  type SupportRequest,
  type SupportStatus,
} from "../../api/support";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
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

export const ContactFitGateSection: React.FC = () => {
  const [requests, setRequests] = useState<SupportRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active / selected thread
  const [activeRequest, setActiveRequest] = useState<SupportRequest | null>(null);
  const [replyText, setReplyText] = useState("");
  const [replying, setReplying] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);

  // New request modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [category, setCategory] = useState<SupportCategory>("system_problem");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchRequests = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listGymSupportRequests();
      const list = Array.isArray(data) ? data : [];
      setRequests(list);
      if (activeRequest) {
        const updated = list.find((r) => r.id === activeRequest.id);
        if (updated) setActiveRequest(updated);
      }
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load support requests.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const handleOpenModal = () => {
    setCategory("system_problem");
    setSubject("");
    setMessage("");
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMsg(null);

    const trimmedSubject = subject.trim();
    const trimmedMessage = message.trim();

    if (trimmedSubject.length < 3 || trimmedSubject.length > 100) {
      setFormError("Subject must be between 3 and 100 characters.");
      return;
    }

    if (trimmedMessage.length < 5 || trimmedMessage.length > 1000) {
      setFormError("Message must be between 5 and 1,000 characters.");
      return;
    }

    try {
      setSubmitting(true);
      const newReq = await createGymSupportRequest({
        category,
        subject: trimmedSubject,
        message: trimmedMessage,
      });

      setIsModalOpen(false);
      setSuccessMsg("Support request submitted to FitGate Administration.");
      await fetchRequests();
      setActiveRequest(newReq);
    } catch (err: unknown) {
      const errData = (err as { data?: Record<string, unknown> })?.data;
      let msg = (errData?.detail as string) || "";
      if (!msg && errData) {
        const firstField = Object.keys(errData)[0];
        const val = errData[firstField];
        if (Array.isArray(val) && val.length > 0) {
          msg = `${val[0]}`;
        } else if (typeof val === "string") {
          msg = val;
        }
      }
      setFormError(msg || "Failed to submit support request.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSelectRequest = async (req: SupportRequest) => {
    try {
      const detail = await getGymSupportRequestDetail(req.id);
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
      const updated = await replyGymSupportRequest(activeRequest.id, trimmedReply);
      setActiveRequest(updated);
      setReplyText("");
      await fetchRequests();
    } catch (err: unknown) {
      const errData = (err as { data?: Record<string, unknown> })?.data;
      let msg = (errData?.detail as string) || "";
      if (!msg && errData) {
        const firstField = Object.keys(errData)[0];
        const val = errData[firstField];
        if (Array.isArray(val) && val.length > 0) {
          msg = `${val[0]}`;
        } else if (typeof val === "string") {
          msg = val;
        }
      }
      setReplyError(msg || "Failed to send reply.");
    } finally {
      setReplying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Privacy Warning Banner */}
      <Alert variant="warning" className="text-xs">
        <strong>Privacy Notice:</strong> Do not include member names, phone
        numbers or payment details in support communications. FitGate Super
        Admins only view request text and gym identity, never member records.
      </Alert>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">
            Contact FitGate
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Direct communication channel with FitGate platform administrators.
            Limit 5 new requests per calendar day.
          </p>
        </div>
        <Button variant="primary" onClick={handleOpenModal}>
          New Support Request
        </Button>
      </div>

      {successMsg && (
        <Alert variant="success" onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {error && <Alert variant="danger">{error}</Alert>}

      {/* Main Grid: List and Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Requests List */}
        <div className="lg:col-span-5 space-y-3">
          <Card className="bg-surface border-border overflow-hidden p-0">
            <div className="p-3 bg-surface-2 border-b border-border flex items-center justify-between">
              <span className="text-xs font-semibold text-text uppercase tracking-wider">
                Your Support Requests
              </span>
              <Badge variant="neutral" className="text-[10px]">
                {requests.length}
              </Badge>
            </div>

            {loading ? (
              <div className="flex justify-center p-6">
                <Spinner size="md" />
              </div>
            ) : requests.length === 0 ? (
              <div className="p-6 text-center text-xs text-text-muted">
                No support requests submitted yet. Click &quot;New Support Request&quot;
                if you have questions or encountered an issue.
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
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <span className="text-xs font-semibold text-text line-clamp-1">
                          {req.subject}
                        </span>
                        <Badge
                          variant={STATUS_VARIANTS[req.status] || "neutral"}
                          className="text-[10px] shrink-0 capitalize"
                        >
                          {req.status.replace("_", " ")}
                        </Badge>
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-text-muted">
                        <Badge variant="neutral" className="text-[10px]">
                          {CATEGORY_LABELS[req.category || req.request_type || "other"] || req.category || req.request_type}
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
                    Category:{" "}
                    <strong>
                      {CATEGORY_LABELS[activeRequest.category || activeRequest.request_type || "other"] ||
                        activeRequest.category || activeRequest.request_type}
                    </strong>{" "}
                    &bull; Created by {activeRequest.created_by_name} on{" "}
                    {new Date(activeRequest.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="text-xs text-text-muted">
                  {activeRequest.messages?.length || 0} of 20 messages
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
                          ? "bg-surface-2 border-border ml-4"
                          : "bg-primary/10 border-primary/30 mr-4"
                      }`}
                    >
                      <div className="flex items-center justify-between text-text-muted font-medium">
                        <span className={isStaff ? "text-text" : "text-primary font-semibold"}>
                          {isStaff ? `${msg.sender_name} (Gym Staff)` : "FitGate Support"}
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
              {activeRequest.messages && activeRequest.messages.length >= 20 ? (
                <div className="p-3 bg-surface-2 rounded border border-border text-xs text-text-muted text-center">
                  This conversation has reached the limit of 20 messages. If
                  you require additional assistance, please open a new support request.
                </div>
              ) : (
                <form onSubmit={handleSendReply} className="space-y-2 pt-2 border-t border-border">
                  {replyError && <Alert variant="danger">{replyError}</Alert>}

                  {activeRequest.status === "resolved" && (
                    <div className="text-[11px] text-amber-500 bg-amber-500/10 p-2 rounded border border-amber-500/20">
                      Note: This request is marked resolved. Submitting a new message will automatically reopen it.
                    </div>
                  )}

                  <textarea
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder="Type your reply to FitGate Support (max 1,000 characters)..."
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
                      {replying ? "Sending..." : "Send Reply"}
                    </Button>
                  </div>
                </form>
              )}
            </Card>
          ) : (
            <Card className="bg-surface border-border p-12 text-center text-text-muted text-xs">
              Select a support request from the list to view its message thread or reply.
            </Card>
          )}
        </div>
      </div>

      {/* New Request Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="New Support Request"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <Alert variant="warning" className="text-xs">
            <strong>Privacy Reminder:</strong> Do not include member names,
            phone numbers or payment details in your request.
          </Alert>

          {formError && <Alert variant="danger">{formError}</Alert>}

          <FormField id="category" label="Category">
            <select
              id="category"
              value={category}
              onChange={(e) => setCategory(e.target.value as SupportCategory)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="system_problem">System Problem</option>
              <option value="question">Question</option>
              <option value="feature_request">Feature Request</option>
              <option value="billing">Billing</option>
              <option value="other">Other</option>
            </select>
          </FormField>

          <FormField
            id="subject"
            label="Subject"
            helpText="3 to 100 characters summary of your request."
          >
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Question regarding receipt verification"
              maxLength={100}
              required
            />
          </FormField>

          <FormField
            id="message"
            label="Message"
            helpText="Up to 1,000 characters. Attachments are not supported."
          >
            <textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe your issue or inquiry in detail..."
              rows={4}
              maxLength={1000}
              required
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </FormField>

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsModalOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? "Submitting..." : "Submit Request"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
