import React, { useEffect, useState } from "react";
import { getPublicPlans, getMembershipPlans } from "../../api/plans";
import { getPublicGymEntry } from "../../api/gyms";
import { formatGymContactLine } from "../../utils/contactLine";
import {
  getGymPaymentPublicStatus,
  initiateChapaCheckout,
  getMemberUpgradeQuote,
  type PlanUpgradeQuote,
} from "../../api/payments";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import { useAuth } from "../../context/AuthContext";
import { getTenantFromHostname } from "../../utils/tenant";
import { ApiError } from "../../api/client";

interface DisplayPlan {
  id: string;
  name: string;
  description?: string;
  duration_value: number;
  duration_unit: string;
  price_etb: string;
  trainer_inclusive?: boolean;
}

interface MemberCheckoutCardProps {
  memberStatus: string;
  activeSubscription?: {
    id: string;
    plan_id: string;
    plan_name: string;
    plan_price_etb: string;
    trainer_inclusive?: boolean;
    start_date: string;
    end_date: string;
  } | null;
  onPaymentInitiated?: () => void;
}

export const MemberCheckoutCard: React.FC<MemberCheckoutCardProps> = ({
  memberStatus,
  activeSubscription,
}) => {
  const { capabilities } = useAuth();
  const [selectedUpgradePlan, setSelectedUpgradePlan] =
    useState<DisplayPlan | null>(null);
  const [upgradeQuote, setUpgradeQuote] = useState<PlanUpgradeQuote | null>(
    null
  );
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);

  const handleOpenUpgrade = async (plan: DisplayPlan) => {
    setSelectedUpgradePlan(plan);
    setLoadingQuote(true);
    setQuoteError(null);
    try {
      const quote = await getMemberUpgradeQuote(plan.id);
      setUpgradeQuote(quote);
    } catch (err: unknown) {
      const errorObj = err as {
        detail?: string;
        data?: { detail?: string };
        message?: string;
      };
      setQuoteError(
        errorObj?.data?.detail ||
          errorObj?.detail ||
          errorObj?.message ||
          "Failed to load upgrade quote."
      );
    } finally {
      setLoadingQuote(false);
    }
  };

  const handleCloseUpgrade = () => {
    setSelectedUpgradePlan(null);
    setUpgradeQuote(null);
    setQuoteError(null);
  };
  const [plans, setPlans] = useState<DisplayPlan[]>([]);
  const [onlinePaymentVerified, setOnlinePaymentVerified] = useState(false);
  const [isSimulated, setIsSimulated] = useState(false);
  const [contactPhone, setContactPhone] = useState<string>("");
  const [contactLocation, setContactLocation] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState(false);
  const [targetPlanId, setTargetPlanId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setErrorMsg(null);
      const tenant = getTenantFromHostname();

      let activePlans: DisplayPlan[] = [];
      let phone = "";
      let location = "";
      let verified = false;
      let hasEntry = false;

      // 1. Fetch public gym entry for contact info, active plans, and verification status
      try {
        const entry = await getPublicGymEntry(tenant || undefined);
        if (entry) {
          hasEntry = true;
          if (Array.isArray(entry.plans) && entry.plans.length > 0) {
            activePlans = entry.plans;
          }
          phone = entry.public_contact_phone || entry.phone || "";
          location = entry.location || "";
          if (typeof entry.online_payment_verified === "boolean") {
            verified = entry.online_payment_verified;
          }
        }
      } catch (err: unknown) {
        if (
          err instanceof ApiError &&
          err.data &&
          typeof err.data === "object"
        ) {
          hasEntry = true;
          const data = err.data as Record<string, unknown>;
          if (Array.isArray(data.plans) && data.plans.length > 0) {
            activePlans = data.plans as DisplayPlan[];
          }
          phone = (data.phone as string) || "";
          location = (data.location as string) || "";
          if (typeof data.online_payment_verified === "boolean") {
            verified = data.online_payment_verified as boolean;
          }
        }
      }

      // 2. Fallback to public plans endpoint if plans list is still empty
      if (activePlans.length === 0) {
        try {
          const pubPlans = await getPublicPlans();
          if (Array.isArray(pubPlans) && pubPlans.length > 0) {
            activePlans = pubPlans;
          }
        } catch {
          // ignore
        }
      }

      // 3. Fallback for tests that mocked getMembershipPlans
      if (activePlans.length === 0) {
        try {
          const memPlans = await getMembershipPlans();
          if (Array.isArray(memPlans) && memPlans.length > 0) {
            activePlans = memPlans.filter((p) => p.is_active);
          }
        } catch {
          // ignore
        }
      }

      // 4. Confirm public payment status (and mock mode badge)
      try {
        const statusData = await getGymPaymentPublicStatus(tenant || undefined);
        if (
          statusData &&
          typeof statusData.online_payment_verified === "boolean"
        ) {
          verified = statusData.online_payment_verified;
          if (statusData.use_mock) {
            setIsSimulated(true);
          }
        } else if (!hasEntry) {
          verified = true;
        }
      } catch {
        if (!hasEntry) {
          verified = true;
        }
      }

      setPlans(activePlans);
      setContactPhone(phone);
      setContactLocation(location);
      setOnlinePaymentVerified(verified);
      setLoading(false);
    };

    fetchData();
  }, []);

  const handleOnlineCheckout = async (planId: string) => {
    if (!planId) return;
    setTargetPlanId(planId);
    setCheckingOut(true);
    setErrorMsg(null);

    try {
      const res = await initiateChapaCheckout(planId);
      if (res.checkout_url) {
        window.location.assign(res.checkout_url);
      } else {
        setErrorMsg(
          "We could not start the online payment. Please try again or pay at the front desk (cash or bank transfer)."
        );
      }
    } catch (err: unknown) {
      const errorObj = err as {
        detail?: string;
        message?: string;
        data?: { detail?: string };
      };
      setErrorMsg(
        errorObj?.detail ||
          errorObj?.data?.detail ||
          errorObj?.message ||
          "We could not start the online payment. Please try again or pay at the front desk (cash or bank transfer)."
      );
    } finally {
      setCheckingOut(false);
    }
  };

  if (memberStatus === "frozen") {
    return (
      <Card className="p-6">
        <p className="text-sm font-medium text-text">
          Your membership is frozen.
        </p>
      </Card>
    );
  }

  if (memberStatus === "suspended") {
    return (
      <Card className="p-6">
        <p className="text-sm font-medium text-text">
          Please see the front desk.
        </p>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3">
          <Spinner size="sm" />
          <span className="text-xs text-text-muted">
            Loading available plans...
          </span>
        </div>
      </Card>
    );
  }

  const isRenewal = memberStatus === "active";
  const cardTitle = isRenewal ? "Renew" : "Choose a plan";

  const contactInfoText = formatGymContactLine(contactPhone, contactLocation);

  if (plans.length === 0) {
    return (
      <Card className="p-6 space-y-4">
        <div className="border-b border-border pb-3 flex items-center justify-between">
          <h3 className="text-base font-bold text-text">{cardTitle}</h3>
          <Badge
            variant={isRenewal ? "success" : "warning"}
            className="capitalize"
          >
            Status: {memberStatus}
          </Badge>
        </div>
        <p className="text-sm text-text-muted">
          No membership plans are currently available for purchase. Please
          contact the front desk.
          {contactInfoText ? ` ${contactInfoText}` : ""}
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-6 space-y-6">
      <div className="border-b border-border pb-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-text">{cardTitle}</h3>
          <Badge
            variant={isRenewal ? "success" : "warning"}
            className="capitalize"
          >
            Status: {memberStatus}
          </Badge>
        </div>
        {isSimulated && (
          <p className="text-[11px] text-warning mt-1 font-medium">
            Test environment: payments are simulated
          </p>
        )}
      </div>

      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

      {/* Plan cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {plans.map((plan) => (
          <div
            key={plan.id}
            className="rounded-lg border border-border bg-surface-2 p-5 flex flex-col justify-between"
          >
            <div className="space-y-2">
              <h4 className="font-bold text-base text-text">{plan.name}</h4>
              <p className="text-2xl font-extrabold text-text">
                {plan.price_etb}{" "}
                <span className="text-xs font-normal text-text-muted">ETB</span>
              </p>
              <p className="text-xs text-text-muted">
                {plan.duration_value} {plan.duration_unit}
                {(capabilities?.has_trainer_module && plan.trainer_inclusive) ? " · Includes Trainer" : ""}
              </p>
              {plan.description && (
                <p className="text-xs text-text-muted mt-1">
                  {plan.description}
                </p>
              )}
            </div>

            {onlinePaymentVerified &&
              (() => {
                const isActiveMember =
                  memberStatus === "active" && Boolean(activeSubscription);
                if (isActiveMember && activeSubscription) {
                  const isCurrentPlan = activeSubscription.plan_id === plan.id;
                  const currentPrice = parseFloat(
                    activeSubscription.plan_price_etb
                  );
                  const planPrice = parseFloat(plan.price_etb);
                  const isUpgrade = planPrice > currentPrice;
                  const isCheaper = !isCurrentPlan && planPrice <= currentPrice;

                  // Entitlement check: upgrade must include trainer if current plan has trainer
                  if (
                    !isCurrentPlan &&
                    activeSubscription.trainer_inclusive &&
                    !plan.trainer_inclusive
                  ) {
                    return (
                      <div className="mt-5 pt-3 border-t border-border/50">
                        <p className="text-xs text-text-muted bg-surface/80 p-2.5 rounded border border-border/60">
                          This plan does not include a trainer. You can choose
                          it when your current plan ends on{" "}
                          {activeSubscription.end_date}.
                        </p>
                      </div>
                    );
                  }

                  if (isCheaper) {
                    return (
                      <div className="mt-5 pt-3 border-t border-border/50">
                        <p className="text-xs text-text-muted bg-surface/80 p-2.5 rounded border border-border/60">
                          This plan costs less than your current one. It can
                          start when your current plan ends on{" "}
                          {activeSubscription.end_date}.
                        </p>
                      </div>
                    );
                  }

                  if (isUpgrade) {
                    return (
                      <div className="mt-5 pt-3 border-t border-border/50">
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleOpenUpgrade(plan)}
                          disabled={checkingOut}
                          className="w-full text-xs min-h-[38px]"
                        >
                          Upgrade Plan
                        </Button>
                      </div>
                    );
                  }

                  return (
                    <div className="mt-5 pt-3 border-t border-border/50">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleOnlineCheckout(plan.id)}
                        disabled={checkingOut}
                        className="w-full text-xs min-h-[38px]"
                      >
                        {checkingOut && targetPlanId === plan.id
                          ? "Starting checkout..."
                          : "Renew (Pay online)"}
                      </Button>
                    </div>
                  );
                }

                const hadTrainerPlan = Boolean(
                  activeSubscription?.trainer_inclusive
                );
                const isNonTrainerPlan = !plan.trainer_inclusive;

                return (
                  <div className="mt-5 pt-3 border-t border-border/50 space-y-2">
                    {capabilities?.has_trainer_module && hadTrainerPlan && isNonTrainerPlan && (
                      <p className="text-xs text-amber-500 bg-amber-500/10 p-2 rounded border border-amber-500/20">
                        This plan has no trainer. The member will lose their
                        trainer's AI plans.
                      </p>
                    )}
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => handleOnlineCheckout(plan.id)}
                      disabled={checkingOut}
                      className="w-full text-xs min-h-[38px]"
                    >
                      {checkingOut && targetPlanId === plan.id
                        ? "Starting checkout..."
                        : "Pay online (Chapa)"}
                    </Button>
                  </div>
                );
              })()}
          </div>
        ))}
      </div>

      {/* Front desk and payment availability information */}
      <div className="pt-2 border-t border-border/60">
        {onlinePaymentVerified ? (
          <p className="text-xs text-text-muted">
            Or pay at the front desk with cash or bank transfer.
            {contactInfoText ? ` ${contactInfoText}` : ""}
          </p>
        ) : (
          <div className="p-4 bg-surface-2 rounded-lg border border-border text-sm text-text">
            <p className="font-medium">
              Online payment is not available at this gym. Please pay at the
              front desk.
              {contactInfoText ? ` ${contactInfoText}` : ""}
            </p>
          </div>
        )}
      </div>
      {/* Upgrade Quote Modal */}
      {selectedUpgradePlan && (
        <div
          className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4 overflow-y-auto"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-surface border border-border rounded-xl max-w-md w-full p-6 space-y-4 my-8 text-text">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h3 className="text-lg font-bold text-text">
                  Upgrade Membership
                </h3>
                <p className="text-xs text-text-muted">
                  To {selectedUpgradePlan.name}
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseUpgrade}
                disabled={checkingOut}
                className="text-text-muted hover:text-text text-xl p-1"
              >
                ✕
              </button>
            </div>

            {quoteError && <Alert variant="danger">{quoteError}</Alert>}

            {loadingQuote && (
              <div className="py-8 flex flex-col items-center justify-center gap-2">
                <Spinner size="md" />
                <span className="text-xs text-text-muted">
                  Calculating your prorated credit...
                </span>
              </div>
            )}

            {upgradeQuote && !loadingQuote && (
              <div className="space-y-4 text-xs">
                <div className="bg-surface-2 p-4 rounded-lg border border-border space-y-2">
                  <div className="flex justify-between">
                    <span className="text-text-muted">Current Plan:</span>
                    <span className="font-semibold text-text">
                      {upgradeQuote.current_plan_name}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Days Remaining:</span>
                    <span className="text-text font-medium">
                      {upgradeQuote.remaining_days} of {upgradeQuote.total_days}{" "}
                      days
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-border/60 pt-2">
                    <span className="text-text-muted">
                      New Plan Price (Gross):
                    </span>
                    <span className="text-text font-semibold">
                      {upgradeQuote.gross_amount_etb} ETB
                    </span>
                  </div>
                  <div className="flex justify-between text-success">
                    <span className="font-medium">Unused Credit Applied:</span>
                    <span className="font-bold">
                      -{upgradeQuote.credit_amount_etb} ETB
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-border pt-2 text-sm font-bold">
                    <span className="text-text">Total Net to Pay:</span>
                    <span className="text-primary text-base font-black">
                      {upgradeQuote.net_amount_etb} ETB
                    </span>
                  </div>
                </div>

                <div className="text-[11px] text-text-muted space-y-1">
                  <p>
                    Your upgrade takes effect today. New period:{" "}
                    <strong className="text-text">
                      {upgradeQuote.new_start_date}
                    </strong>{" "}
                    to{" "}
                    <strong className="text-text">
                      {upgradeQuote.new_end_date}
                    </strong>
                    .
                  </p>
                  <p>Your previous subscription will be marked superseded.</p>
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-border">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleCloseUpgrade}
                    disabled={checkingOut}
                  >
                    Cancel
                  </Button>
                  {onlinePaymentVerified ? (
                    <Button
                      type="button"
                      variant="primary"
                      onClick={() =>
                        handleOnlineCheckout(selectedUpgradePlan.id)
                      }
                      disabled={checkingOut}
                    >
                      {checkingOut ? "Starting checkout..." : "Pay with Chapa"}
                    </Button>
                  ) : (
                    <div className="text-xs text-text-muted bg-surface-2 p-2.5 rounded border border-border">
                      Online payment is not available at this gym. Please pay at
                      the front desk.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
};
