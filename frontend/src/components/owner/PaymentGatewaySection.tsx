import React, { useEffect, useState } from "react";
import {
  getGymPaymentConfig,
  updateGymPaymentConfig,
  testGymPaymentConfig,
  getGymReceivingAccounts,
  createGymReceivingAccount,
  deleteGymReceivingAccount,
  type GymPaymentConfig,
  type GymReceivingAccount,
} from "../../api/payments";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";

interface PaymentGatewaySectionProps {
  onUpdated?: () => void;
}

export const PaymentGatewaySection: React.FC<PaymentGatewaySectionProps> = ({
  onUpdated,
}) => {
  const [config, setConfig] = useState<GymPaymentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [togglingSwitch, setTogglingSwitch] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form fields
  const [publicKey, setPublicKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [showSecrets, setShowSecrets] = useState(false);

  // Receiving Accounts & Bank Receipt Verification state (Sprint 12d)
  const [receivingAccounts, setReceivingAccounts] = useState<
    GymReceivingAccount[]
  >([]);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [isAddingAccount, setIsAddingAccount] = useState(false);
  const [newBank, setNewBank] = useState("cbe");
  const [newAccountNumber, setNewAccountNumber] = useState("");
  const [newAccountHolderName, setNewAccountHolderName] = useState("");
  const [accountError, setAccountError] = useState<string | null>(null);
  const [savingAccount, setSavingAccount] = useState(false);
  const [togglingVerification, setTogglingVerification] = useState(false);

  const accounts = Array.isArray(receivingAccounts) ? receivingAccounts : [];

  const fetchConfig = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await getGymPaymentConfig();
      setConfig(data);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to load payment configuration."
      );
    } finally {
      setLoading(false);
    }
  };

  const fetchReceivingAccounts = async () => {
    setLoadingAccounts(true);
    try {
      const data = await getGymReceivingAccounts();
      setReceivingAccounts(Array.isArray(data) ? data : []);
    } catch {
      // Ignore initial account fetch error if none
      setReceivingAccounts([]);
    } finally {
      setLoadingAccounts(false);
    }
  };

  useEffect(() => {
    fetchConfig();
    fetchReceivingAccounts();
  }, []);

  const handleToggleAutoVerification = async () => {
    const nextVal = !config?.verify_bank_receipts_automatically;
    if (nextVal && accounts.length === 0) {
      setErrorMsg(
        "Add at least one receiving account to enable bank receipt verification."
      );
      return;
    }
    setTogglingVerification(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await updateGymPaymentConfig({
        verify_bank_receipts_automatically: nextVal,
      });
      setConfig(updated);
      setSuccessMsg(
        nextVal
          ? "Automatic bank receipt verification enabled."
          : "Automatic bank receipt verification disabled."
      );
      if (onUpdated) onUpdated();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to update receipt verification status."
      );
    } finally {
      setTogglingVerification(false);
    }
  };

  const handleFailurePolicyChange = async (
    policy: "activate_and_reconcile_later" | "hold_for_approval"
  ) => {
    setTogglingVerification(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await updateGymPaymentConfig({
        receipt_verification_failure_policy: policy,
      });
      setConfig(updated);
      setSuccessMsg(
        policy === "hold_for_approval"
          ? "Unchecked receipts will now be held for Owner or Manager review."
          : "Unchecked receipts will activate immediately and reconcile later."
      );
      if (onUpdated) onUpdated();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to update failure policy."
      );
    } finally {
      setTogglingVerification(false);
    }
  };

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setAccountError(null);
    const accNum = newAccountNumber.trim();
    if (!accNum) {
      setAccountError("Account number or phone is required.");
      return;
    }

    if (newBank === "cbe" && !/^\d{13}$/.test(accNum)) {
      setAccountError("CBE account number must be exactly 13 digits.");
      return;
    }

    if (newBank === "telebirr" && !/^(?:\+251|0)?9\d{8}$/.test(accNum)) {
      setAccountError(
        "Telebirr wallet phone must be a valid 10-digit Ethiopian mobile (09... or +2519...)."
      );
      return;
    }

    setSavingAccount(true);
    try {
      await createGymReceivingAccount({
        bank: newBank,
        account_number: accNum,
        account_holder_name: newAccountHolderName.trim() || undefined,
      });
      setNewAccountNumber("");
      setNewAccountHolderName("");
      setIsAddingAccount(false);
      setSuccessMsg("Receiving account added successfully.");
      await fetchReceivingAccounts();
      await fetchConfig();
      if (onUpdated) onUpdated();
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: unknown } };
      const detail = errorObj?.data?.detail;
      setAccountError(
        typeof detail === "string"
          ? detail
          : err instanceof Error
            ? err.message
            : "Failed to add receiving account."
      );
    } finally {
      setSavingAccount(false);
    }
  };

  const handleDeleteAccount = async (id: string) => {
    if (!window.confirm("Remove this receiving bank account?")) return;
    try {
      await deleteGymReceivingAccount(id);
      setSuccessMsg("Receiving account removed.");
      await fetchReceivingAccounts();
      await fetchConfig();
      if (onUpdated) onUpdated();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to remove receiving account."
      );
    }
  };

  const handleToggleOnlinePayments = async () => {
    const nextState = !config?.is_enabled;
    if (nextState && !config?.is_verified) {
      setErrorMsg("Verify your Chapa connection first.");
      return;
    }
    setTogglingSwitch(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await updateGymPaymentConfig({ is_enabled: nextState });
      setConfig(updated);
      if (!nextState) {
        const count = updated.unfinished_online_payments ?? 0;
        setSuccessMsg(
          count > 0
            ? `Online payments disabled. Note: ${count} unfinished online payment${count === 1 ? " is" : "s are"} in progress.`
            : "Online payments disabled."
        );
      } else {
        setSuccessMsg("Online payments enabled successfully.");
      }
      if (onUpdated) onUpdated();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to update online payment status."
      );
    } finally {
      setTogglingSwitch(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const payload: Record<string, string> = {};
      if (publicKey.trim()) payload.public_key = publicKey.trim();
      if (secretKey.trim()) payload.secret_key = secretKey.trim();
      if (webhookSecret.trim()) payload.webhook_secret = webhookSecret.trim();

      const updated = await updateGymPaymentConfig(payload);
      setConfig(updated);
      setPublicKey("");
      setSecretKey("");
      setWebhookSecret("");
      setSuccessMsg(
        "Chapa credentials encrypted and saved successfully. Please test your connection to enable online member checkout."
      );
      if (onUpdated) onUpdated();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to save payment credentials."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const result = await testGymPaymentConfig();
      if (result.success) {
        setSuccessMsg(
          result.message ||
            "Chapa connection verified successfully! Online checkout is enabled."
        );
        fetchConfig();
        if (onUpdated) onUpdated();
      } else {
        setErrorMsg(result.message || "Chapa connection test failed.");
      }
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Connection test failed. Please verify your Chapa credentials."
      );
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3">
          <Spinner size="sm" />
          <span className="text-xs text-text-muted">
            Loading payment configuration...
          </span>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
        <div>
          <h2 className="text-lg font-bold text-text flex items-center gap-2">
            Chapa Payment Gateway
            {config?.is_configured ? (
              <Badge variant={config.is_test_mode ? "warning" : "success"}>
                {config.is_test_mode ? "Test Mode" : "Live Mode"}
              </Badge>
            ) : (
              <Badge variant="secondary">Not Configured</Badge>
            )}
            {config?.is_verified ? (
              <Badge variant={config.use_mock ? "warning" : "success"}>
                {config.use_mock
                  ? "Simulated (mock mode): not checked with Chapa"
                  : "Verified & Active"}
              </Badge>
            ) : (
              config?.is_configured && (
                <Badge variant="secondary">Not Verified</Badge>
              )
            )}
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Configure your gym's Chapa merchant keys to enable online membership
            checkout. Checks your secret key with Chapa. The webhook secret is
            confirmed when the first payment arrives.
          </p>
        </div>

        {config?.is_configured && (
          <div className="flex flex-col sm:items-end gap-1">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleTestConnection}
              disabled={testing}
            >
              {testing ? "Testing Connection..." : "Test Connection"}
            </Button>
            <span className="text-[10px] text-text-muted text-left sm:text-right max-w-xs">
              Checks your secret key with Chapa. The webhook secret is confirmed
              when the first payment arrives.
            </span>
          </div>
        )}
      </div>

      {config?.use_mock && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-3 text-xs text-warning font-medium">
          Test environment: payments are simulated
        </div>
      )}

      {successMsg && <Alert variant="success">{successMsg}</Alert>}
      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

      {/* Current Configuration Summary */}
      {config?.is_configured && (
        <div className="bg-surface-2 p-4 rounded-lg space-y-2 border border-border/60">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Active Credentials (Masked)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-text-muted">Public Key:</span>{" "}
              <code className="font-mono text-text font-medium">
                {config.masked_public_key || "None"}
              </code>
            </div>
            <div>
              <span className="text-text-muted">Secret Key:</span>{" "}
              <span className="text-text font-medium">
                {config.has_secret_key
                  ? "•••••••• (Encrypted at rest)"
                  : "Not Set"}
              </span>
            </div>
            <div>
              <span className="text-text-muted">Webhook Secret:</span>{" "}
              <span className="text-text font-medium">
                {config.has_webhook_secret
                  ? "•••••••• (Encrypted at rest)"
                  : "Not Set"}
              </span>
            </div>
          </div>
          {config.verified_at && (
            <p className="text-[11px] text-text-muted mt-2">
              Last verified: {new Date(config.verified_at).toLocaleString()}
            </p>
          )}
        </div>
      )}

      {/* Online Payments Switch (Accept online payments) */}
      <div className="bg-surface-2 p-5 rounded-lg border border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-text">
              Accept online payments (Chapa)
            </span>
            <Badge variant={config?.is_enabled ? "success" : "secondary"}>
              {config?.is_enabled ? "Enabled" : "Disabled"}
            </Badge>
          </div>
          <p className="text-xs text-text-muted max-w-xl">
            When turned off, members must pay at the front desk (cash or bank
            transfer). Keys and verified connection status are preserved.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              aria-label="Accept online payments (Chapa)"
              className="sr-only peer"
              checked={Boolean(config?.is_enabled)}
              disabled={togglingSwitch || saving}
              onChange={handleToggleOnlinePayments}
            />
            <div className="w-11 h-6 bg-surface-3 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-border after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>
      </div>

      {/* Bank Receipt Verification & Receiving Accounts (Sprint 12d) */}
      <div className="bg-surface-2 p-5 rounded-lg border border-border/60 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/50 pb-3">
          <div>
            <h3 className="text-base font-bold text-text flex items-center gap-2">
              Bank Receipt Verification (Cheki)
              <Badge
                variant={
                  config?.verify_bank_receipts_automatically
                    ? "success"
                    : "secondary"
                }
              >
                {config?.verify_bank_receipts_automatically ? "Active" : "Off"}
              </Badge>
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              Automatically verifies member bank transfer receipt references
              against bank systems in direct mode.
            </p>
          </div>

          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              aria-label="Verify bank receipts automatically"
              className="sr-only peer"
              checked={Boolean(config?.verify_bank_receipts_automatically)}
              disabled={
                togglingVerification || saving || accounts.length === 0
              }
              onChange={handleToggleAutoVerification}
            />
            <div className="w-11 h-6 bg-surface-3 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-border after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>

        {accounts.length === 0 && (
          <p className="text-xs text-amber-500 font-medium">
            ⚠️ Add at least one receiving account below to enable automatic bank
            receipt verification.
          </p>
        )}

        {/* Failure Policy Selection */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-text uppercase tracking-wider text-[10px]">
            If a receipt cannot be checked:
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <label
              className={`p-3 rounded-lg border cursor-pointer flex items-start gap-2.5 transition-colors ${
                (config?.receipt_verification_failure_policy ||
                  "activate_and_reconcile_later") ===
                "activate_and_reconcile_later"
                  ? "border-primary bg-primary/5"
                  : "border-border bg-surface"
              }`}
            >
              <input
                type="radio"
                name="failurePolicy"
                className="mt-0.5"
                checked={
                  (config?.receipt_verification_failure_policy ||
                    "activate_and_reconcile_later") ===
                  "activate_and_reconcile_later"
                }
                onChange={() =>
                  handleFailurePolicyChange("activate_and_reconcile_later")
                }
                disabled={togglingVerification}
              />
              <div>
                <span className="font-semibold text-text block">
                  Activate now and reconcile later (Default)
                </span>
                <span className="text-[11px] text-text-muted">
                  Membership activates immediately without delay. The Owner
                  reconciles the transfer later against bank statements.
                </span>
              </div>
            </label>

            <label
              className={`p-3 rounded-lg border cursor-pointer flex items-start gap-2.5 transition-colors ${
                config?.receipt_verification_failure_policy ===
                "hold_for_approval"
                  ? "border-primary bg-primary/5"
                  : "border-border bg-surface"
              }`}
            >
              <input
                type="radio"
                name="failurePolicy"
                className="mt-0.5"
                checked={
                  config?.receipt_verification_failure_policy ===
                  "hold_for_approval"
                }
                onChange={() => handleFailurePolicyChange("hold_for_approval")}
                disabled={togglingVerification}
              />
              <div>
                <span className="font-semibold text-text block">
                  Hold for Owner or Manager approval
                </span>
                <span className="text-[11px] text-text-muted">
                  Membership does NOT activate until an Owner or Manager reviews
                  statement and decides in the queue.
                </span>
              </div>
            </label>
          </div>
        </div>

        {/* Receiving Bank Accounts List */}
        <div className="space-y-3 pt-2 border-t border-border/50">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-text uppercase tracking-wider text-[10px]">
              Gym Receiving Accounts ({accounts.length}/5)
            </h4>
            {!isAddingAccount && accounts.length < 5 && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setAccountError(null);
                  setIsAddingAccount(true);
                }}
              >
                + Add Account
              </Button>
            )}
          </div>

          {accountError && <Alert variant="danger">{accountError}</Alert>}

          {/* Add Account Inline Form */}
          {isAddingAccount && (
            <form
              onSubmit={handleAddAccount}
              className="bg-surface p-4 rounded-lg border border-border space-y-3"
            >
              <h5 className="text-xs font-bold text-text">
                Add Receiving Bank Account
              </h5>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] text-text-muted mb-1">
                    Bank / Channel
                  </label>
                  <select
                    value={newBank}
                    onChange={(e) => setNewBank(e.target.value)}
                    className="w-full text-xs rounded border border-border bg-surface-2 p-2 text-text"
                  >
                    <option value="cbe">
                      Commercial Bank of Ethiopia (CBE)
                    </option>
                    <option value="telebirr">Ethio Telecom Telebirr</option>
                    <option value="boa">Bank of Abyssinia (BOA)</option>
                    <option value="mpesa">Safaricom M-Pesa</option>
                    <option value="awash">Awash Bank</option>
                    <option value="dashen">Dashen Bank</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-text-muted mb-1">
                    {newBank === "telebirr"
                      ? "Phone Number (10 digits)"
                      : "Account Number (13 digits for CBE)"}
                  </label>
                  <Input
                    type="text"
                    placeholder={
                      newBank === "telebirr"
                        ? "0911223344"
                        : newBank === "cbe"
                          ? "1000123456789"
                          : "Account number"
                    }
                    value={newAccountNumber}
                    onChange={(e) => setNewAccountNumber(e.target.value)}
                    className="font-mono text-xs"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-text-muted mb-1">
                    Account Holder Name
                  </label>
                  <Input
                    type="text"
                    placeholder="e.g. Bole Gym PLC"
                    value={newAccountHolderName}
                    onChange={(e) => setNewAccountHolderName(e.target.value)}
                    className="text-xs"
                  />
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <Button
                  type="submit"
                  size="sm"
                  variant="primary"
                  disabled={savingAccount}
                >
                  {savingAccount ? "Saving..." : "Save Account"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={savingAccount}
                  onClick={() => {
                    setIsAddingAccount(false);
                    setAccountError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}

          {/* Accounts List Table */}
          {loadingAccounts ? (
            <div className="flex items-center gap-2 text-xs text-text-muted py-2">
              <Spinner size="sm" />
              <span>Loading receiving accounts...</span>
            </div>
          ) : accounts.length === 0 ? (
            <div className="text-xs text-text-muted italic bg-surface p-3 rounded border border-border">
              No receiving accounts configured. Add your gym's CBE or Telebirr
              account to receive and verify receipts.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse bg-surface rounded-lg border border-border">
                <thead>
                  <tr className="border-b border-border text-text-muted bg-surface-2/60">
                    <th className="py-2 px-3 font-semibold">Bank</th>
                    <th className="py-2 px-3 font-semibold">Account / Phone</th>
                    <th className="py-2 px-3 font-semibold">Holder Name</th>
                    <th className="py-2 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {accounts.map((acc) => (
                    <tr key={acc.id} className="hover:bg-surface-2/40">
                      <td className="py-2.5 px-3 font-medium uppercase text-text">
                        {acc.bank}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-text">
                        {acc.account_number}
                      </td>
                      <td className="py-2.5 px-3 text-text-muted">
                        {acc.account_holder_name || "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-danger hover:underline p-0 h-auto"
                          onClick={() => handleDeleteAccount(acc.id)}
                        >
                          Delete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Credentials Update Form */}
      <form onSubmit={handleSave} className="space-y-4">
        <h3 className="text-sm font-semibold text-text">
          {config?.is_configured ? "Update Credentials" : "Enter Credentials"}
        </h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-text mb-1">
              Chapa Public Key
            </label>
            <Input
              type="text"
              placeholder="e.g. CHAPUBK_TEST-xxxxxxxxxxxx or CHAPUBK-xxxxxxxxxxxx"
              value={publicKey}
              onChange={(e) => setPublicKey(e.target.value)}
              className="font-mono text-xs"
            />
            <p className="text-[11px] text-text-muted mt-1">
              Used on the client-side checkout and to determine test or live
              mode.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-text mb-1">
              Chapa Secret Key
            </label>
            <Input
              type={showSecrets ? "text" : "password"}
              placeholder="e.g. CHASECK_TEST-xxxxxxxxxxxx or CHASECK-xxxxxxxxxxxx"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              className="font-mono text-xs"
            />
            <p className="text-[11px] text-text-muted mt-1">
              Used for server-to-server transaction verification. Never returned
              in any API or logged.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-text mb-1">
              Chapa Webhook Secret (Secret Hash)
            </label>
            <Input
              type={showSecrets ? "text" : "password"}
              placeholder="Custom secret hash set in your Chapa webhook settings"
              value={webhookSecret}
              onChange={(e) => setWebhookSecret(e.target.value)}
              className="font-mono text-xs"
            />
            <p className="text-[11px] text-text-muted mt-1">
              Used to cryptographically verify HMAC-SHA256 signatures on
              incoming payment webhooks.
            </p>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="show-secrets"
              checked={showSecrets}
              onChange={(e) => setShowSecrets(e.target.checked)}
              className="rounded border-border text-primary focus:ring-primary"
            />
            <label
              htmlFor="show-secrets"
              className="text-xs text-text-muted cursor-pointer"
            >
              Reveal secret keys in input fields while editing
            </label>
          </div>
        </div>

        <div className="pt-2 flex items-center justify-between">
          <Button type="submit" variant="primary" disabled={saving}>
            {saving ? "Encrypting & Saving..." : "Save Credentials"}
          </Button>
          <span className="text-[11px] text-text-muted italic">
            Owner-only access · AES-Fernet encrypted
          </span>
        </div>
      </form>
    </Card>
  );
};
