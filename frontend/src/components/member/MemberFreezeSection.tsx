import React, { useEffect, useState } from "react";
import { getMemberProfileMe, type Member } from "../../api/members";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Spinner } from "../ui/Spinner";
import { MemberFreezeCard } from "./MemberFreezeCard";

export const MemberFreezeSection: React.FC = () => {
  const [profile, setProfile] = useState<Member | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadProfile() {
      try {
        setLoading(true);
        setError(null);
        const data = await getMemberProfileMe();
        if (isMounted) setProfile(data);
      } catch (err: unknown) {
        if (isMounted) {
          setError(
            err instanceof Error ? err.message : "Failed to load member profile."
          );
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadProfile();
    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center flex flex-col items-center gap-3">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">Loading membership freeze options...</p>
      </div>
    );
  }

  if (error || !profile) {
    return <Alert variant="danger">{error || "Member profile not found."}</Alert>;
  }

  return (
    <div className="space-y-6">
      {/* Page Title & Status Header */}
      <div className="bg-surface border border-border rounded-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl sm:text-2xl font-bold text-text">
              Membership Freeze
            </h2>
            <Badge
              variant={
                profile.status === "active"
                  ? "success"
                  : profile.status === "frozen"
                  ? "warning"
                  : "secondary"
              }
              className="capitalize"
            >
              {profile.status}
            </Badge>
          </div>
          <p className="text-xs text-text-muted mt-1">
            Request to pause your pass and extend your subscription expiration date.
          </p>
        </div>
      </div>

      {/* Currently Frozen Notice */}
      {profile.status === "frozen" && (
        <Alert variant="warning">
          <strong>Your membership is currently frozen.</strong> Check-in passes are
          temporarily paused. Your pass will automatically reactivate when the freeze
          period ends, or front-desk staff can end your freeze early if you return sooner.
        </Alert>
      )}

      {/* Suspended Notice */}
      {profile.status === "suspended" && (
        <Alert variant="danger">
          <strong>Your membership is currently suspended.</strong> You cannot request
          a membership freeze while suspended. Please contact the front desk.
        </Alert>
      )}

      {/* Pending Notice */}
      {profile.status === "pending" && (
        <Alert variant="warning">
          <strong>You do not have an active subscription yet.</strong> Please purchase or
          activate a membership plan at the front desk or online before requesting a freeze.
        </Alert>
      )}

      {/* Main Freeze Management Card & Requests History */}
      <MemberFreezeCard memberStatus={profile.status} />
    </div>
  );
};
