import React, { useEffect, useState } from "react";
import { getMyClients, type TrainerMyClient } from "../../api/trainers";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { AuthenticatedImage } from "../ui/AuthenticatedImage";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";

export const MyClientsSection: React.FC = () => {
  const [clients, setClients] = useState<TrainerMyClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchClients = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const res = await getMyClients();
      setClients(res);
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load assigned clients.";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center flex flex-col items-center gap-3">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">Loading your clients...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-text">
            My Clients
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Active gym members currently assigned to you.
          </p>
        </div>
        <Badge variant="primary">{clients.length} Active Clients</Badge>
      </div>

      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

      <Card className="bg-surface border-border p-5 space-y-4">
        {clients.length === 0 ? (
          <div className="text-center py-10 text-text-muted text-xs">
            You do not have any assigned clients at this time.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="py-2.5 px-3 font-semibold">Client</th>
                  <th className="py-2.5 px-3 font-semibold">Phone</th>
                  <th className="py-2.5 px-3 font-semibold">Membership Plan</th>
                  <th className="py-2.5 px-3 font-semibold">Assignment Date</th>
                  <th className="py-2.5 px-3 font-semibold">Measurements</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {clients.map((c) => (
                  <tr
                    key={c.assignment_id}
                    className="hover:bg-surface-elevated/40"
                  >
                    <td className="py-3 px-3 font-semibold text-text">
                      <div className="flex items-center gap-2.5">
                        {c.photo_url ? (
                          <AuthenticatedImage
                            src={c.photo_url}
                            alt={c.member_name}
                            className="w-8 h-8 rounded-full object-cover border border-border"
                          />
                        ) : (
                          <div className="w-8 h-8 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center text-xs border border-border">
                            {c.member_name.slice(0, 2).toUpperCase()}
                          </div>
                        )}
                        <span>{c.member_name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-text-muted">
                      {c.member_phone}
                    </td>
                    <td className="py-3 px-3 text-text font-medium">
                      {c.plan_name}
                    </td>
                    <td className="py-3 px-3 text-text-muted">
                      {new Date(c.assigned_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-3">
                      {c.has_measurements ? (
                        <Badge variant="success">Recorded</Badge>
                      ) : (
                        <Badge variant="warning">No measurements</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
