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
import {
  filterPhoneInput,
  focusFirstInvalidField,
  validateEmail,
  validateName,
  validatePaymentAmount,
  validatePhone,
  validateSubdomain,
  validateTextLength,
} from "../../utils/validators";

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
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

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
  const [ownerEmailConfirm, setOwnerEmailConfirm] = useState("");
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
      if (prefillData.contact_phone)
        setContactPhone(filterPhoneInput(prefillData.contact_phone));
      if (prefillData.contact_email) {
        setContactEmail(prefillData.contact_email);
        setOwnerEmail(prefillData.contact_email);
        setOwnerEmailConfirm(prefillData.contact_email);
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
    setFieldErrors({});

    const errors: Record<string, string> = {};
    const nameErr = validateName(name, "Gym name", 2, 100);
    if (nameErr) errors.name = nameErr;

    const subErr = validateSubdomain(subdomain);
    if (subErr) errors.subdomain = subErr;

    if (location.trim()) {
      const locErr = validateTextLength(location, "Location", 0, 100);
      if (locErr) errors.location = locErr;
    }

    if (contactName.trim()) {
      const cNameErr = validateName(contactName, "Contact name", 2, 100);
      if (cNameErr) errors.contact_name = cNameErr;
    }

    if (contactPhone.trim()) {
      const cPhoneErr = validatePhone(contactPhone, false);
      if (cPhoneErr) errors.contact_phone = cPhoneErr;
    }

    if (contactEmail.trim()) {
      const cEmailErr = validateEmail(contactEmail, false);
      if (cEmailErr) errors.contact_email = cEmailErr;
    }

    if (ownerName.trim()) {
      const oNameErr = validateName(ownerName, "Owner name", 2, 100);
      if (oNameErr) errors.owner_name = oNameErr;
    }

    const oEmailErr = validateEmail(ownerEmail, true);
    if (oEmailErr) errors.owner_email = oEmailErr;

    if (!ownerEmailConfirm.trim()) {
      errors.owner_email_confirm = "Please confirm the owner email address.";
    } else if (
      ownerEmailConfirm.trim().toLowerCase() !== ownerEmail.trim().toLowerCase()
    ) {
      errors.owner_email_confirm = "Owner email confirmation does not match.";
    }

    const payErr = validatePaymentAmount(paymentAmount);
    if (payErr) errors.payment_amount = payErr;

    const refErr = validateTextLength(
      paymentReference,
      "Bank reference",
      3,
      100
    );
    if (refErr) errors.payment_reference = refErr;

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setIsSubmitting(true);

    try {
      const resp = await createGym({
        name: name.trim(),
        subdomain: subdomain.trim().toLowerCase(),
        tier,
        location: location.trim(),
        contact_name: contactName.trim(),
        contact_phone: contactPhone.trim(),
        contact_email: contactEmail.trim().toLowerCase(),
        owner_name: ownerName.trim(),
        owner_email: ownerEmail.trim().toLowerCase(),
        owner_email_confirm: ownerEmailConfirm.trim().toLowerCase(),
        payment_amount: paymentAmount.trim(),
        payment_reference: paymentReference.trim(),
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
      setOwnerEmailConfirm("");
      setPaymentReference("");
      setFieldErrors({});
      fetchGyms();
    } catch (err: unknown) {
      const errorObj = err as {
        response?: { data?: Record<string, string[] | string> };
      };
      if (errorObj.response?.data) {
        const serverFieldErrors: Record<string, string> = {};
        const generalMessages: string[] = [];
        Object.entries(errorObj.response.data).forEach(([k, v]) => {
          const msg = Array.isArray(v) ? v.join(" ") : String(v);
          serverFieldErrors[k] = msg;
          generalMessages.push(`${k}: ${msg}`);
        });
        setFieldErrors(serverFieldErrors);
        setErrorMessage(generalMessages.join(" | "));
        focusFirstInvalidField(serverFieldErrors);
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
            <a
              href={
                createSuccess.gym_url ||
                createSuccess.gym.url ||
                `https://${createSuccess.gym.subdomain}.${import.meta.env.VITE_DOMAIN || "fitgate.tebebtech.com"}/`
              }
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline hover:opacity-80 font-mono font-medium"
            >
              {createSuccess.gym_url ||
                createSuccess.gym.url ||
                `https://${createSuccess.gym.subdomain}.${import.meta.env.VITE_DOMAIN || "fitgate.tebebtech.com"}/`}
            </a>
            ) &bull; Tier:{" "}
            <span className="uppercase">{createSuccess.gym.tier}</span>
          </p>
          <div className="mt-2 text-xs bg-surface-2 p-2.5 rounded border border-border">
            <span className="font-medium text-text">
              Owner Set-Password Invite Email Sent:
            </span>
            <div className="text-text-muted mt-1">
              An invitation email containing the single-use set-password link
              has been dispatched to{" "}
              <strong>{createSuccess.owner.email}</strong>.
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

            <form
              onSubmit={handleCreateGym}
              className="space-y-4 mt-4"
              noValidate
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField
                  label="Gym Name"
                  htmlFor="gym-name"
                  required
                  error={fieldErrors.name}
                >
                  <Input
                    id="gym-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Bole Power Fitness"
                    maxLength={100}
                    error={fieldErrors.name}
                    required
                  />
                </FormField>

                <div className="flex flex-col justify-end">
                  <FormField
                    label="Subdomain"
                    htmlFor="gym-subdomain"
                    required
                    error={fieldErrors.subdomain}
                  >
                    <div className="flex gap-2">
                      <Input
                        id="gym-subdomain"
                        value={subdomain}
                        onChange={(e) => setSubdomain(e.target.value)}
                        placeholder="bole-power"
                        maxLength={63}
                        error={fieldErrors.subdomain}
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

                <FormField
                  label="Location"
                  htmlFor="gym-location"
                  error={fieldErrors.location}
                >
                  <Input
                    id="gym-location"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. Bole Atlas"
                    maxLength={100}
                    error={fieldErrors.location}
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField
                  label="Contact Name"
                  htmlFor="gym-contact-name"
                  error={fieldErrors.contact_name}
                >
                  <Input
                    id="gym-contact-name"
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    placeholder="Contact person"
                    maxLength={100}
                    error={fieldErrors.contact_name}
                  />
                </FormField>

                <FormField
                  label="Contact Phone"
                  htmlFor="gym-contact-phone"
                  error={fieldErrors.contact_phone}
                >
                  <Input
                    id="gym-contact-phone"
                    value={contactPhone}
                    onChange={(e) =>
                      setContactPhone(filterPhoneInput(e.target.value))
                    }
                    placeholder="+251911..."
                    inputMode="tel"
                    maxLength={20}
                    error={fieldErrors.contact_phone}
                  />
                </FormField>
              </div>

              <div className="border-t border-border pt-4">
                <div className="text-xs font-semibold text-text-muted uppercase mb-3">
                  Owner Account Details
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <FormField
                    label="Owner Name"
                    htmlFor="gym-owner-name"
                    error={fieldErrors.owner_name}
                  >
                    <Input
                      id="gym-owner-name"
                      value={ownerName}
                      onChange={(e) => setOwnerName(e.target.value)}
                      placeholder="Full Name"
                      maxLength={100}
                      error={fieldErrors.owner_name}
                    />
                  </FormField>

                  <FormField
                    label="Owner Email"
                    htmlFor="gym-owner-email"
                    required
                    error={fieldErrors.owner_email}
                  >
                    <Input
                      id="gym-owner-email"
                      type="email"
                      value={ownerEmail}
                      onChange={(e) => setOwnerEmail(e.target.value)}
                      placeholder="owner@example.com"
                      maxLength={254}
                      error={fieldErrors.owner_email}
                      required
                    />
                  </FormField>

                  <FormField
                    label="Confirm Owner Email"
                    htmlFor="gym-owner-email-confirm"
                    required
                    error={fieldErrors.owner_email_confirm}
                  >
                    <Input
                      id="gym-owner-email-confirm"
                      type="email"
                      value={ownerEmailConfirm}
                      onChange={(e) => setOwnerEmailConfirm(e.target.value)}
                      placeholder="owner@example.com"
                      maxLength={254}
                      error={fieldErrors.owner_email_confirm}
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
                    error={fieldErrors.payment_amount}
                  >
                    <Input
                      id="gym-payment-amount"
                      type="number"
                      step="0.01"
                      min="1"
                      inputMode="decimal"
                      value={paymentAmount}
                      onChange={(e) => setPaymentAmount(e.target.value)}
                      error={fieldErrors.payment_amount}
                      required
                    />
                  </FormField>

                  <FormField
                    label="Bank Reference"
                    htmlFor="gym-payment-ref"
                    required
                    error={fieldErrors.payment_reference}
                  >
                    <Input
                      id="gym-payment-ref"
                      value={paymentReference}
                      onChange={(e) => setPaymentReference(e.target.value)}
                      placeholder="e.g. CBE-TX-998811"
                      maxLength={100}
                      error={fieldErrors.payment_reference}
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
                  disabled={isSubmitting}
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
