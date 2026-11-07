import React, { useEffect, useState } from "react";
import {
  createPlatformNotice,
  getPlatformNotices,
  listGyms,
  withdrawPlatformNotice,
  type GymTenantSummary,
  type PlatformNotice,
} from "../../api/gyms";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";

export const PlatformNoticesSection: React.FC = () => {
  const [notices, setNotices] = useState<PlatformNotice[]>([]);
  const [gyms, setGyms] = useState<GymTenantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Compose modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [audienceType, setAudienceType] = useState<"all" | "selected">("all");
  const [selectedGymIds, setSelectedGymIds] = useState<string[]>([]);
  const [gymSearch, setGymSearch] = useState("");
  const [showUntil, setShowUntil] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Withdrawing state
  const [withdrawingId, setWithdrawingId] = useState<string | null>(null);

  const fetchNotices = async () => {
    try {
      setLoading(true);
      setError(null);
      const [noticeData, gymData] = await Promise.all([
        getPlatformNotices(),
        listGyms().catch(() => []),
      ]);
      setNotices(noticeData);
      setGyms(gymData);
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load platform notices.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotices();
  }, []);

  const handleOpenModal = () => {
    setTitle("");
    setMessage("");
    setAudienceType("all");
    setSelectedGymIds([]);
    setGymSearch("");
    setShowUntil("");
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleToggleGym = (id: string) => {
    setSelectedGymIds((prev) =>
      prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]
    );
  };

  const handleSelectAllFilteredGyms = (filtered: GymTenantSummary[]) => {
    const ids = filtered.map((g) => g.id);
    setSelectedGymIds((prev) => Array.from(new Set([...prev, ...ids])));
  };

  const handleClearGymSelection = () => {
    setSelectedGymIds([]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMsg(null);

    const trimmedTitle = title.trim();
    const trimmedMsg = message.trim();

    if (trimmedTitle.length < 3 || trimmedTitle.length > 100) {
      setFormError("Notice title must be between 3 and 100 characters.");
      return;
    }

    if (trimmedMsg.length < 5 || trimmedMsg.length > 1000) {
      setFormError("Notice message must be between 5 and 1,000 characters.");
      return;
    }

    if (audienceType === "selected" && selectedGymIds.length === 0) {
      setFormError("Please select at least one target gym for this notice.");
      return;
    }

    try {
      setSubmitting(true);
      await createPlatformNotice({
        title: trimmedTitle,
        message: trimmedMsg,
        audience_type: audienceType,
        target_gym_ids: audienceType === "selected" ? selectedGymIds : [],
        show_until: showUntil ? showUntil : null,
      });

      setIsModalOpen(false);
      setSuccessMsg(
        audienceType === "all"
          ? "Platform notice broadcast to all gym Owners."
          : `Platform notice delivered to ${selectedGymIds.length} gym Owner(s).`
      );
      await fetchNotices();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to create platform notice.";
      setFormError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async (notice: PlatformNotice) => {
    if (
      !window.confirm(
        `Are you sure you want to withdraw notice "${notice.title}"? Owners will no longer see it.`
      )
    ) {
      return;
    }

    try {
      setWithdrawingId(notice.id);
      await withdrawPlatformNotice(notice.id);
      setSuccessMsg(`Notice "${notice.title}" withdrawn successfully.`);
      await fetchNotices();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to withdraw notice.";
      setError(msg);
    } finally {
      setWithdrawingId(null);
    }
  };

  const filteredGyms = gyms.filter(
    (g) =>
      g.name.toLowerCase().includes(gymSearch.toLowerCase()) ||
      g.subdomain.toLowerCase().includes(gymSearch.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">
            Platform Notices
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Broadcast administrative announcements and platform updates to gym
            Owners across all tiers.
          </p>
        </div>
        <Button variant="primary" onClick={handleOpenModal}>
          Compose Notice
        </Button>
      </div>

      {successMsg && (
        <Alert variant="success" onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {error && <Alert variant="danger">{error}</Alert>}

      {/* Loading */}
      {loading && (
        <div className="flex justify-center p-8">
          <Spinner size="lg" />
        </div>
      )}

      {/* Notices Table */}
      {!loading && (
        <Card className="bg-surface border-border overflow-hidden p-0">
          {notices.length === 0 ? (
            <div className="p-8 text-center text-text-muted text-sm">
              No platform notices posted yet. Click &quot;Compose Notice&quot; to send an announcement.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-text">
                <thead className="bg-surface-2 text-text-muted border-b border-border text-xs uppercase font-medium">
                  <tr>
                    <th className="px-4 py-3">Title & Message</th>
                    <th className="px-4 py-3">Audience</th>
                    <th className="px-4 py-3">Show Until</th>
                    <th className="px-4 py-3">Sent At</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {notices.map((n) => (
                    <tr
                      key={n.id}
                      className={`hover:bg-surface-2/40 transition-colors ${
                        n.is_withdrawn ? "opacity-60 bg-surface-2/20" : ""
                      }`}
                    >
                      <td className="px-4 py-3 max-w-md">
                        <div className="font-semibold text-text">{n.title}</div>
                        <p className="text-xs text-text-muted mt-0.5 line-clamp-2">
                          {n.message}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {n.audience_type === "all" ? (
                          <Badge variant="primary">All Gyms</Badge>
                        ) : (
                          <div className="space-y-1">
                            <Badge variant="neutral">
                              {n.target_gym_names?.length || n.target_gym_ids?.length || 0} Gym(s)
                            </Badge>
                            {n.target_gym_names && n.target_gym_names.length > 0 && (
                              <div className="text-[11px] text-text-muted line-clamp-1">
                                {n.target_gym_names.join(", ")}
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-muted">
                        {n.show_until ? new Date(n.show_until).toLocaleDateString() : "Permanent"}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-muted">
                        {new Date(n.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        {n.is_withdrawn ? (
                          <Badge variant="neutral">Withdrawn</Badge>
                        ) : (
                          <Badge variant="success">Active</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {!n.is_withdrawn ? (
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => handleWithdraw(n)}
                            disabled={withdrawingId === n.id}
                            className="text-xs"
                          >
                            {withdrawingId === n.id ? "Withdrawing..." : "Withdraw"}
                          </Button>
                        ) : (
                          <span className="text-xs text-text-muted italic">Withdrawn</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* Compose Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Compose Platform Notice"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && <Alert variant="danger">{formError}</Alert>}

          <FormField
            id="notice_title"
            label="Notice Title"
            helpText="3 to 100 characters. Shown as notification subject to gym Owners."
          >
            <Input
              id="notice_title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Scheduled System Maintenance"
              maxLength={100}
              required
            />
          </FormField>

          <FormField
            id="notice_message"
            label="Message"
            helpText="Up to 1,000 characters."
          >
            <textarea
              id="notice_message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Enter announcement details..."
              rows={4}
              maxLength={1000}
              required
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </FormField>

          <FormField id="audience" label="Target Audience">
            <div className="flex items-center gap-4 mt-1">
              <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
                <input
                  type="radio"
                  name="audience_type"
                  value="all"
                  checked={audienceType === "all"}
                  onChange={() => setAudienceType("all")}
                  className="text-primary focus:ring-primary"
                />
                All Gyms
              </label>
              <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
                <input
                  type="radio"
                  name="audience_type"
                  value="selected"
                  checked={audienceType === "selected"}
                  onChange={() => setAudienceType("selected")}
                  className="text-primary focus:ring-primary"
                />
                Selected Gyms ({selectedGymIds.length})
              </label>
            </div>
          </FormField>

          {audienceType === "selected" && (
            <div className="border border-border rounded-lg p-3 bg-surface-2 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Input
                  type="text"
                  placeholder="Search gyms by name or subdomain..."
                  value={gymSearch}
                  onChange={(e) => setGymSearch(e.target.value)}
                  className="text-xs py-1"
                />
                <div className="flex items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSelectAllFilteredGyms(filteredGyms)}
                    className="text-[11px] px-2 py-1"
                  >
                    Select All
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleClearGymSelection}
                    className="text-[11px] px-2 py-1"
                  >
                    Clear
                  </Button>
                </div>
              </div>

              <div className="max-h-40 overflow-y-auto divide-y divide-border/60 bg-surface rounded border border-border">
                {filteredGyms.length === 0 ? (
                  <div className="p-3 text-center text-xs text-text-muted">
                    No gyms match search query.
                  </div>
                ) : (
                  filteredGyms.map((g) => {
                    const isChecked = selectedGymIds.includes(g.id);
                    return (
                      <label
                        key={g.id}
                        className="flex items-center justify-between p-2 hover:bg-surface-2 cursor-pointer text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleToggleGym(g.id)}
                            className="rounded border-border text-primary focus:ring-primary"
                          />
                          <span className="font-medium text-text">{g.name}</span>
                          <span className="text-text-muted font-mono">({g.subdomain})</span>
                        </div>
                        <Badge variant="neutral" className="text-[10px]">
                          {g.tier}
                        </Badge>
                      </label>
                    );
                  })
                )}
              </div>
            </div>
          )}

          <FormField
            id="show_until"
            label="Show Until (Optional)"
            helpText="Leave empty to display indefinitely until manually withdrawn."
          >
            <Input
              id="show_until"
              type="date"
              value={showUntil}
              onChange={(e) => setShowUntil(e.target.value)}
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
              {submitting ? "Sending..." : "Publish Announcement"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
