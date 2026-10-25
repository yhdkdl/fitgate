import React, { useEffect, useState } from "react";
import { getMembershipPlans, type MembershipPlan } from "../../api/plans";
import { initiateChapaCheckout } from "../../api/payments";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";

interface MemberCheckoutCardProps {
  memberStatus: string;
  onPaymentInitiated?: () => void;
}

export const MemberCheckoutCard: React.FC<MemberCheckoutCardProps> = ({
  memberStatus,
}) => {
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const fetchPlans = async () => {
      setLoading(true);
      setErrorMsg(null);
      try {
        const data = await getMembershipPlans();
        const activePlans = data.filter((p) => p.is_active);
        setPlans(activePlans);
        if (activePlans.length > 0) {
          setSelectedPlanId(activePlans[0].id);
        }
      } catch (err: unknown) {
        setErrorMsg(
          err instanceof Error ? err.message : "Failed to load membership plans."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchPlans();
  }, []);

  const handleOnlineCheckout = async () => {
    if (!selectedPlanId) return;
    setCheckingOut(true);
    setErrorMsg(null);

    try {
      const res = await initiateChapaCheckout(selectedPlanId);
      if (res.checkout_url) {
        window.location.assign(res.checkout_url);
      }
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Online checkout is unavailable. Please visit the front desk to pay with cash."
      );
    } finally {
      setCheckingOut(false);
    }
  };

  const selectedPlan = plans.find((p) => p.id === selectedPlanId);

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3">
          <Spinner size="sm" />
          <span className="text-xs text-text-muted">Loading available plans...</span>
        </div>
      </Card>
    );
  }

  if (plans.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-xs text-text-muted">
          No membership plans are currently available for purchase. Please contact reception.
        </p>
      </Card>
    );
  }

  const isRenewal = memberStatus === "expired";
  const isPending = memberStatus === "pending";

  return (
    <Card className="p-6 space-y-5">
      <div className="border-b border-border pb-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-text">
            {isPending ? "Choose a Plan to Activate Pass" : isRenewal ? "Renew Your Membership" : "Membership Plan"}
          </h3>
          <Badge variant={isPending || isRenewal ? "warning" : "success"}>
            Status: {memberStatus}
          </Badge>
        </div>
        <p className="text-xs text-text-muted mt-1">
          Pay online via Chapa (Telebirr, CBE, Cards) or visit reception to pay cash.
        </p>
      </div>

      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

      {/* Plan selection grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {plans.map((plan) => {
          const isSelected = plan.id === selectedPlanId;
          return (
            <div
              key={plan.id}
              onClick={() => setSelectedPlanId(plan.id)}
              className={`cursor-pointer rounded-lg border p-4 transition-all ${
                isSelected
                  ? "border-primary bg-primary/10 shadow-sm ring-1 ring-primary"
                  : "border-border bg-surface-2 hover:border-border/80"
              }`}
            >
              <div className="flex justify-between items-start mb-2">
                <span className="font-semibold text-sm text-text">{plan.name}</span>
                {isSelected && (
                  <span className="text-xs text-primary font-bold">Selected</span>
                )}
              </div>
              <p className="text-lg font-bold text-text mb-1">
                {plan.price_etb} <span className="text-xs font-normal text-text-muted">ETB</span>
              </p>
              <p className="text-xs text-text-muted">
                {plan.duration_value} {plan.duration_unit}
                {plan.includes_trainer && " · Includes Trainer"}
              </p>
            </div>
          );
        })}
      </div>

      {selectedPlan && (
        <div className="bg-surface-2 p-4 rounded-lg border border-border/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-text">
              Selected: {selectedPlan.name} ({selectedPlan.price_etb} ETB)
            </p>
            <p className="text-xs text-text-muted">
              Immediate pass activation upon verified payment confirmation.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
            <Button
              variant="primary"
              onClick={handleOnlineCheckout}
              disabled={checkingOut}
              className="w-full sm:w-auto"
            >
              {checkingOut ? "Redirecting to Chapa..." : "Pay Online with Chapa"}
            </Button>
          </div>
        </div>
      )}

      <div className="pt-2 text-[11px] text-text-muted flex items-center justify-between border-t border-border/50">
        <span>Payment options: Chapa (Telebirr, CBEBirr, Credit/Debit cards) or front desk cash.</span>
        <span>Secure 256-bit payment transaction</span>
      </div>
    </Card>
  );
};
