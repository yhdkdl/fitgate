import React, { useEffect, useState } from "react";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";
import {
  createPlatformNotice,
  deletePlatformNotice,
  getPlatformNotices,
} from "../../api/gyms";
import { createNotice, deleteNotice, listNotices } from "../../api/notices";
import type { GymNotice } from "../../types/notice";

interface NoticeBoardSectionProps {
  userRole: string;
}

export const NoticeBoardSection: React.FC<NoticeBoardSectionProps> = ({
  userRole,
}) => {
  const [notices, setNotices] = useState<GymNotice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Post modal state
  const [isPostOpen, setIsPostOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);
  const [postSuccessNotice, setPostSuccessNotice] = useState<{
    text: string;
    variant: "success" | "warning";
  } | null>(null);

  const canPost =
    userRole === "owner" || userRole === "manager" || userRole === "super_admin";

  const fetchNotices = async () => {
    try {
      setLoading(true);
      setError(null);
      const data =
        userRole === "super_admin"
          ? ((await getPlatformNotices()) as unknown as GymNotice[])
          : await listNotices();
      setNotices(data);
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load notice board.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotices();
  }, []);

  const handleOpenPost = () => {
    setTitle("");
    setBody("");
    setPostError(null);
    setIsPostOpen(true);
  };

  const handlePostSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPostError(null);
    setPostSuccessNotice(null);

    const trimmedTitle = title.trim();
    const trimmedBody = body.trim();

    if (trimmedTitle.length < 2 || trimmedTitle.length > 100) {
      setPostError("Notice title must be between 2 and 100 characters.");
      return;
    }

    if (trimmedBody.length < 5 || trimmedBody.length > 1000) {
      setPostError("Notice body must be between 5 and 1,000 characters.");
      return;
    }

    try {
      setSubmitting(true);
      if (userRole === "super_admin") {
        await createPlatformNotice(trimmedTitle, trimmedBody);
        setIsPostOpen(false);
        await fetchNotices();
        setPostSuccessNotice({
          text: "Platform-wide announcement posted to every gym Owner.",
          variant: "success",
        });
      } else {
        const result = await createNotice({
          title: trimmedTitle,
          body: trimmedBody,
        });

        setIsPostOpen(false);
        await fetchNotices();

        if (result.telegram_sent) {
          setPostSuccessNotice({
            text: "Notice published in-app and broadcast to Telegram channel.",
            variant: "success",
          });
        } else {
          setPostSuccessNotice({
            text: `Notice published in-app (not sent to Telegram: ${result.telegram_note || "not configured"}).`,
            variant: "warning",
          });
        }
      }
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to publish notice.";
      setPostError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, noticeTitle: string) => {
    if (
      !window.confirm(
        `Are you sure you want to delete notice '${noticeTitle}'?`
      )
    ) {
      return;
    }

    try {
      if (userRole === "super_admin") {
        await deletePlatformNotice(id);
      } else {
        await deleteNotice(id);
      }
      await fetchNotices();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to delete notice.";
      setError(msg);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">
            Notice Board
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {canPost
              ? "Publish announcements to gym members and broadcast to your Telegram channel."
              : "Latest announcements and news from gym management."}
          </p>
        </div>
        {canPost && (
          <Button variant="primary" onClick={handleOpenPost}>
            Post Notice
          </Button>
        )}
      </div>

      {postSuccessNotice && (
        <Alert
          variant={postSuccessNotice.variant}
          onClose={() => setPostSuccessNotice(null)}
        >
          {postSuccessNotice.text}
        </Alert>
      )}

      {error && <Alert variant="danger">{error}</Alert>}

      {/* Loading */}
      {loading && (
        <div className="flex justify-center p-8">
          <Spinner size="lg" />
        </div>
      )}

      {/* Notices List */}
      {!loading && notices.length === 0 && (
        <Card className="p-8 text-center text-text-muted">
          <p className="text-base font-medium">No announcements posted yet.</p>
          <p className="text-xs mt-1">
            {canPost
              ? "Click 'Post Notice' to share your first announcement."
              : "Check back later for updates from your gym."}
          </p>
        </Card>
      )}

      {!loading && notices.length > 0 && (
        <div className="space-y-4">
          {notices.map((n) => (
            <Card key={n.id} className="p-5 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-text">{n.title}</h2>
                    {Boolean(
                      (n as unknown as { is_platform_wide?: boolean })
                        .is_platform_wide
                    ) && <Badge variant="primary">Platform Announcement</Badge>}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-text-muted">
                    <span>Posted by {n.posted_by_name || "Gym Staff"}</span>
                    <span>•</span>
                    <span>
                      {new Date(n.created_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                </div>
                {canPost &&
                  (!(n as unknown as { is_platform_wide?: boolean })
                    .is_platform_wide ||
                    userRole === "super_admin") && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(n.id, n.title)}
                      className="text-danger hover:text-danger hover:bg-danger/10 self-start sm:self-auto"
                    >
                      Delete
                    </Button>
                  )}
              </div>
              <div className="text-sm text-text whitespace-pre-wrap leading-relaxed">
                {n.body}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Post Notice Modal */}
      <Modal
        isOpen={isPostOpen}
        onClose={() => setIsPostOpen(false)}
        title="Post Notice Announcement"
      >
        <form onSubmit={handlePostSubmit} className="space-y-4">
          {postError && <Alert variant="danger">{postError}</Alert>}

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-medium text-text-muted">
                Title *
              </label>
              <span className="text-[11px] text-text-muted">
                {title.length} / 100
              </span>
            </div>
            <Input
              required
              maxLength={100}
              placeholder="e.g. Holiday Hours & Special Schedule"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-medium text-text-muted">
                Announcement Body *
              </label>
              <span className="text-[11px] text-text-muted">
                {body.length} / 1000
              </span>
            </div>
            <textarea
              required
              rows={5}
              maxLength={1000}
              placeholder="Write announcement details here (up to 1,000 characters)..."
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="p-3 bg-surface-2/60 border border-border rounded-lg text-xs text-text-muted">
            If a Telegram channel is configured in Gym Settings, this notice
            will also broadcast automatically.
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsPostOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? "Publishing..." : "Publish Notice"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
