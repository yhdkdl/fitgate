import React, { useEffect, useState } from "react";
import {
  getGymPaymentConfig,
  updateGymPaymentConfig,
  testGymPaymentConfig,
  type GymPaymentConfig,
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
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form fields
  const [publicKey, setPublicKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [showSecrets, setShowSecrets] = useState(false);

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

  useEffect(() => {
    fetchConfig();
  }, []);

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
