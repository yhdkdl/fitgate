import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../ui/Card";
import { listNotices } from "../../api/notices";
import type { GymNotice } from "../../types/notice";

export const MemberNoticesCard: React.FC = () => {
  const [latestNotice, setLatestNotice] = useState<GymNotice | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        const data = await listNotices();
        if (isMounted && data.length > 0) {
          setLatestNotice(data[0]);
        }
      } catch {
        // Non-blocking
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  if (!latestNotice) {
    return null;
  }

  return (
    <Card className="p-5 border-border bg-surface-2/40 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">📢</span>
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Latest Announcement
          </span>
        </div>
        <Link
          to="/notices"
          className="text-xs font-medium text-primary hover:underline"
        >
          View all notices →
        </Link>
      </div>

      <div>
        <h3 className="text-base font-bold text-text">{latestNotice.title}</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Posted on{" "}
          {new Date(latestNotice.created_at).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
          })}
        </p>
      </div>

      <p className="text-sm text-text line-clamp-3 whitespace-pre-wrap leading-relaxed">
        {latestNotice.body}
      </p>
    </Card>
  );
};
