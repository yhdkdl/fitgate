import React, { useEffect, useState } from "react";
import {
  getGymDetails,
  updateGymDetails,
  getGymSettings,
  getGymSubscription,
  updateGymSettings,
  uploadGymLogo,
  type GymSubscriptionDetails,
} from "../../api/gyms";
import { testTelegramBroadcast } from "../../api/notices";
import { useAuth } from "../../context/AuthContext";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";
import {
  ExternalLink,
  Eye,
  Palette,
  QrCode,
  Sparkles,
} from "lucide-react";
import {
  focusFirstInvalidField,
  filterPhoneInput,
  validatePhone,
  validateAddress,
  validateHexColor,
  validateReminderDays,
  getTwoLargestReminderDays,
} from "../../utils/validators";
import {
  BRAND_COLOR_PRESETS,
  HERO_IMAGE_PRESETS,
  getGymLandingCustomization,
  saveGymLandingCustomization,
  resolveHeroImage,
} from "../../utils/gymLandingCustomization";

interface GymBrandingSectionProps {
  gymId?: string;
  onUpdated?: () => void;
}

export const GymBrandingSection: React.FC<GymBrandingSectionProps> = ({
  gymId,
  onUpdated,
}) => {
  const { user, capabilities } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);

  const [publicContactPhone, setPublicContactPhone] = useState("");
  const [gymLocation, setGymLocation] = useState("");
  const [savingDetails, setSavingDetails] = useState(false);
  const [detailsSuccessMsg, setDetailsSuccessMsg] = useState<string | null>(null);
  const [detailsErrorMsg, setDetailsErrorMsg] = useState<string | null>(null);
  const [detailsFieldErrors, setDetailsFieldErrors] = useState<Record<string, string>>({});
  const [brandColor, setBrandColor] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [showUnavailableEquipment, setShowUnavailableEquipment] =
    useState(false);
  const [isEquipmentListComplete, setIsEquipmentListComplete] = useState(false);
  const [telegramChannel, setTelegramChannel] = useState("");
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [telegramTestResult, setTelegramTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [memberReminderFirst, setMemberReminderFirst] = useState("7");
  const [memberReminderSecond, setMemberReminderSecond] = useState("2");
  const [freezeDaysAllowed, setFreezeDaysAllowed] = useState<number>(0);
  const [freezeDaysCap, setFreezeDaysCap] = useState<number>(30);
  const [gymTier, setGymTier] = useState<string>("");
  const [subscription, setSubscription] = useState<GymSubscriptionDetails | null>(
    null
  );

  // Landing page appearance customizer state
  const [heroMotto, setHeroMotto] = useState("Train Hard. Stay Strong.");
  const [heroSubtitle, setHeroSubtitle] = useState("");
  const [heroImagePreset, setHeroImagePreset] = useState("modern-iron");
  const [customHeroImage, setCustomHeroImage] = useState("");
  const [operatingHours, setOperatingHours] = useState("Mon - Sun: 6:00 AM - 10:00 PM");

  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

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
        setIsEquipmentListComplete(Boolean(res.is_equipment_list_complete));
        setTelegramChannel(
          (res as { telegram_channel?: string }).telegram_channel || ""
        );
        const [firstRem, secondRem] = getTwoLargestReminderDays(res.member_reminder_days);
        setMemberReminderFirst(firstRem || "7");
        setMemberReminderSecond(secondRem || "2");
        setFreezeDaysAllowed(
          res.freeze_days_allowed !== undefined ? res.freeze_days_allowed : 0
        );
        setFreezeDaysCap(
          res.freeze_days_cap !== undefined ? res.freeze_days_cap : 30
        );
        setGymTier((res as { tier?: string }).tier || "");

        // Load landing customization
        const targetId = gymId || user?.gym_id;
        const landing = getGymLandingCustomization(targetId);
        if (landing.heroMotto) setHeroMotto(landing.heroMotto);
        if (landing.heroSubtitle) setHeroSubtitle(landing.heroSubtitle);
        if (landing.heroImagePreset) setHeroImagePreset(landing.heroImagePreset);
        if (landing.customHeroImage) setCustomHeroImage(landing.customHeroImage);
        if (landing.operatingHours) setOperatingHours(landing.operatingHours);

        if (user?.role === "owner" && !gymId) {
          try {
            const det = await getGymDetails();
            if (isMounted) {
              setPublicContactPhone(det.public_contact_phone || "");
              setGymLocation(det.location || "");
            }
          } catch {
            // ignore
          }
        }
        if (user?.role === "owner" && !gymId) {
          try {
            const sub = await getGymSubscription();
            if (isMounted) setSubscription(sub);
          } catch {
            // ignore
          }
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
  }, [gymId, user]);

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

  const handleSaveDetails = async (e: React.FormEvent) => {
    e.preventDefault();
    setDetailsSuccessMsg(null);
    setDetailsErrorMsg(null);
    setDetailsFieldErrors({});

    const errors: Record<string, string> = {};
    const phoneErr = validatePhone(publicContactPhone, true);
    if (phoneErr) errors.public_contact_phone = phoneErr;

    if (gymLocation.trim()) {
      const locErr = validateAddress(gymLocation, false);
      if (locErr) errors.location = locErr;
    }

    if (Object.keys(errors).length > 0) {
      setDetailsFieldErrors(errors);
      return;
    }

    setSavingDetails(true);
    try {
      await updateGymDetails({
        public_contact_phone: publicContactPhone.trim(),
        location: gymLocation.trim(),
      });
      setDetailsSuccessMsg("Gym details updated successfully.");
    } catch {
      setDetailsErrorMsg("Failed to update gym details. Please check your inputs.");
    } finally {
      setSavingDetails(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg(null);
    setErrorMsg(null);
    setFieldErrors({});

    const errors: Record<string, string> = {};
    const trimmedChannel = telegramChannel.trim();
    if (
      trimmedChannel &&
      !/^@[a-zA-Z][a-zA-Z0-9_]{4,31}$/.test(trimmedChannel)
    ) {
      errors.telegram_channel =
        "Telegram channel must be in the format @channel_name (5–32 letters, digits, or underscores starting with a letter).";
    }

    const trimmedColor = brandColor.trim();
    if (trimmedColor) {
      const colorErr = validateHexColor(trimmedColor, "Brand color");
      if (colorErr) errors.brand_color_text = colorErr;
    }

    // Parse reminder days
    const { firstError, secondError } = validateReminderDays(
      memberReminderFirst,
      memberReminderSecond
    );
    if (firstError) {
      errors.member_reminder_first = firstError;
    }
    if (secondError) {
      errors.member_reminder_second = secondError;
    }

    if (gymTier === "starter") {
      if (freezeDaysAllowed > 0) {
        errors.freeze_days_allowed =
          "Starter gyms cannot use membership freeze.";
      }
    } else {
      if (freezeDaysAllowed < 0) {
        errors.freeze_days_allowed = "Freeze days allowed cannot be negative.";
      } else if (freezeDaysAllowed > freezeDaysCap) {
        errors.freeze_days_allowed = `Cannot exceed maximum freeze allowance cap of ${freezeDaysCap} days.`;
      }
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    const reminderDays = memberReminderSecond.trim() !== ""
      ? [parseInt(memberReminderFirst, 10), parseInt(memberReminderSecond, 10)]
      : [parseInt(memberReminderFirst, 10)];

    try {
      setSaving(true);
      await updateGymSettings(
        {
          brand_color: trimmedColor || null,
          show_unavailable_equipment: showUnavailableEquipment,
          is_equipment_list_complete: isEquipmentListComplete,
          telegram_channel: trimmedChannel || null,
          member_reminder_days: reminderDays,
          freeze_days_allowed:
            gymTier === "starter" ? 0 : Number(freezeDaysAllowed),
        },
        gymId
      );

      // Save custom landing appearance
      const targetId = gymId || user?.gym_id;
      saveGymLandingCustomization(targetId, {
        heroMotto: heroMotto.trim() || undefined,
        heroSubtitle: heroSubtitle.trim() || undefined,
        heroImagePreset,
        customHeroImage: customHeroImage.trim() || undefined,
        operatingHours: operatingHours.trim() || undefined,
      });

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

  const handleTestTelegram = async () => {
    setTelegramTestResult(null);
    setTestingTelegram(true);
    try {
      const res = await testTelegramBroadcast();
      setTelegramTestResult({ success: res.success, message: res.detail });
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to send test message.";
      setTelegramTestResult({ success: false, message: msg });
    } finally {
      setTestingTelegram(false);
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

  const currentPreviewCover = resolveHeroImage({
    heroImagePreset,
    customHeroImage,
  });

  return (
    <div className="space-y-6">
      {/* Quick Launch & Live Landing Page Preview Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-[#0B1324] to-slate-900 border border-slate-800 text-white shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full animate-pulse"
              style={{ backgroundColor: brandColor || "#A3E635" }}
            />
            <h3 className="text-base font-black uppercase tracking-wider text-white">
              Public Gym Landing Page
            </h3>
          </div>
          <p className="text-xs text-slate-400 max-w-xl">
            Your gym has its own dedicated portal with athletic full-screen styling, animated WebGL light rays, and direct member registration.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/entry?preview=true"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-xs font-black uppercase tracking-wider rounded-xl shadow-lg transition"
            style={{
              backgroundColor: brandColor || "#A3E635",
              color: "#020617",
            }}
          >
            <Eye className="w-4 h-4" />
            <span>Preview Landing Page</span>
            <ExternalLink className="w-3.5 h-3.5 opacity-70" />
          </a>
        </div>
      </div>

      <Card className="bg-surface border-border p-6 space-y-6">
        <div className="border-b border-border pb-3">
          <h2 className="text-lg font-bold text-text">
            Gym Branding & Operational Settings
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Configure your portal&apos;s visual identity (brand accent, logo) and
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
                id="brand_color_text"
                label="Brand Accent Color (Hex)"
                helpText="Used as a high-contrast accent highlight on your public portal."
                error={fieldErrors.brand_color_text}
              >
                <div className="space-y-2">
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
                      maxLength={7}
                      error={fieldErrors.brand_color_text}
                      className="font-mono text-sm"
                    />
                  </div>

                  {/* Preset Swatches */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[11px] font-semibold text-text-muted mr-1">
                      Presets:
                    </span>
                    {BRAND_COLOR_PRESETS.map((preset) => (
                      <button
                        key={preset.hex}
                        type="button"
                        onClick={() => setBrandColor(preset.hex)}
                        className={`px-2 py-0.5 text-[11px] font-semibold rounded-md border flex items-center gap-1 transition ${
                          brandColor.toUpperCase() === preset.hex.toUpperCase()
                            ? "border-slate-900 bg-slate-200 text-slate-900 font-bold"
                            : "border-border bg-surface-2 text-text hover:bg-surface"
                        }`}
                      >
                        <span
                          className="w-2.5 h-2.5 rounded-full border border-black/20"
                          style={{ backgroundColor: preset.hex }}
                        />
                        <span>{preset.name}</span>
                      </button>
                    ))}
                  </div>
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

          {/* Landing Page Content Customizer Section */}
          <div className="pt-6 border-t border-border space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-text flex items-center gap-2">
                  <Palette className="w-4 h-4 text-primary" />
                  <span>Landing Page Content &amp; Imagery</span>
                </h3>
                <p className="text-xs text-text-muted">
                  Personalize your public banner headline, hero photography, and operating schedule.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                id="hero_motto"
                label="Hero Motto Tag"
                helpText="Short motivational badge on top of your headline."
              >
                <Input
                  id="hero_motto"
                  value={heroMotto}
                  onChange={(e) => setHeroMotto(e.target.value)}
                  placeholder="e.g. Train Hard. Stay Strong."
                />
              </FormField>

              <FormField
                id="operating_hours"
                label="Operating Schedule"
                helpText="Displayed on your top announcement ribbon and location section."
              >
                <Input
                  id="operating_hours"
                  value={operatingHours}
                  onChange={(e) => setOperatingHours(e.target.value)}
                  placeholder="e.g. Mon - Sun: 6:00 AM - 10:00 PM"
                />
              </FormField>
            </div>

            <FormField
              id="hero_subtitle"
              label="Hero Welcome Pitch"
              helpText="Brief description explaining your gym's environment and member experience."
            >
              <textarea
                id="hero_subtitle"
                rows={2}
                value={heroSubtitle}
                onChange={(e) => setHeroSubtitle(e.target.value)}
                placeholder="e.g. Modern equipment, certified trainers, and touchless entrance gates for Addis Ababa fitness enthusiasts."
                className="w-full text-xs rounded-input border border-border bg-surface-2 p-3 text-text focus:ring-2 focus:ring-primary focus:outline-none"
              />
            </FormField>

            {/* Hero Cover Photography Selector */}
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-text block">
                Hero Cover Photography
              </label>
              <p className="text-xs text-text-muted">
                Choose a curated athletic preset or specify your gym&apos;s custom facility photo URL.
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-1">
                {HERO_IMAGE_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => {
                      setHeroImagePreset(preset.id);
                      setCustomHeroImage("");
                    }}
                    className={`relative rounded-xl overflow-hidden border-2 transition text-left group ${
                      heroImagePreset === preset.id && !customHeroImage
                        ? "border-primary ring-2 ring-primary/30"
                        : "border-border hover:border-slate-500"
                    }`}
                  >
                    <img
                      src={preset.url}
                      alt={preset.name}
                      className="w-full h-20 object-cover group-hover:scale-105 transition duration-300"
                    />
                    <div className="p-1.5 bg-surface text-[10px] font-semibold text-text truncate">
                      {preset.name}
                    </div>
                  </button>
                ))}
              </div>

              <div className="pt-2">
                <Input
                  id="custom_hero_image"
                  value={customHeroImage}
                  onChange={(e) => setCustomHeroImage(e.target.value)}
                  placeholder="Or enter custom image URL: https://..."
                  className="text-xs font-mono"
                />
              </div>
            </div>

            {/* Live Interactive Hero Mockup */}
            <div className="rounded-xl overflow-hidden border border-slate-800 bg-[#070A11] p-4 text-white space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-slate-800">
                <span className="font-bold uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" style={{ color: brandColor || "#A3E635" }} />
                  <span>Real-Time Landing Hero Preview</span>
                </span>
                <span className="text-[11px]">Dynamic WebGL Rays Enabled</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
                <div className="md:col-span-8 space-y-2">
                  <span
                    className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider"
                    style={{
                      backgroundColor: `${brandColor || "#A3E635"}22`,
                      color: brandColor || "#A3E635",
                    }}
                  >
                    {heroMotto || "Train Hard. Stay Strong."}
                  </span>
                  <div className="text-xl font-black uppercase tracking-tight">
                    Welcome to <span style={{ color: brandColor || "#A3E635" }}>Your Gym</span>
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-2">
                    {heroSubtitle ||
                      "Fast QR check-ins, automated training programs, and certified trainer support."}
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <span
                      className="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-950 uppercase"
                      style={{ backgroundColor: brandColor || "#A3E635" }}
                    >
                      Choose Plan
                    </span>
                    <span className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-slate-800 border border-slate-700">
                      Member Login
                    </span>
                  </div>
                </div>

                <div className="md:col-span-4">
                  <div className="rounded-lg overflow-hidden border border-slate-800 relative h-28">
                    <img
                      src={currentPreviewCover}
                      alt="Cover Preview"
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent flex items-end p-2">
                      <span className="text-[10px] font-bold text-slate-200 flex items-center gap-1">
                        <QrCode className="w-3 h-3 text-[#A3E635]" />
                        <span>Instant QR Gate</span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Freeze Days Allowed & Member Reminder Days */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-border">
            {(capabilities?.has_freeze || (gymTier && gymTier !== "starter")) && (
              <FormField
                id="freeze_days_allowed"
                label="Freeze days allowed"
                helpText={`Annual freeze days allowed per member (0 up to the gym cap of ${freezeDaysCap} days).`}
                error={fieldErrors.freeze_days_allowed}
              >
                <div className="space-y-1">
                  <Input
                    id="freeze_days_allowed"
                    type="number"
                    min={0}
                    max={freezeDaysCap}
                    value={freezeDaysAllowed}
                    onChange={(e) =>
                      setFreezeDaysAllowed(parseInt(e.target.value, 10) || 0)
                    }
                    error={fieldErrors.freeze_days_allowed}
                    className="text-sm"
                  />
                  <span className="text-[11px] text-text-muted">
                    Platform Cap: {freezeDaysCap} days (set by Super Admin)
                  </span>
                </div>
              </FormField>
            )}

            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-sm font-medium text-text">
                  Membership renewal reminders: remind each member and Reception this many days before a membership ends
                </label>
                <p className="text-xs text-text-muted">
                  First reminder is required (1 to 90 days). Second reminder is optional and must be smaller than the first.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField
                  id="member_reminder_first"
                  label="First reminder"
                  error={fieldErrors.member_reminder_first}
                >
                  <Input
                    id="member_reminder_first"
                    type="number"
                    min={1}
                    max={90}
                    value={memberReminderFirst}
                    onChange={(e) => setMemberReminderFirst(e.target.value)}
                    placeholder="7"
                    error={fieldErrors.member_reminder_first}
                  />
                </FormField>

                <FormField
                  id="member_reminder_second"
                  label="Second reminder (optional)"
                  error={fieldErrors.member_reminder_second}
                >
                  <Input
                    id="member_reminder_second"
                    type="number"
                    min={1}
                    max={90}
                    value={memberReminderSecond}
                    onChange={(e) => setMemberReminderSecond(e.target.value)}
                    placeholder="2"
                    error={fieldErrors.member_reminder_second}
                  />
                </FormField>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
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

          <div className="flex items-center gap-3 pt-1">
            <input
              type="checkbox"
              id="is_equipment_list_complete"
              checked={isEquipmentListComplete}
              onChange={(e) => setIsEquipmentListComplete(e.target.checked)}
              className="w-5 h-5 rounded border-border bg-surface-2 text-primary focus:ring-ring cursor-pointer"
            />
            <label
              htmlFor="is_equipment_list_complete"
              className="text-sm text-text cursor-pointer select-none"
            >
              My equipment list is complete (AI workout plans use only registered
              usable gym equipment)
            </label>
          </div>

          {/* Telegram Channel Bridge */}
          <div className="pt-4 border-t border-border space-y-3">
            <FormField
              id="telegram_channel"
              label="Telegram Channel Bridge (Optional)"
              helpText="Add the FitGate platform bot to your public Telegram channel as an Administrator with 'Post Messages' rights, enter your channel handle here (e.g. @your_gym_channel), save settings, and press 'Send test message'."
              error={fieldErrors.telegram_channel}
            >
              <div className="flex flex-col sm:flex-row gap-2">
                <Input
                  id="telegram_channel"
                  value={telegramChannel}
                  onChange={(e) => setTelegramChannel(e.target.value)}
                  placeholder="@your_gym_channel"
                  maxLength={33}
                  error={fieldErrors.telegram_channel}
                  className="text-sm font-mono flex-1"
                />
                <Button
                  type="button"
                  variant="secondary"
                  disabled={testingTelegram || !telegramChannel.trim()}
                  onClick={handleTestTelegram}
                >
                  {testingTelegram ? "Sending Test..." : "Send test message"}
                </Button>
              </div>
            </FormField>

            {telegramTestResult && (
              <Alert variant={telegramTestResult.success ? "success" : "danger"}>
                {telegramTestResult.message}
              </Alert>
            )}
          </div>

          <div className="flex justify-end pt-4 border-t border-border">
            <Button type="submit" disabled={saving || uploadingLogo}>
              {saving ? "Saving Changes..." : "Save Branding Settings"}
            </Button>
          </div>
        </form>
      </Card>

      {user?.role === "owner" && !gymId && (
        <Card className="bg-surface border-border p-6 space-y-4">
          <div className="border-b border-border pb-3">
            <h2 className="text-lg font-semibold text-text">
              Gym details
            </h2>
            <p className="text-xs text-text-muted mt-0.5">
              Manage your gym&apos;s public phone number and address displayed to members and on your public entry screen.
            </p>
          </div>

          {detailsSuccessMsg && (
            <Alert variant="success">{detailsSuccessMsg}</Alert>
          )}
          {detailsErrorMsg && (
            <Alert variant="danger">{detailsErrorMsg}</Alert>
          )}

          <form onSubmit={handleSaveDetails} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField
                label="Address (shown to members)"
                htmlFor="gym-owner-location"
                error={detailsFieldErrors.location}
                helpText="Physical street address (optional, 3–200 characters)."
              >
                <Input
                  id="gym-owner-location"
                  value={gymLocation}
                  onChange={(e) => setGymLocation(e.target.value)}
                  placeholder="e.g. Bole Atlas, Addis Ababa"
                  maxLength={200}
                  error={detailsFieldErrors.location}
                />
              </FormField>

              <FormField
                label="Public Contact Phone (shown to members)"
                htmlFor="gym-owner-phone"
                error={detailsFieldErrors.public_contact_phone}
                required
                helpText="Displayed on member portal and public entry screen."
              >
                <Input
                  id="gym-owner-phone"
                  value={publicContactPhone}
                  onChange={(e) =>
                    setPublicContactPhone(filterPhoneInput(e.target.value))
                  }
                  placeholder="+251911..."
                  inputMode="tel"
                  maxLength={20}
                  error={detailsFieldErrors.public_contact_phone}
                  required
                />
              </FormField>
            </div>

            <div className="flex justify-end pt-2 border-t border-border">
              <Button type="submit" disabled={savingDetails}>
                {savingDetails ? "Saving Details..." : "Save Gym Details"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {user?.role === "owner" && !gymId && (
        <Card className="bg-surface border-border p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div>
              <h2 className="text-lg font-semibold text-text">
                Your FitGate subscription
              </h2>
              <p className="text-xs text-text-muted mt-0.5">
                Overview of your gym&apos;s current tier, subscription status, and past platform payments.
              </p>
            </div>
            {subscription && (
              <Badge
                variant={
                  subscription.subscription_status === "active"
                    ? "success"
                    : subscription.subscription_status === "terminated"
                      ? "danger"
                      : "warning"
                }
              >
                {subscription.subscription_status}
              </Badge>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-surface-2 p-3 rounded-lg border border-border">
              <span className="text-xs text-text-muted block">Tier</span>
              <span className="text-base font-bold text-text uppercase">
                {subscription?.tier || gymTier || "—"}
              </span>
            </div>
            <div className="bg-surface-2 p-3 rounded-lg border border-border">
              <span className="text-xs text-text-muted block">Status</span>
              <span className="text-base font-bold text-text capitalize">
                {subscription?.subscription_status || "—"}
              </span>
            </div>
            <div className="bg-surface-2 p-3 rounded-lg border border-border">
              <span className="text-xs text-text-muted block">Expires on</span>
              <span className="text-base font-bold text-text">
                {subscription?.subscription_expires_at
                  ? new Date(subscription.subscription_expires_at).toLocaleDateString()
                  : "No expiration"}
              </span>
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <h3 className="text-sm font-semibold text-text">Past Platform Payments</h3>
            {subscription && subscription.past_payments && subscription.past_payments.length > 0 ? (
              <div className="overflow-x-auto border border-border rounded-lg">
                <table className="w-full text-left text-xs text-text">
                  <thead className="bg-surface-2 text-text-muted border-b border-border font-medium">
                    <tr>
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2">Amount (ETB)</th>
                      <th className="px-3 py-2">Method</th>
                      <th className="px-3 py-2">Reference</th>
                      <th className="px-3 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {subscription.past_payments.map((p) => (
                      <tr key={p.id} className="hover:bg-surface-2/40">
                        <td className="px-3 py-2 font-mono">
                          {new Date(p.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-3 py-2 font-semibold">
                          ETB {p.amount_etb}
                        </td>
                        <td className="px-3 py-2 capitalize">{p.payment_method}</td>
                        <td className="px-3 py-2 font-mono text-text-muted">
                          {p.reference || "—"}
                        </td>
                        <td className="px-3 py-2">
                          <Badge
                            variant={p.status === "completed" ? "success" : "neutral"}
                          >
                            {p.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-xs text-text-muted bg-surface-2 p-3 rounded border border-border">
                No past platform payments on record.
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};
