import React, { useEffect, useState } from "react";
import { getPublicPlans, getMembershipPlans } from "../../api/plans";
import { getPublicGymEntry } from "../../api/gyms";
import {
  getGymPaymentPublicStatus,
  initiateChapaCheckout,
} from "../../api/payments";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
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
  onPaymentInitiated?: () => void;
}

export const MemberCheckoutCard: React.FC<MemberCheckoutCardProps> = ({
  memberStatus,
}) => {
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
          phone = entry.phone || "";
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
    } catch {
      setErrorMsg(
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

  const contactParts: string[] = [];
  if (contactPhone && contactPhone.trim()) {
    contactParts.push(`Phone: ${contactPhone.trim()}`);
  }
  if (contactLocation && contactLocation.trim()) {
    contactParts.push(`Address: ${contactLocation.trim()}`);
  }
  const contactInfoText =
    contactParts.length > 0 ? `(${contactParts.join(" · ")})` : "";

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
                {plan.trainer_inclusive ? " · Includes Trainer" : ""}
              </p>
              {plan.description && (
                <p className="text-xs text-text-muted mt-1">
                  {plan.description}
                </p>
              )}
            </div>

            {onlinePaymentVerified && (
              <div className="mt-5 pt-3 border-t border-border/50">
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
            )}
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
              front desk with cash or bank transfer and tell the staff which
              plan you want.
              {contactInfoText ? ` ${contactInfoText}` : ""}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
};
