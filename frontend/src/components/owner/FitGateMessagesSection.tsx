import React, { useEffect, useState } from "react";
import { getGymPlatformNotices, type PlatformNotice } from "../../api/gyms";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";

export const FitGateMessagesSection: React.FC = () => {
  const [notices, setNotices] = useState<PlatformNotice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await getGymPlatformNotices();
        if (isMounted) setNotices(data);
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg =
          (err as { data?: { detail?: string } })?.data?.detail ||
          "Failed to load FitGate messages.";
        setError(msg);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text">
          FitGate Messages
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Official platform announcements and notifications from FitGate Administration.
        </p>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}

      {loading && (
        <div className="flex justify-center p-8">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && notices.length === 0 && (
        <Card className="p-8 text-center text-text-muted text-sm">
          No platform notices currently on record for your gym.
        </Card>
      )}

      {!loading && notices.length > 0 && (
        <div className="space-y-4">
          {notices.map((n) => (
            <Card key={n.id} className="bg-surface border-border p-5 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
                  <h2 className="text-base font-bold text-text">{n.title}</h2>
                  <Badge variant="primary" className="text-[10px]">
                    FitGate Platform
                  </Badge>
                </div>
                <div className="text-xs text-text-muted">
                  {new Date(n.created_at).toLocaleDateString()} &bull;{" "}
                  {new Date(n.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </div>

              <div className="text-sm text-text whitespace-pre-wrap leading-relaxed">
                {n.message}
              </div>

              {n.show_until && (
                <div className="text-[11px] text-text-muted pt-2 border-t border-border/50">
                  Visible until {new Date(n.show_until).toLocaleDateString()}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
