import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  CheckCircle,
  Mail,
  MapPin,
  MessageSquare,
  Phone,
  Send,
} from "lucide-react";
import { submitPublicDemoRequest } from "../api/demoRequests";
import { ApiError } from "../api/client";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { getTenantFromHostname } from "../utils/tenant";

import {
  focusFirstInvalidField,
  normalizePhone,
  validateEmail,
  validateName,
  validatePhone,
  validateTextLength,
} from "../utils/validators";

interface DemoFieldErrors {
  gymName?: string;
  contactName?: string;
  phone?: string;
  email?: string;
  message?: string;
  city?: string;
}

export const RequestDemoScreen: React.FC = () => {
  const tenant = getTenantFromHostname();
  const [gymName, setGymName] = useState("");
  const [contactName, setContactName] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [honeypot, setHoneypot] = useState("");

  const [fieldErrors, setFieldErrors] = useState<DemoFieldErrors>({});

  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!submitted) return;
    const timer = setTimeout(() => {
      navigate("/");
    }, 5000);
    return () => clearTimeout(timer);
  }, [submitted, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const errors: {
      gymName?: string;
      contactName?: string;
      phone?: string;
      email?: string;
      message?: string;
      city?: string;
    } = {};

    if (!gymName.trim() || !contactName.trim() || !phone.trim()) {
      setError("Please fill in gym name, your name, and phone number.");
    }

    const gymNameErr = validateName(gymName, "Gym name", true);
    if (gymNameErr) errors.gymName = gymNameErr;

    const contactNameErr = validateName(contactName, "Contact name", true);
    if (contactNameErr) errors.contactName = contactNameErr;

    const phoneErr = validatePhone(phone, true);
    if (phoneErr) errors.phone = phoneErr;

    if (email.trim()) {
      const emailErr = validateEmail(email, false);
      if (emailErr) errors.email = emailErr;
    }

    if (message.trim()) {
      const msgErr = validateTextLength(message, 0, 1000, "Message");
      if (msgErr) errors.message = msgErr;
    }

    if (city.trim() && city.trim().length > 100) {
      errors.city = "City cannot exceed 100 characters.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(
        [
          errors.gymName ? "demo-gym-name" : "",
          errors.contactName ? "demo-contact-name" : "",
          errors.phone ? "demo-phone" : "",
          errors.city ? "demo-city" : "",
          errors.email ? "demo-email" : "",
          errors.message ? "demo-message" : "",
        ].filter(Boolean)
      );
      return;
    }

    setFieldErrors({});
    setLoading(true);
    try {
      await submitPublicDemoRequest({
        gym_name: gymName.trim(),
        contact_name: contactName.trim(),
        phone: normalizePhone(phone),
        city: city.trim(),
        email: email.trim().toLowerCase(),
        message: message.trim(),
        website: honeypot.trim(),
      });
      setSubmitted(true);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError(
            "Too many requests. Please wait a few moments or contact our team directly via Telegram or phone."
          );
        } else if (
          err.status === 400 &&
          typeof err.data === "object" &&
          err.data !== null
        ) {
          const data = err.data as Record<string, unknown>;
          if ("detail" in data) {
            setError(String(data.detail));
          } else {
            // Map server field errors to form fields
            const newFieldErrors: DemoFieldErrors = {};
            if (data.gym_name)
              newFieldErrors.gymName = Array.isArray(data.gym_name)
                ? String(data.gym_name[0])
                : String(data.gym_name);
            if (data.contact_name)
              newFieldErrors.contactName = Array.isArray(data.contact_name)
                ? String(data.contact_name[0])
                : String(data.contact_name);
            if (data.phone)
              newFieldErrors.phone = Array.isArray(data.phone)
                ? String(data.phone[0])
                : String(data.phone);
            if (data.email)
              newFieldErrors.email = Array.isArray(data.email)
                ? String(data.email[0])
                : String(data.email);
            if (data.message)
              newFieldErrors.message = Array.isArray(data.message)
                ? String(data.message[0])
                : String(data.message);
            setFieldErrors(newFieldErrors);
            setError("Please correct the errors indicated below.");
          }
        } else {
          setError(err.message || "Failed to submit demo request.");
        }
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Network error. Please check your connection and try again."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg text-text py-12 px-4 sm:px-6 lg:px-8 flex flex-col justify-center items-center">
      <div className="w-full max-w-4xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary/20 text-primary font-bold text-2xl mb-3 border border-primary/30">
            FG
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
            Request a FitGate Demo
          </h1>
          <p className="mt-2 text-base text-text-muted max-w-2xl mx-auto">
            Experience the modern management system built specifically for
            Ethiopian gyms. Automate subscriptions, biometric/QR access, and
            mobile payments.
          </p>
        </div>

        {tenant && (
          <div className="mb-6 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-xs text-amber-300 max-w-xl mx-auto">
            <p className="font-semibold mb-1">
              Note: You are currently on a gym subdomain ({tenant}).
            </p>
            <p>
              Demo requests are managed on the platform apex domain. Please
              submit from{" "}
              <a
                href="http://localhost:5173/request-demo"
                className="underline text-primary font-semibold"
              >
                http://localhost:5173/request-demo
              </a>
              .
            </p>
          </div>
        )}

        {submitted ? (
          <Card className="max-w-xl mx-auto text-center p-8 bg-surface border-border">
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center mb-4">
              <CheckCircle className="w-10 h-10" />
            </div>
            <h2 className="text-2xl font-bold text-text mb-2">
              Demo Request Received!
            </h2>
            <p className="text-text-muted mb-6">
              Thank you for reaching out. A FitGate product specialist will call
              or message you within 24 hours to arrange an interactive
              demonstration.
            </p>
            <div className="flex justify-center">
              <Link to="/">
                <Button variant="primary">Back to home</Button>
              </Link>
            </div>
            <p className="text-xs text-text-muted mt-4">
              Redirecting to home in 5 seconds...
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start">
            {/* Direct Contact Info Sidebar */}
            <div className="md:col-span-1 space-y-6">
              <Card className="p-6 bg-surface border-border space-y-6">
                <div>
                  <h3 className="text-lg font-semibold text-text mb-1">
                    Direct Contact
                  </h3>
                  <p className="text-xs text-text-muted">
                    Need immediate assistance or prefer speaking directly?
                  </p>
                </div>

                <div className="space-y-4 text-sm">
                  <div className="flex items-start gap-3">
                    <Phone className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-text">
                        Phone / WhatsApp
                      </div>
                      <a
                        href="tel:+251911234567"
                        className="text-text-muted hover:text-primary transition-colors"
                      >
                        +251 911 234 567
                      </a>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <MessageSquare className="w-5 h-5 text-sky-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-text">Telegram</div>
                      <a
                        href="https://t.me/fitgate_ethiopia"
                        target="_blank"
                        rel="noreferrer"
                        className="text-text-muted hover:text-sky-400 transition-colors"
                      >
                        @FitGateSupport
                      </a>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <Mail className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-text">Email</div>
                      <a
                        href="mailto:contact@fitgate.tebebtech.com"
                        className="text-text-muted hover:text-indigo-400 transition-colors"
                      >
                        contact@fitgate.tebebtech.com
                      </a>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <MapPin className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium text-text">Office</div>
                      <span className="text-text-muted">
                        Bole, Addis Ababa, Ethiopia
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-border/60">
                  <Link
                    to="/login"
                    className="text-xs text-primary hover:underline font-medium"
                  >
                    ← Already a customer? Sign In
                  </Link>
                </div>
              </Card>
            </div>

            {/* Lead Form */}
            <div className="md:col-span-2">
              <Card className="p-6 bg-surface border-border">
                {error && (
                  <Alert variant="danger" className="mb-6">
                    {error}
                  </Alert>
                )}

                <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                  {/* Invisible Honeypot field for bot detection */}
                  <input
                    type="text"
                    name="website"
                    tabIndex={-1}
                    autoComplete="off"
                    aria-hidden="true"
                    className="hidden"
                    value={honeypot}
                    onChange={(e) => setHoneypot(e.target.value)}
                  />

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <FormField
                      label="Gym Name"
                      htmlFor="demo-gym-name"
                      required
                      error={fieldErrors.gymName}
                    >
                      <Input
                        id="demo-gym-name"
                        type="text"
                        placeholder="e.g. Bole Fitness Hub"
                        value={gymName}
                        onChange={(e) => setGymName(e.target.value)}
                        required
                        maxLength={100}
                        error={fieldErrors.gymName}
                      />
                    </FormField>

                    <FormField
                      label="Contact Person"
                      htmlFor="demo-contact-name"
                      required
                      error={fieldErrors.contactName}
                    >
                      <Input
                        id="demo-contact-name"
                        type="text"
                        placeholder="e.g. Abebe Bikila"
                        value={contactName}
                        onChange={(e) => setContactName(e.target.value)}
                        required
                        maxLength={100}
                        error={fieldErrors.contactName}
                      />
                    </FormField>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <FormField
                      label="Phone Number"
                      htmlFor="demo-phone"
                      required
                      error={fieldErrors.phone}
                    >
                      <Input
                        id="demo-phone"
                        type="tel"
                        inputMode="tel"
                        placeholder="e.g. +251 911 234 567"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        required
                        maxLength={20}
                        error={fieldErrors.phone}
                      />
                    </FormField>

                    <FormField
                      label="City / Location"
                      htmlFor="demo-city"
                      error={fieldErrors.city}
                    >
                      <Input
                        id="demo-city"
                        type="text"
                        placeholder="e.g. Addis Ababa, Hawassa"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        maxLength={100}
                        error={fieldErrors.city}
                      />
                    </FormField>
                  </div>

                  <FormField
                    label="Email Address (Optional)"
                    htmlFor="demo-email"
                    error={fieldErrors.email}
                  >
                    <Input
                      id="demo-email"
                      type="email"
                      placeholder="e.g. owner@gym.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      maxLength={254}
                      error={fieldErrors.email}
                    />
                  </FormField>

                  <FormField
                    label="Message or Questions (Optional)"
                    htmlFor="demo-message"
                    error={fieldErrors.message}
                  >
                    <textarea
                      id="demo-message"
                      rows={3}
                      className="w-full px-3.5 py-2.5 bg-surface text-text placeholder-text-muted border rounded-input transition-colors text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50 border-border hover:border-border/80"
                      placeholder="Tell us about your facility (member count, current challenges, desired features)..."
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      maxLength={1000}
                    />
                  </FormField>

                  <Button
                    type="submit"
                    variant="primary"
                    className="w-full min-h-[46px] text-base"
                    disabled={loading}
                  >
                    {loading ? (
                      "Submitting..."
                    ) : (
                      <>
                        <Send className="w-4 h-4 mr-2" />
                        Request Live Demo
                      </>
                    )}
                  </Button>
                </form>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
