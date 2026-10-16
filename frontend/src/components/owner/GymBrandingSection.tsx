import React, { useEffect, useState } from "react";
import {
  getGymSettings,
  updateGymSettings,
  uploadGymLogo,
} from "../../api/gyms";
import { useAuth } from "../../context/AuthContext";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";

interface GymBrandingSectionProps {
  gymId?: string;
  onUpdated?: () => void;
}

export const GymBrandingSection: React.FC<GymBrandingSectionProps> = ({
  gymId,
  onUpdated,
}) => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);

  const [brandColor, setBrandColor] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [showUnavailableEquipment, setShowUnavailableEquipment] =
    useState(false);
  const [memberReminderDays, setMemberReminderDays] = useState("7, 2");

  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadConfig() {
      try {
        setLoading(true);
        setErrorMsg(null);
        const res = await getGymSettings(gymId);
        if (!isMounted) return;
        setBrandColor(res.brand_color || "#2563EB");
        setLogoUrl(res.logo || "");
        setShowUnavailableEquipment(Boolean(res.show_unavailable_equipment));
        if (Array.isArray(res.member_reminder_days)) {
          setMemberReminderDays(res.member_reminder_days.join(", "));
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg =
          (err as { data?: { detail?: string } })?.data?.detail ||
          "Unable to load gym configuration.";
        setErrorMsg(msg);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadConfig();
    return () => {
      isMounted = false;
    };
  }, [gymId]);

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const targetGymId = gymId || user?.gym_id;
    if (!targetGymId) {
      setErrorMsg("Gym ID required to upload logo.");
      return;
    }

    try {
      setUploadingLogo(true);
      setErrorMsg(null);
      const res = await uploadGymLogo(file, targetGymId);
      setLogoUrl(res.url);
      setSuccessMsg("Gym logo uploaded successfully.");
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Logo upload failed. Please ensure the file is an image under 2MB.";
      setErrorMsg(msg);
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg(null);
    setErrorMsg(null);

    // Validate hex code format if provided
    const trimmedColor = brandColor.trim();
    if (trimmedColor && !/^#[0-9A-Fa-f]{6}$/.test(trimmedColor)) {
      setErrorMsg(
        "Brand color must be a valid 6-character hex code (e.g. #2563EB)."
      );
      return;
    }

    // Parse reminder days
    const reminderDays = memberReminderDays
      .split(",")
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n) && n >= 0);

    try {
      setSaving(true);
      await updateGymSettings(
        {
          brand_color: trimmedColor || null,
          show_unavailable_equipment: showUnavailableEquipment,
          member_reminder_days: reminderDays.length ? reminderDays : undefined,
        },
        gymId
      );

      setSuccessMsg("Gym settings and branding updated successfully.");
      if (onUpdated) onUpdated();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to update gym settings.";
      setErrorMsg(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="bg-surface border-border p-6 flex items-center justify-center">
        <Spinner size="md" />
        <span className="text-sm text-text-muted ml-3">
          Loading gym branding...
        </span>
      </Card>
    );
  }

  return (
    <Card className="bg-surface border-border p-6 space-y-6">
      <div className="border-b border-border pb-3">
        <h2 className="text-lg font-bold text-text">
          Gym Branding & Operational Settings
        </h2>
        <p className="text-xs text-text-muted mt-1">
          Configure your portal's visual identity (brand accent, logo) and
          member reminder frequencies.
        </p>
      </div>

      {successMsg && <Alert variant="success">{successMsg}</Alert>}
      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Brand Color */}
          <div className="space-y-3">
            <FormField
              id="brand_color"
              label="Brand Accent Color (Hex)"
              helpText="Used as a high-contrast accent highlight on your public portal."
            >
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={
                    brandColor.startsWith("#") && brandColor.length === 7
                      ? brandColor
                      : "#2563EB"
                  }
                  onChange={(e) => setBrandColor(e.target.value.toUpperCase())}
                  className="w-11 h-11 rounded-lg border border-border bg-surface-2 cursor-pointer p-1"
                />
                <Input
                  id="brand_color_text"
                  value={brandColor}
                  onChange={(e) => setBrandColor(e.target.value)}
                  placeholder="#2563EB"
                  className="font-mono text-sm"
                />
              </div>
            </FormField>

            <div className="p-3 rounded-lg border border-border bg-surface-2/60 text-xs text-text-muted flex items-center gap-3">
              <div
                className="w-6 h-6 rounded border shrink-0"
                style={{ backgroundColor: brandColor || "#2563EB" }}
              />
              <span>
                Live Accent Preview: {brandColor || "Default (#2563EB)"}
              </span>
            </div>
          </div>

          {/* Logo Upload & URL */}
          <div className="space-y-3">
            <FormField
              id="gym_logo"
              label="Gym Logo"
              helpText="Upload a logo (max 2MB, WebP/PNG/JPEG) or specify an image asset URL."
            >
              <div className="space-y-2">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleLogoUpload}
                  disabled={uploadingLogo}
                  className="block w-full text-xs text-text-muted file:mr-3 file:py-2 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary file:text-white hover:file:bg-primary/90 cursor-pointer"
                />
                {uploadingLogo && (
                  <p className="text-xs text-primary flex items-center gap-2">
                    <Spinner size="sm" /> Uploading and resizing logo...
                  </p>
                )}
                <Input
                  id="logo_url"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  placeholder="https://... or /media/logos/..."
                  className="text-xs"
                />
              </div>
            </FormField>

            {logoUrl && (
              <div className="flex items-center gap-3 p-2 bg-surface-2 rounded border border-border">
                <img
                  src={logoUrl}
                  alt="Gym logo preview"
                  className="w-10 h-10 object-contain rounded border border-border bg-black/40"
                />
                <span className="text-xs text-text-muted truncate">
                  {logoUrl}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Member Reminder Days */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2 border-t border-border">
          <FormField
            id="member_reminder_days"
            label="Member Renewal Reminder Days"
            helpText="Comma-separated days before membership expiry to notify members (default: 7, 2)."
          >
            <Input
              id="member_reminder_days"
              value={memberReminderDays}
              onChange={(e) => setMemberReminderDays(e.target.value)}
              placeholder="7, 2"
            />
          </FormField>

          <div className="flex items-center gap-3 pt-6">
            <input
              type="checkbox"
              id="show_unavailable_equipment"
              checked={showUnavailableEquipment}
              onChange={(e) => setShowUnavailableEquipment(e.target.checked)}
              className="w-5 h-5 rounded border-border bg-surface-2 text-primary focus:ring-ring cursor-pointer"
            />
            <label
              htmlFor="show_unavailable_equipment"
              className="text-sm text-text cursor-pointer select-none"
            >
              Show unavailable equipment to members in catalog
            </label>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-border">
          <Button type="submit" disabled={saving || uploadingLogo}>
            {saving ? "Saving Changes..." : "Save Branding Settings"}
          </Button>
        </div>
      </form>
    </Card>
  );
};
