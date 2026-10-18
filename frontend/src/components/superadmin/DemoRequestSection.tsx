import React, { useState, useEffect, useCallback } from "react";
import {
  Building2,
  CheckCircle,
  Filter,
  Loader2,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  UserCheck,
  X,
} from "lucide-react";
import {
  listDemoRequests,
  updateDemoRequest,
  getDemoRequestConvertData,
  type DemoRequest,
  type DemoRequestStatus,
  type DemoRequestConvertResponse,
} from "../../api/demoRequests";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";

interface DemoRequestSectionProps {
  onConvertToGym?: (data: DemoRequestConvertResponse) => void;
}

export const DemoRequestSection: React.FC<DemoRequestSectionProps> = ({
  onConvertToGym,
}) => {
  const [requests, setRequests] = useState<DemoRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Lead review modal state
  const [selectedLead, setSelectedLead] = useState<DemoRequest | null>(null);
  const [leadStatus, setLeadStatus] = useState<DemoRequestStatus>("new");
  const [leadNotes, setLeadNotes] = useState<string>("");
  const [savingLead, setSavingLead] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [converting, setConverting] = useState(false);

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDemoRequests(statusFilter || undefined);
      setRequests(data);
    } catch {
      setError("Failed to load demo requests.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleOpenLead = (lead: DemoRequest) => {
    setSelectedLead(lead);
    setLeadStatus(lead.status as DemoRequestStatus);
    setLeadNotes(lead.notes || "");
    setModalError(null);
    setNotesError(null);
  };

  const handleCloseLead = () => {
    setSelectedLead(null);
    setModalError(null);
    setNotesError(null);
  };

  const handleSaveLead = async () => {
    if (!selectedLead) return;
    setModalError(null);
    setNotesError(null);

    if (leadNotes.length > 1000) {
      setNotesError("Notes must not exceed 1000 characters.");
      return;
    }

    setSavingLead(true);
    try {
      const updated = await updateDemoRequest(selectedLead.id, {
        status: leadStatus,
        notes: leadNotes.trim(),
      });
      setSelectedLead(updated);
      setRequests((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r))
      );
    } catch {
      setModalError("Failed to update demo request.");
    } finally {
      setSavingLead(false);
    }
  };

  const handleConvertLead = async () => {
    if (!selectedLead) return;
    setConverting(true);
    try {
      const convertData = await getDemoRequestConvertData(selectedLead.id);
      handleCloseLead();
      if (onConvertToGym) {
        onConvertToGym(convertData);
      }
    } catch {
      setModalError("Failed to retrieve conversion data.");
    } finally {
      setConverting(false);
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case "new":
        return <Badge variant="primary">New</Badge>;
      case "contacted":
        return <Badge variant="neutral">Contacted</Badge>;
      case "demo_done":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
            Demo Done
          </span>
        );
      case "converted":
        return <Badge variant="success">Converted</Badge>;
      case "lost":
        return <Badge variant="danger">Lost</Badge>;
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-text">Demo Requests & Leads</h2>
          <p className="text-sm text-text-muted">
            Track inquiries from prospective gym owners and convert qualified
            leads into active gyms.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={fetchRequests}
          disabled={loading}
          className="flex items-center gap-1.5"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-b border-border pb-3">
        <span className="text-xs font-medium text-text-muted flex items-center gap-1 mr-2">
          <Filter className="w-3.5 h-3.5" /> Filter:
        </span>
        {[
          { label: "All", value: "" },
          { label: "New", value: "new" },
          { label: "Contacted", value: "contacted" },
          { label: "Demo Done", value: "demo_done" },
          { label: "Converted", value: "converted" },
          { label: "Lost", value: "lost" },
        ].map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              statusFilter === tab.value
                ? "bg-primary text-white"
                : "bg-surface-2 text-text-muted hover:text-text hover:bg-surface-3"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <Card className="overflow-hidden border-border bg-surface">
        {loading && requests.length === 0 ? (
          <div className="p-8 text-center text-text-muted">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
            Loading demo requests...
          </div>
        ) : requests.length === 0 ? (
          <div className="p-8 text-center text-text-muted">
            No demo requests found matching the current filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-2/60 text-xs text-text-muted uppercase tracking-wider border-b border-border">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Gym & Location</th>
                  <th className="px-4 py-3">Contact</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Handled By</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {requests.map((req) => (
                  <tr
                    key={req.id}
                    className="hover:bg-surface-2/40 transition-colors"
                  >
                    <td className="px-4 py-3 text-text-muted text-xs whitespace-nowrap">
                      {req.created_at
                        ? new Date(req.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-text">
                        {req.gym_name}
                      </div>
                      {req.city && (
                        <div className="text-xs text-text-muted flex items-center gap-1 mt-0.5">
                          <MapPin className="w-3 h-3" /> {req.city}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-text font-medium">
                        {req.contact_name}
                      </div>
                      <div className="text-xs text-text-muted flex items-center gap-1 mt-0.5">
                        <Phone className="w-3 h-3" /> {req.phone}
                      </div>
                      {req.email && (
                        <div className="text-xs text-text-muted flex items-center gap-1">
                          <Mail className="w-3 h-3" /> {req.email}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">{getStatusBadge(req.status)}</td>
                    <td className="px-4 py-3 text-xs text-text-muted">
                      {req.handled_by_email || "—"}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleOpenLead(req)}
                      >
                        Review Lead
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Lead Review & Status Modal */}
      {selectedLead && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-xl bg-surface border border-border rounded-card shadow-2xl p-6 relative max-h-[90vh] overflow-y-auto space-y-6">
            <div className="flex justify-between items-start border-b border-border pb-4">
              <div>
                <h3 className="text-lg font-bold text-text flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-primary" />
                  {selectedLead.gym_name}
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Requested on{" "}
                  {selectedLead.created_at
                    ? new Date(selectedLead.created_at).toLocaleString()
                    : "—"}
                </p>
              </div>
              <button
                onClick={handleCloseLead}
                className="text-text-muted hover:text-text p-1 rounded-lg transition-colors"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {modalError && <Alert variant="danger">{modalError}</Alert>}

            {/* Lead Information Card */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-surface-2/40 p-4 rounded-card border border-border/80 text-sm">
              <div>
                <span className="text-xs text-text-muted block">
                  Contact Person
                </span>
                <span className="font-medium text-text">
                  {selectedLead.contact_name}
                </span>
              </div>
              <div>
                <span className="text-xs text-text-muted block">
                  Phone Number
                </span>
                <a
                  href={`tel:${selectedLead.phone}`}
                  className="font-medium text-primary hover:underline"
                >
                  {selectedLead.phone}
                </a>
              </div>
              <div>
                <span className="text-xs text-text-muted block">
                  Email Address
                </span>
                <span className="text-text">{selectedLead.email || "—"}</span>
              </div>
              <div>
                <span className="text-xs text-text-muted block">Location</span>
                <span className="text-text">{selectedLead.city || "—"}</span>
              </div>
              {selectedLead.message && (
                <div className="sm:col-span-2 pt-2 border-t border-border/40">
                  <span className="text-xs text-text-muted block mb-1">
                    Inquiry Message
                  </span>
                  <p className="text-xs text-text bg-surface/60 p-2.5 rounded border border-border/60">
                    {selectedLead.message}
                  </p>
                </div>
              )}
              {selectedLead.converted_gym_subdomain && (
                <div className="sm:col-span-2 pt-2 border-t border-border/40 flex items-center gap-2 text-xs text-emerald-400">
                  <CheckCircle className="w-4 h-4" />
                  Converted to Gym Tenant:{" "}
                  <span className="font-semibold underline">
                    {selectedLead.converted_gym_subdomain}
                  </span>
                </div>
              )}
            </div>

            {/* Status & Notes Editing */}
            <div className="space-y-4">
              <FormField label="Lead Status" htmlFor="lead-status-select">
                <select
                  id="lead-status-select"
                  value={leadStatus}
                  onChange={(e) =>
                    setLeadStatus(e.target.value as DemoRequestStatus)
                  }
                  className="w-full px-3.5 py-2.5 bg-surface text-text border rounded-input border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                >
                  <option value="new">New (Uncontacted)</option>
                  <option value="contacted">Contacted (In Discussion)</option>
                  <option value="demo_done">
                    Demo Done (Completed Presentation)
                  </option>
                  <option value="converted">
                    Converted (Became Gym Tenant)
                  </option>
                  <option value="lost">Lost (Not Interested / Dropped)</option>
                </select>
              </FormField>

              <FormField
                label="Internal Notes & Follow-up Log"
                htmlFor="lead-notes"
                error={notesError || undefined}
              >
                <textarea
                  id="lead-notes"
                  rows={4}
                  maxLength={1000}
                  value={leadNotes}
                  onChange={(e) => setLeadNotes(e.target.value)}
                  placeholder="e.g. Called owner on Monday, requested pricing details for 2 branches..."
                  className="w-full px-3.5 py-2.5 bg-surface text-text placeholder-text-muted border rounded-input border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                />
              </FormField>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row justify-between items-center gap-3 pt-4 border-t border-border">
              <Button
                variant="primary"
                onClick={handleConvertLead}
                disabled={converting || selectedLead.status === "converted"}
                className="w-full sm:w-auto flex items-center gap-1.5"
              >
                <UserCheck className="w-4 h-4" />
                {converting ? "Loading Data..." : "Convert to Gym"}
              </Button>

              <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                <Button variant="secondary" onClick={handleCloseLead}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSaveLead}
                  disabled={savingLead}
                >
                  {savingLead ? "Saving..." : "Save Notes"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
