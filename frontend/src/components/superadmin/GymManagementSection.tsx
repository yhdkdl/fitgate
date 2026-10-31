import React, { useEffect, useState } from "react";
import {
  confirmGymTls,
  createGym,
  getGymSettings,
  listGyms,
  proposeSubdomain,
  updateGymSettings,
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

  // Config modal states
  const [selectedGymForConfig, setSelectedGymForConfig] = useState<GymTenantSummary | null>(null);
  const [configTier, setConfigTier] = useState<string>("starter");
  const [hasTrainerModule, setHasTrainerModule] = useState(false);
  const [hasAiPlans, setHasAiPlans] = useState(false);
  const [hasAnalytics, setHasAnalytics] = useState(false);
  const [freezeDaysCap, setFreezeDaysCap] = useState<number>(30);
  const [paymentGraceDays, setPaymentGraceDays] = useState<number>(7);
  const [subscriptionReminderDays, setSubscriptionReminderDays] = useState<string>("14, 7");
  const [savingConfig, setSavingConfig] = useState(false);
  const [configSuccessMsg, setConfigSuccessMsg] = useState<string | null>(null);
  const [configErrorMsg, setConfigErrorMsg] = useState<string | null>(null);

  const handleOpenConfig = async (gym: GymTenantSummary) => {
    setSelectedGymForConfig(gym);
    setConfigTier(gym.tier);
    setConfigSuccessMsg(null);
    setConfigErrorMsg(null);
    try {
      const cfg = await getGymSettings(gym.id);
      setHasTrainerModule(Boolean(cfg.has_trainer_module));
      setHasAiPlans(Boolean(cfg.has_ai_plans));
      setHasAnalytics(Boolean(cfg.has_analytics));
      setFreezeDaysCap(cfg.freeze_days_cap !== undefined ? cfg.freeze_days_cap : 30);
      setPaymentGraceDays(cfg.payment_grace_days !== undefined ? cfg.payment_grace_days : 7);
      setSubscriptionReminderDays(
        Array.isArray(cfg.subscription_reminder_days)
          ? cfg.subscription_reminder_days.join(", ")
          : "14, 7"
      );
    } catch {
      setHasTrainerModule(false);
      setHasAiPlans(false);
      setHasAnalytics(false);
      setFreezeDaysCap(30);
      setPaymentGraceDays(7);
      setSubscriptionReminderDays("14, 7");
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedGymForConfig) return;
    setSavingConfig(true);
    setConfigSuccessMsg(null);
    setConfigErrorMsg(null);
    try {
      const reminderParts = subscriptionReminderDays
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => parseInt(s, 10));

      const payload: Record<string, unknown> = {
        has_trainer_module: hasTrainerModule,
        has_ai_plans: hasAiPlans,
        has_analytics: hasAnalytics,
        freeze_days_cap: Number(freezeDaysCap),
        payment_grace_days: Number(paymentGraceDays),
        subscription_reminder_days: reminderParts.length ? reminderParts : [14, 7],
      };
      if (selectedGymForConfig.tier !== "pro") {
        payload.tier = configTier;
      }
      await updateGymSettings(payload, selectedGymForConfig.id);
      setConfigSuccessMsg("Gym configuration and entitlements updated successfully.");
      await fetchGyms();
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setConfigErrorMsg(errObj.message || "Failed to update gym configuration.");
    } finally {
      setSavingConfig(false);
    }
  };

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
                <th className="px-4 py-3">Owner Email</th>
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
                    colSpan={7}
                    className="px-4 py-8 text-center text-text-muted"
                  >
                    Loading gym tenants...
                  </td>
                </tr>
              ) : gyms.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
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
                    <td className="px-4 py-3 text-xs text-text-muted">
                      {gym.owner_email || "—"}
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
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleOpenConfig(gym)}
                          className="text-xs"
                        >
                          Config
                        </Button>
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
                      </div>
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

      {/* Super Admin Gym Config & Entitlement Editor Modal */}
      {selectedGymForConfig && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
          <div className="bg-surface border border-border rounded-card w-full max-w-lg p-6 shadow-2xl my-8">
            <div className="flex items-center justify-between pb-4 border-b border-border">
              <div>
                <h3 className="text-lg font-bold text-text">
                  Configure Gym: {selectedGymForConfig.name}
                </h3>
                <span className="text-xs text-text-muted font-mono">
                  {selectedGymForConfig.subdomain}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedGymForConfig(null)}
                className="text-text-muted hover:text-text font-bold text-xl px-2"
                aria-label="Close"
              >
                &times;
              </button>
            </div>

            {configSuccessMsg && (
              <Alert variant="success" className="mt-4 text-sm">
                {configSuccessMsg}
              </Alert>
            )}
            {configErrorMsg && (
              <Alert variant="danger" className="mt-4 text-sm">
                {configErrorMsg}
              </Alert>
            )}

            <form onSubmit={handleSaveConfig} className="space-y-4 mt-4">
              {/* Tier Selection */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-1.5">
                  Subscription Tier
                </label>
                {selectedGymForConfig.tier === "pro" ? (
                  <div className="p-3 bg-surface-2 rounded-lg border border-border text-sm text-text">
                    <span className="font-bold uppercase text-primary">Pro</span>{" "}
                    <span className="text-xs text-text-muted">(Read-only)</span>
                  </div>
                ) : (
                  <select
                    value={configTier}
                    onChange={(e) => setConfigTier(e.target.value)}
                    className="w-full bg-surface-2 border border-border rounded-input px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px]"
                  >
                    <option value="starter">Starter</option>
                    <option value="growth">Growth</option>
                  </select>
                )}
              </div>

              {/* Entitlement Numbers (Freeze Cap, Grace, Reminders) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-1.5">
                    Freeze Days Cap (0-365)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={365}
                    value={freezeDaysCap}
                    onChange={(e) => setFreezeDaysCap(Math.max(0, Math.min(365, parseInt(e.target.value, 10) || 0)))}
                    className="w-full bg-surface-2 border border-border rounded-input px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px]"
                  />
                  <p className="text-[11px] text-text-muted mt-1">Platform freeze cap for owner (default 30).</p>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-1.5">
                    Payment Grace Days
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={365}
                    value={paymentGraceDays}
                    onChange={(e) => setPaymentGraceDays(Math.max(0, Math.min(365, parseInt(e.target.value, 10) || 0)))}
                    className="w-full bg-surface-2 border border-border rounded-input px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px]"
                  />
                  <p className="text-[11px] text-text-muted mt-1">Days before gym access cuts off (default 7).</p>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-1.5">
                  Subscription Reminder Days
                </label>
                <input
                  type="text"
                  value={subscriptionReminderDays}
                  onChange={(e) => setSubscriptionReminderDays(e.target.value)}
                  placeholder="14, 7"
                  className="w-full bg-surface-2 border border-border rounded-input px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px]"
                />
                <p className="text-[11px] text-text-muted mt-1">Comma-separated days before expiry for renewal reminders.</p>
              </div>

              {/* Feature Entitlements */}
              <div className="space-y-3 pt-2">
                <span className="block text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Feature Entitlements
                </span>
                <label className="flex items-center gap-2 cursor-pointer text-sm text-text">
                  <input
                    type="checkbox"
                    checked={hasTrainerModule}
                    onChange={(e) => setHasTrainerModule(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                  />
                  <span>Trainer Module</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-sm text-text">
                  <input
                    type="checkbox"
                    checked={hasAiPlans}
                    onChange={(e) => setHasAiPlans(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                  />
                  <span>AI Workout Plans</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-sm text-text">
                  <input
                    type="checkbox"
                    checked={hasAnalytics}
                    onChange={(e) => setHasAnalytics(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                  />
                  <span>Analytics & Reports</span>
                </label>
              </div>

              <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setSelectedGymForConfig(null)}
                >
                  Close
                </Button>
                <Button type="submit" variant="primary" disabled={savingConfig}>
                  {savingConfig ? "Saving..." : "Save Changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
