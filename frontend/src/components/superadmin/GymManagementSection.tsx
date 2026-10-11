import React, { useEffect, useState } from "react";
import {
  confirmGymTls,
  createGym,
  listGyms,
  proposeSubdomain,
  type CreateGymResponse,
  type GymTenantSummary,
} from "../../api/gyms";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";

const TIER_PRICES: Record<string, string> = {
  starter: "12000.00",
  growth: "30000.00",
  pro: "60000.00",
};

export interface GymPrefillData {
  demo_request_id?: string;
  name?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  location?: string;
}

interface GymManagementSectionProps {
  prefillData?: GymPrefillData | null;
  onClearPrefill?: () => void;
}

export const GymManagementSection: React.FC<GymManagementSectionProps> = ({
  prefillData,
  onClearPrefill,
}) => {
  const [gyms, setGyms] = useState<GymTenantSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createSuccess, setCreateSuccess] = useState<CreateGymResponse | null>(
    null
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form states
  const [demoRequestId, setDemoRequestId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [tier, setTier] = useState<"starter" | "growth" | "pro">("starter");
  const [location, setLocation] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("12000.00");
  const [paymentReference, setPaymentReference] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  useEffect(() => {
    if (prefillData) {
      if (prefillData.name) setName(prefillData.name);
      if (prefillData.contact_name) {
        setContactName(prefillData.contact_name);
        setOwnerName(prefillData.contact_name);
      }
      if (prefillData.contact_phone) setContactPhone(prefillData.contact_phone);
      if (prefillData.contact_email) {
        setContactEmail(prefillData.contact_email);
        setOwnerEmail(prefillData.contact_email);
      }
      if (prefillData.location) setLocation(prefillData.location);
      if (prefillData.demo_request_id)
        setDemoRequestId(prefillData.demo_request_id);
      setShowCreateModal(true);
      if (prefillData.name) {
        proposeSubdomain(prefillData.name)
          .then(setSubdomain)
          .catch(() => {});
      }
    }
  }, [prefillData]);

  const fetchGyms = async () => {
    setIsLoading(true);
    try {
      const data = await listGyms();
      setGyms(data);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGyms();
  }, []);

  const handleTierChange = (selectedTier: "starter" | "growth" | "pro") => {
    setTier(selectedTier);
    setPaymentAmount(TIER_PRICES[selectedTier] || "12000.00");
  };

  const handleSuggestSubdomain = async () => {
    if (!name.trim()) return;
    try {
      const suggestion = await proposeSubdomain(name);
      setSubdomain(suggestion);
    } catch {
      // ignore
    }
  };

  const handleCreateGym = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      const resp = await createGym({
        name,
        subdomain,
        tier,
        location,
        contact_name: contactName,
        contact_phone: contactPhone,
        contact_email: contactEmail,
        owner_name: ownerName,
        owner_email: ownerEmail,
        payment_amount: paymentAmount,
        payment_reference: paymentReference,
        payment_method: "bank_transfer",
        demo_request_id: demoRequestId || null,
      });

      setCreateSuccess(resp);
      setShowCreateModal(false);
      setDemoRequestId(null);
      if (onClearPrefill) onClearPrefill();
      // Reset form
      setName("");
      setSubdomain("");
      setLocation("");
      setContactName("");
      setContactPhone("");
      setContactEmail("");
      setOwnerName("");
      setOwnerEmail("");
      setPaymentReference("");
      fetchGyms();
    } catch (err: unknown) {
      const errorObj = err as {
        response?: { data?: Record<string, string[] | string> };
      };
      if (errorObj.response?.data) {
        const messages = Object.entries(errorObj.response.data)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
          .join(" | ");
        setErrorMessage(messages);
      } else {
        setErrorMessage("Failed to create gym tenant. Please verify inputs.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmTls = async (gymId: string) => {
    setConfirmingId(gymId);
    try {
      await confirmGymTls(gymId);
      await fetchGyms();
    } catch {
      // ignore
    } finally {
      setConfirmingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-text">Gym Tenants</h2>
          <p className="text-sm text-text-muted mt-0.5">
            Manage provisioned gyms, cPanel subdomains, and TLS certificate
            gates.
          </p>
        </div>
        <Button
          id="btn-open-create-gym"
          variant="primary"
          onClick={() => {
            setShowCreateModal(true);
            setCreateSuccess(null);
          }}
        >
          + Create New Gym
        </Button>
      </div>

      {createSuccess && (
        <Alert variant="success" className="space-y-2">
          <div className="font-semibold text-base">
            Gym Successfully Created & Subdomain Provisioned!
          </div>
          <p className="text-sm">
            Gym: <strong>{createSuccess.gym.name}</strong> (
            <code>{createSuccess.gym.subdomain}.fitgate.org</code>) &bull; Tier:{" "}
            <span className="uppercase">{createSuccess.gym.tier}</span>
          </p>
          <div className="mt-2 text-xs bg-surface-2 p-2.5 rounded border border-border">
            <span className="font-medium text-text">
              Owner Set-Password Invite Link:
            </span>
            <div className="font-mono text-primary break-all select-all mt-1">
              {createSuccess.invite_link}
            </div>
          </div>
        </Alert>
      )}

      {/* Gym Tenants Table */}
      <Card className="bg-surface border-border overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-text">
            <thead className="bg-surface-2 text-text-muted border-b border-border text-xs uppercase font-medium">
              <tr>
                <th className="px-4 py-3">Gym</th>
                <th className="px-4 py-3">Subdomain</th>
                <th className="px-4 py-3">Tier</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">TLS Security</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading && gyms.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-text-muted"
                  >
                    Loading gym tenants...
                  </td>
                </tr>
              ) : gyms.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-text-muted"
                  >
                    No gym tenants registered yet. Click &quot;Create New
                    Gym&quot; to provision the first one.
                  </td>
                </tr>
              ) : (
                gyms.map((gym) => (
                  <tr
                    key={gym.id}
                    className="hover:bg-surface-2/40 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-text">
                      {gym.name}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-primary">
                      {gym.subdomain}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="primary">{gym.tier.toUpperCase()}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={
                          gym.status === "active" ? "success" : "warning"
                        }
                      >
                        {gym.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {gym.tls_confirmed_at ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-success font-medium">
                          <span className="w-2 h-2 rounded-full bg-success" />
                          Secured
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-xs text-warning font-medium">
                          <span className="w-2 h-2 rounded-full bg-warning animate-pulse" />
                          Securing...
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!gym.tls_confirmed_at && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleConfirmTls(gym.id)}
                          isLoading={confirmingId === gym.id}
                          className="text-xs"
                        >
                          Confirm TLS
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal / Form Dialog for Create Gym */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
          <div className="bg-surface border border-border rounded-card w-full max-w-xl p-6 shadow-2xl my-8">
            <div className="flex items-center justify-between pb-4 border-b border-border">
              <h3 className="text-lg font-bold text-text">
                Create Gym & Provision Subdomain
              </h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-text-muted hover:text-text font-bold text-xl px-2"
                aria-label="Close"
              >
                &times;
              </button>
            </div>

            {errorMessage && (
              <Alert variant="danger" className="mt-4 text-sm" role="alert">
                {errorMessage}
              </Alert>
            )}

            <form onSubmit={handleCreateGym} className="space-y-4 mt-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="Gym Name" htmlFor="gym-name" required>
                  <Input
                    id="gym-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Bole Power Fitness"
                    required
                  />
                </FormField>

                <div className="flex flex-col justify-end">
                  <FormField label="Subdomain" htmlFor="gym-subdomain" required>
                    <div className="flex gap-2">
                      <Input
                        id="gym-subdomain"
                        value={subdomain}
                        onChange={(e) => setSubdomain(e.target.value)}
                        placeholder="bole-power"
                        required
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={handleSuggestSubdomain}
                        size="sm"
                        className="shrink-0"
                      >
                        Suggest
                      </Button>
                    </div>
                  </FormField>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="Tier" htmlFor="gym-tier" required>
                  <select
                    id="gym-tier"
                    value={tier}
                    onChange={(e) =>
                      handleTierChange(
                        e.target.value as "starter" | "growth" | "pro"
                      )
                    }
                    className="w-full bg-surface-2 border border-border rounded-input px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px]"
                  >
                    <option value="starter">Starter (12,000 ETB / yr)</option>
                    <option value="growth">Growth (30,000 ETB / yr)</option>
                    <option value="pro">Pro (60,000 ETB / yr)</option>
                  </select>
                </FormField>

                <FormField label="Location" htmlFor="gym-location">
                  <Input
                    id="gym-location"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. Bole Atlas"
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="Contact Name" htmlFor="gym-contact-name">
                  <Input
                    id="gym-contact-name"
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    placeholder="Contact person"
                  />
                </FormField>

                <FormField label="Contact Phone" htmlFor="gym-contact-phone">
                  <Input
                    id="gym-contact-phone"
                    value={contactPhone}
                    onChange={(e) => setContactPhone(e.target.value)}
                    placeholder="+251911..."
                  />
                </FormField>
              </div>

              <div className="border-t border-border pt-4">
                <div className="text-xs font-semibold text-text-muted uppercase mb-3">
                  Owner Account Details
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <FormField label="Owner Name" htmlFor="gym-owner-name">
                    <Input
                      id="gym-owner-name"
                      value={ownerName}
                      onChange={(e) => setOwnerName(e.target.value)}
                      placeholder="Full Name"
                    />
                  </FormField>

                  <FormField
                    label="Owner Email"
                    htmlFor="gym-owner-email"
                    required
                  >
                    <Input
                      id="gym-owner-email"
                      type="email"
                      value={ownerEmail}
                      onChange={(e) => setOwnerEmail(e.target.value)}
                      placeholder="owner@example.com"
                      required
                    />
                  </FormField>
                </div>
              </div>

              <div className="border-t border-border pt-4">
                <div className="text-xs font-semibold text-text-muted uppercase mb-3">
                  Bank Transfer Payment Record
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <FormField
                    label="Amount (ETB)"
                    htmlFor="gym-payment-amount"
                    required
                  >
                    <Input
                      id="gym-payment-amount"
                      type="number"
                      step="0.01"
                      value={paymentAmount}
                      onChange={(e) => setPaymentAmount(e.target.value)}
                      required
                    />
                  </FormField>

                  <FormField
                    label="Bank Reference"
                    htmlFor="gym-payment-ref"
                    required
                  >
                    <Input
                      id="gym-payment-ref"
                      value={paymentReference}
                      onChange={(e) => setPaymentReference(e.target.value)}
                      placeholder="e.g. CBE-TX-998811"
                      required
                    />
                  </FormField>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-border">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  id="btn-submit-create-gym"
                  type="submit"
                  variant="primary"
                  isLoading={isSubmitting}
                >
                  Provision Gym
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
