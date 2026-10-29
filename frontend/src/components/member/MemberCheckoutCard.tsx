import React, { useEffect, useState } from "react";
import { getMembershipPlans, type MembershipPlan } from "../../api/plans";
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

interface MemberCheckoutCardProps {
  memberStatus: string;
  onPaymentInitiated?: () => void;
}

export const MemberCheckoutCard: React.FC<MemberCheckoutCardProps> = ({
  memberStatus,
}) => {
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [onlinePaymentVerified, setOnlinePaymentVerified] = useState(true);
  const [isSimulated, setIsSimulated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setErrorMsg(null);
      try {
        const data = await getMembershipPlans();
        const activePlans = (data || []).filter((p) => p.is_active);
        setPlans(activePlans);
        if (activePlans.length > 0) {
          setSelectedPlanId(activePlans[0].id);
        }

        try {
          const tenant = getTenantFromHostname();
          const statusData = await Promise.resolve(
            getGymPaymentPublicStatus?.(tenant || undefined)
          );
          if (
            statusData &&
            typeof statusData.online_payment_verified === "boolean"
          ) {
            setOnlinePaymentVerified(statusData.online_payment_verified);
            if (statusData.use_mock) {
              setIsSimulated(true);
            }
          } else {
            setOnlinePaymentVerified(true);
          }
        } catch {
          setOnlinePaymentVerified(false);
        }
      } catch (err: unknown) {
        setErrorMsg(
          err instanceof Error
            ? err.message
            : "Failed to load membership plans."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleOnlineCheckout = async (planIdToCheckout?: string) => {
    const targetPlanId = planIdToCheckout || selectedPlanId;
    if (!targetPlanId) return;
    setCheckingOut(true);
    setErrorMsg(null);

    try {
      const res = await initiateChapaCheckout(targetPlanId);
      if (res.checkout_url) {
        window.location.assign(res.checkout_url);
      }
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Online checkout is unavailable. Please visit the front desk to pay with cash or bank transfer."
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
          <span className="text-xs text-text-muted">
            Loading available plans...
          </span>
        </div>
      </Card>
    );
  }

  if (plans.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-xs text-text-muted">
          No membership plans are currently available for purchase. Please
          contact reception.
        </p>
      </Card>
    );
  }

  const isRenewal = memberStatus === "active";
  const cardTitle = isRenewal ? "Renew" : "Choose a plan";

  return (
    <Card className="p-6 space-y-5">
      <div className="border-b border-border pb-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-text">{cardTitle}</h3>
          <Badge variant={isRenewal ? "success" : "warning"}>
            Status: {memberStatus}
          </Badge>
        </div>
        <p className="text-xs text-text-muted mt-1">
          {onlinePaymentVerified
            ? "Pay online via Chapa (Telebirr, CBE, Cards) or visit reception to pay at front desk."
            : "Please pay at front desk (cash or bank transfer)."}
        </p>
        {isSimulated && (
          <p className="text-[11px] text-warning mt-1 font-medium">
            Test environment: payments are simulated
          </p>
        )}
      </div>

      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

      {/* Notice if online payment is not verified */}
      {!onlinePaymentVerified && (
        <div className="p-3 bg-surface-2 rounded-lg border border-border text-sm text-text font-medium">
          Please pay at front desk (cash or bank transfer)
        </div>
      )}

      {/* Plan selection grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {plans.map((plan) => {
          const isSelected = plan.id === selectedPlanId;
          return (
            <div
              key={plan.id}
              onClick={() => setSelectedPlanId(plan.id)}
              className={`cursor-pointer rounded-lg border p-4 transition-all flex flex-col justify-between ${
                isSelected
                  ? "border-primary bg-primary/10 shadow-sm ring-1 ring-primary"
                  : "border-border bg-surface-2 hover:border-border/80"
              }`}
            >
              <div>
                <div className="flex justify-between items-start mb-2">
                  <span className="font-semibold text-sm text-text">
                    {plan.name}
                  </span>
                  {isSelected && (
                    <span className="text-xs text-primary font-bold">
                      Selected
                    </span>
                  )}
                </div>
                <p className="text-lg font-bold text-text mb-1">
                  {plan.price_etb}{" "}
                  <span className="text-xs font-normal text-text-muted">
                    ETB
                  </span>
                </p>
                <p className="text-xs text-text-muted">
                  {plan.duration_value} {plan.duration_unit}
                  {plan.trainer_inclusive && " · Includes Trainer"}
                </p>
              </div>

              {onlinePaymentVerified && (
                <div className="mt-4 pt-2 border-t border-border/50">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedPlanId(plan.id);
                      handleOnlineCheckout(plan.id);
                    }}
                    disabled={checkingOut}
                    className="w-full text-xs min-h-[36px]"
                  >
                    {checkingOut && selectedPlanId === plan.id
                      ? "Redirecting..."
                      : "Pay online"}
                  </Button>
                </div>
              )}
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
            {onlinePaymentVerified ? (
              <Button
                variant="primary"
                onClick={() => handleOnlineCheckout(selectedPlan.id)}
                disabled={checkingOut}
                className="w-full sm:w-auto"
              >
                {checkingOut
                  ? "Redirecting to Chapa..."
                  : "Pay Online with Chapa"}
              </Button>
            ) : (
              <span className="text-xs font-semibold text-text-muted">
                Please pay at front desk (cash or bank transfer)
              </span>
            )}
          </div>
        </div>
      )}

      <div className="pt-2 text-[11px] text-text-muted flex items-center justify-between border-t border-border/50">
        <span>
          Payment options: Chapa (Telebirr, CBEBirr, Credit/Debit cards) or
          front desk cash.
        </span>
        <span>Secure 256-bit payment transaction</span>
      </div>
    </Card>
  );
};
