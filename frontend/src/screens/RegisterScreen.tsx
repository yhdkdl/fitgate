import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  PublicMemberRegistrationPayload,
  registerMemberSelfService,
} from "../api/members";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { PasswordChecklist } from "../components/ui/PasswordChecklist";
import { Spinner } from "../components/ui/Spinner";
import { getTenantFromHostname } from "../utils/tenant";
import {
  checkPasswordRequirements,
  filterPhoneInput,
  focusFirstInvalidField,
  validateDateOfBirth,
  validateEmail,
  validateName,
  validatePhone,
} from "../utils/validators";

export const RegisterScreen: React.FC = () => {
  const tenant = getTenantFromHostname();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [emergencyContact, setEmergencyContact] = useState("");
  const [waiverAccepted, setWaiverAccepted] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    const errors: Record<string, string> = {};

    const nameErr = validateName(fullName, "Full name", 2, 100);
    if (nameErr) errors.full_name = nameErr;

    const emailErr = validateEmail(email, true);
    if (emailErr) errors.email = emailErr;

    const phoneErr = validatePhone(phone, true);
    if (phoneErr) errors.phone = phoneErr;

    const pwdReqs = checkPasswordRequirements(password);
    if (!pwdReqs.isValid) {
      if (!pwdReqs.hasMinLength)
        errors.password = "Password must be at least 10 characters long.";
      else if (!pwdReqs.hasNoCommon)
        errors.password = "Password is too common.";
      else if (!pwdReqs.hasNotOnlyDigits)
        errors.password = "Password cannot be entirely numeric.";
    }

    if (!gender || (gender !== "female" && gender !== "male")) {
      errors.gender = "Please select either Female or Male.";
    }

    if (dateOfBirth) {
      const dobErr = validateDateOfBirth(dateOfBirth);
      if (dobErr) errors.date_of_birth = dobErr;
    }

    if (emergencyContact.trim()) {
      const ecErr = validatePhone(emergencyContact, false);
      if (ecErr) errors.emergency_contact = ecErr;
    }

    if (!waiverAccepted) {
      errors.waiver_accepted =
        "You must accept the health and safety waiver to register.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setLoading(true);

    try {
      const payload: PublicMemberRegistrationPayload = {
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        password,
        waiver_accepted: waiverAccepted,
        date_of_birth: dateOfBirth || null,
        gender: gender || "",
        emergency_contact: emergencyContact.trim(),
      };

      await registerMemberSelfService(payload);
      setSubmittedEmail(email.trim().toLowerCase());
      setSuccess(true);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      if (apiErr.status === 429) {
        setError(
          "Too many registration requests. Please wait a short while before trying again."
        );
      } else if (apiErr.data && typeof apiErr.data === "object") {
        const dataObj = apiErr.data as Record<string, unknown>;
        const formattedErrors: Record<string, string> = {};
        for (const [key, val] of Object.entries(dataObj)) {
          formattedErrors[key] = Array.isArray(val)
            ? val.join(" ")
            : String(val);
        }
        setFieldErrors(formattedErrors);
        focusFirstInvalidField(formattedErrors);
        if (typeof dataObj.detail === "string") {
          setError(dataObj.detail);
        } else if (Array.isArray(dataObj.waiver_accepted)) {
          setError(String(dataObj.waiver_accepted[0]));
        } else {
          setError("Please correct the errors in the form.");
        }
      } else {
        setError(apiErr.message || "Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    const isLocalhost =
      window.location.hostname === "localhost" ||
      window.location.hostname.endsWith(".localhost") ||
      window.location.hostname === "127.0.0.1";

    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-4">
        <Card className="max-w-md w-full bg-surface border-border p-6 sm:p-8 space-y-6 text-center">
          <div className="w-14 h-14 mx-auto rounded-full bg-primary/10 text-primary flex items-center justify-center border border-primary/20">
            <span className="text-2xl">✉️</span>
          </div>

          <div className="space-y-3">
            <Badge variant="primary">Verification Required</Badge>
            <h1 className="text-2xl font-bold text-text">
              Verify Your Account
            </h1>
            <p className="text-sm text-text-muted">
              We sent a single-use verification link to{" "}
              <strong className="text-text">{submittedEmail}</strong>.
            </p>
            <div className="p-3 bg-surface-2/60 border border-border/80 rounded-lg text-left text-xs text-text-muted space-y-1.5">
              <p className="font-semibold text-text">What to do next:</p>
              <ol className="list-decimal list-inside space-y-1">
                <li>Open the verification email sent to your inbox.</li>
                <li>Click the verification link to activate your account.</li>
                <li>Once verified, sign in with your email and password.</li>
              </ol>
            </div>
            <p className="text-xs text-amber-400 font-medium">
              Note: You cannot sign in until your email address is verified.
            </p>
            {isLocalhost && (
              <div className="p-3 bg-primary/5 border border-primary/20 rounded-lg text-left text-xs text-text-muted">
                <span className="font-semibold text-primary block mb-1">
                  Local Development Tip:
                </span>
                Transactional emails are output to the backend console. Run{" "}
                <code className="bg-surface px-1.5 py-0.5 rounded text-text font-mono">
                  docker compose logs backend | grep -A 5
                  &quot;verify-email&quot;
                </code>{" "}
                to copy your activation link.
              </div>
            )}
          </div>

          <div className="pt-2">
            <Link to="/login">
              <Button
                variant="secondary"
                size="lg"
                className="w-full min-h-[44px]"
              >
                Proceed to Sign In
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg flex flex-col justify-center items-center p-4 sm:p-6 py-10">
      <div className="max-w-xl w-full space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 mb-1">
            <span className="font-bold text-lg text-text">FitGate</span>
            {tenant && (
              <Badge variant="primary" className="uppercase font-mono text-xs">
                {tenant}
              </Badge>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-text tracking-tight">
            Create Member Account
          </h1>
          <p className="text-sm text-text-muted max-w-sm mx-auto">
            Join {tenant ? `${tenant}'s gym` : "your gym portal"} to track
            workouts, scan in via QR, and manage memberships.
          </p>
        </div>

        {/* Registration Card */}
        <Card className="bg-surface border-border p-6 sm:p-8 shadow-card">
          {error && (
            <Alert variant="danger" className="mb-6">
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <FormField
              label="Full Name"
              htmlFor="full_name"
              required
              error={fieldErrors.full_name}
            >
              <Input
                id="full_name"
                name="full_name"
                type="text"
                required
                maxLength={100}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Abebe Bikila"
                error={fieldErrors.full_name}
                className="min-h-[44px]"
              />
            </FormField>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField
                label="Email Address"
                htmlFor="email"
                required
                error={fieldErrors.email}
              >
                <Input
                  id="email"
                  name="email"
                  type="email"
                  required
                  maxLength={254}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  error={fieldErrors.email}
                  className="min-h-[44px]"
                />
              </FormField>

              <FormField
                label="Phone Number"
                htmlFor="phone"
                required
                error={fieldErrors.phone}
              >
                <Input
                  id="phone"
                  name="phone"
                  type="tel"
                  inputMode="tel"
                  required
                  maxLength={20}
                  value={phone}
                  onChange={(e) => setPhone(filterPhoneInput(e.target.value))}
                  placeholder="+251911223344"
                  error={fieldErrors.phone}
                  className="min-h-[44px]"
                />
              </FormField>
            </div>

            <div className="space-y-4">
              <FormField
                label="Password"
                htmlFor="password"
                required
                error={fieldErrors.password}
              >
                <Input
                  id="password"
                  name="password"
                  type="password"
                  required
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 10 characters"
                  error={fieldErrors.password}
                  className="min-h-[44px]"
                />
              </FormField>

              <PasswordChecklist password={password} />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField
                label="Date of Birth"
                htmlFor="date_of_birth"
                error={fieldErrors.date_of_birth}
              >
                <Input
                  id="date_of_birth"
                  name="date_of_birth"
                  type="date"
                  value={dateOfBirth}
                  onChange={(e) => setDateOfBirth(e.target.value)}
                  error={fieldErrors.date_of_birth}
                  className="min-h-[44px]"
                />
              </FormField>

              <FormField label="Gender" htmlFor="gender">
                <select
                  id="gender"
                  name="gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="w-full bg-surface-2 border border-border text-text rounded-input px-3 py-2 text-sm focus:outline-none focus:border-primary min-h-[44px]"
                  required
                >
                  <option value="">Select Gender *</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </FormField>
            </div>

            <FormField
              label="Emergency Contact Phone"
              htmlFor="emergency_contact"
              error={fieldErrors.emergency_contact}
              helpText="Digits, spaces, hyphens, optional + prefix."
            >
              <Input
                id="emergency_contact"
                name="emergency_contact"
                type="tel"
                inputMode="tel"
                maxLength={20}
                value={emergencyContact}
                onChange={(e) =>
                  setEmergencyContact(filterPhoneInput(e.target.value))
                }
                placeholder="e.g. +251911223344"
                error={fieldErrors.emergency_contact}
                className="min-h-[44px]"
              />
            </FormField>

            {/* Mandatory Health Waiver Checkbox */}
            <div className="bg-surface-2/40 border border-border p-4 rounded-lg space-y-2">
              <label className="flex items-start gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  id="waiver_accepted"
                  name="waiver_accepted"
                  required
                  checked={waiverAccepted}
                  onChange={(e) => setWaiverAccepted(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-xs sm:text-sm text-text leading-relaxed">
                  <strong className="text-text font-semibold">
                    Health & Safety Waiver:{" "}
                  </strong>
                  I confirm that I am in good physical condition and voluntarily
                  agree to participate in gym and fitness activities. I
                  acknowledge and accept the facility rules and safety
                  requirements. <span className="text-danger font-bold">*</span>
                </span>
              </label>
              {fieldErrors.waiver_accepted && (
                <p className="text-xs text-danger mt-1" role="alert">
                  {fieldErrors.waiver_accepted}
                </p>
              )}
            </div>

            <Button
              type="submit"
              size="lg"
              disabled={loading || !waiverAccepted}
              className="w-full mt-4 min-h-[44px]"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <Spinner size="sm" /> Creating Account...
                </span>
              ) : (
                "Complete Registration"
              )}
            </Button>
          </form>

          <div className="text-center mt-6 pt-4 border-t border-border">
            <p className="text-xs text-text-muted">
              Already have an account?{" "}
              <Link
                to="/login"
                className="text-primary font-medium hover:underline"
              >
                Sign in here
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
};
