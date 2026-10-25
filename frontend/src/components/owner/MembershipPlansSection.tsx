import React, { useEffect, useState } from "react";
import {
  createMembershipPlan,
  deactivateMembershipPlan,
  getMembershipPlans,
  updateMembershipPlan,
  type CreatePlanInput,
  type MembershipPlan,
  type UpdatePlanInput,
} from "../../api/plans";
import { useAuth } from "../../context/AuthContext";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";

interface MembershipPlansSectionProps {
  onPlansUpdated?: () => void;
}

export const MembershipPlansSection: React.FC<MembershipPlansSectionProps> = ({
  onPlansUpdated,
}) => {
  const { user } = useAuth();
  const isAuthorized = user?.role === "owner" || user?.role === "manager";

  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filter
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<MembershipPlan | null>(null);
  const [modalSubmitting, setModalSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalWarning, setModalWarning] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState<{
    name: string;
    description: string;
    duration_value: string;
    duration_unit: "days" | "months";
    price_etb: string;
    trainer_inclusive: boolean;
  }>({
    name: "",
    description: "",
    duration_value: "1",
    duration_unit: "months",
    price_etb: "",
    trainer_inclusive: false,
  });

  // Deactivate confirmation
  const [deactivatingPlan, setDeactivatingPlan] = useState<MembershipPlan | null>(null);
  const [deactivatingSubmitting, setDeactivatingSubmitting] = useState(false);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await getMembershipPlans();
      setPlans(data);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setErrorMsg(e.message || "Failed to load membership plans.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthorized) {
      fetchPlans();
    }
  }, [isAuthorized]);

  const handleOpenCreateModal = () => {
    setEditingPlan(null);
    setFormData({
      name: "",
      description: "",
      duration_value: "1",
      duration_unit: "months",
      price_etb: "",
      trainer_inclusive: false,
    });
    setModalError(null);
    setModalWarning(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (plan: MembershipPlan) => {
    setEditingPlan(plan);
    setFormData({
      name: plan.name,
      description: plan.description || "",
      duration_value: String(plan.duration_value),
      duration_unit: plan.duration_unit,
      price_etb: plan.price_etb,
      trainer_inclusive: plan.trainer_inclusive,
    });
    setModalError(null);
    setModalWarning(null);
    setIsModalOpen(true);
  };

  const handleModalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);
    setModalWarning(null);

    const val = parseInt(formData.duration_value, 10);
    if (isNaN(val) || val <= 0) {
      setModalError("Duration value must be a positive number greater than 0.");
      return;
    }

    const price = parseFloat(formData.price_etb);
    if (isNaN(price) || price < 0) {
      setModalError("Price must be 0 or greater.");
      return;
    }

    try {
      setModalSubmitting(true);
      if (editingPlan) {
        const payload: UpdatePlanInput = {
          name: formData.name.trim(),
          description: formData.description.trim(),
          duration_value: val,
          duration_unit: formData.duration_unit,
          price_etb: formData.price_etb.trim(),
          trainer_inclusive: formData.trainer_inclusive,
        };
        const updated = await updateMembershipPlan(editingPlan.id, payload);
        if (updated.has_no_trainers_warning && updated.warning) {
          setSuccessMsg(`Plan updated with note: ${updated.warning}`);
        } else {
          setSuccessMsg(`Membership plan '${updated.name}' updated successfully.`);
        }
      } else {
        const payload: CreatePlanInput = {
          name: formData.name.trim(),
          description: formData.description.trim(),
          duration_value: val,
          duration_unit: formData.duration_unit,
          price_etb: formData.price_etb.trim(),
          trainer_inclusive: formData.trainer_inclusive,
        };
        const created = await createMembershipPlan(payload);
        if (created.has_no_trainers_warning && created.warning) {
          setSuccessMsg(`Plan created with note: ${created.warning}`);
        } else {
          setSuccessMsg(`Membership plan '${created.name}' created successfully.`);
        }
      }

      setIsModalOpen(false);
      await fetchPlans();
      if (onPlansUpdated) onPlansUpdated();
    } catch (err: unknown) {
      const e = err as { detail?: string; message?: string };
      setModalError(e.detail || e.message || "Failed to save membership plan.");
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleConfirmDeactivate = async () => {
    if (!deactivatingPlan) return;
    try {
      setDeactivatingSubmitting(true);
      await deactivateMembershipPlan(deactivatingPlan.id);
      setSuccessMsg(`Membership plan '${deactivatingPlan.name}' has been deactivated.`);
      setDeactivatingPlan(null);
      await fetchPlans();
      if (onPlansUpdated) onPlansUpdated();
    } catch (err: unknown) {
      const e = err as { detail?: string; message?: string };
      setErrorMsg(e.detail || e.message || "Failed to deactivate plan.");
    } finally {
      setDeactivatingSubmitting(false);
    }
  };

  if (!isAuthorized) {
    return null;
  }

  const filteredPlans = plans.filter((p) => {
    if (statusFilter === "active") return p.is_active;
    if (statusFilter === "inactive") return !p.is_active;
    return true;
  });

  return (
    <Card className="bg-surface border-border p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-xl font-bold text-text">Membership Plans & Pricing</h2>
          <p className="text-sm text-text-muted">
            Configure flexible subscription tiers with daily or monthly durations for your members.
          </p>
        </div>
        <Button
          onClick={handleOpenCreateModal}
          variant="primary"
          className="min-h-[44px] shrink-0"
        >
          + Add New Plan
        </Button>
      </div>

      {errorMsg && (
        <Alert variant="error" onClose={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      )}

      {successMsg && (
        <Alert variant="success" onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase text-text-muted">Status:</span>
        {(["all", "active", "inactive"] as const).map((filter) => (
          <button
            key={filter}
            onClick={() => setStatusFilter(filter)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md capitalize transition-colors min-h-[32px] ${
              statusFilter === filter
                ? "bg-primary text-text font-bold"
                : "bg-surface-2 text-text-muted hover:text-text hover:bg-surface-3"
            }`}
          >
            {filter} ({filter === "all" ? plans.length : plans.filter((p) => filter === "active" ? p.is_active : !p.is_active).length})
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center gap-3">
          <Spinner size="lg" />
          <p className="text-sm text-text-muted">Loading membership plans...</p>
        </div>
      ) : filteredPlans.length === 0 ? (
        <div className="py-12 text-center border border-dashed border-border rounded-xl p-8 space-y-3">
          <p className="text-base font-semibold text-text">No membership plans found</p>
          <p className="text-sm text-text-muted max-w-md mx-auto">
            {statusFilter === "all"
              ? "Your gym has not created any membership plans yet. Add your first plan to start enrolling members."
              : `No ${statusFilter} membership plans match the selected filter.`}
          </p>
          {statusFilter === "all" && (
            <Button onClick={handleOpenCreateModal} variant="secondary" className="mt-2 min-h-[44px]">
              Create First Plan
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredPlans.map((plan) => (
            <div
              key={plan.id}
              className={`border rounded-xl p-5 flex flex-col justify-between transition-all ${
                plan.is_active
                  ? "bg-bg border-border hover:border-primary/40"
                  : "bg-surface-2/30 border-border/50 opacity-75"
              }`}
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-bold text-lg text-text leading-tight">{plan.name}</h3>
                  <Badge variant={plan.is_active ? "success" : "default"}>
                    {plan.is_active ? "Active" : "Deactivated"}
                  </Badge>
                </div>

                <div className="flex items-baseline gap-1.5">
                  <span className="text-3xl font-extrabold text-text">
                    {Number(plan.price_etb).toLocaleString()}
                  </span>
                  <span className="text-sm font-semibold text-text-muted">ETB</span>
                  <span className="text-xs text-text-muted">
                    / {plan.duration_value} {plan.duration_unit}
                  </span>
                </div>

                {plan.trainer_inclusive && (
                  <div>
                    <Badge variant="primary" className="text-xs">
                      🏋️ Personal Trainer Included
                    </Badge>
                  </div>
                )}

                {plan.description ? (
                  <p className="text-sm text-text-muted line-clamp-3">{plan.description}</p>
                ) : (
                  <p className="text-xs italic text-text-muted/60">No description provided</p>
                )}
              </div>

              <div className="pt-5 mt-4 border-t border-border flex items-center justify-end gap-2">
                <Button
                  onClick={() => handleOpenEditModal(plan)}
                  variant="secondary"
                  size="sm"
                  className="min-h-[36px]"
                >
                  Edit
                </Button>
                {plan.is_active && (
                  <Button
                    onClick={() => setDeactivatingPlan(plan)}
                    variant="danger"
                    size="sm"
                    className="min-h-[36px]"
                  >
                    Deactivate
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-surface border border-border rounded-card max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-lg font-bold text-text">
                {editingPlan ? "Edit Membership Plan" : "Create New Membership Plan"}
              </h3>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-text-muted hover:text-text text-xl p-1"
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            {modalError && (
              <Alert variant="error" onClose={() => setModalError(null)}>
                {modalError}
              </Alert>
            )}

            {modalWarning && (
              <Alert variant="warning" onClose={() => setModalWarning(null)}>
                {modalWarning}
              </Alert>
            )}

            <form onSubmit={handleModalSubmit} className="space-y-4">
              <FormField label="Plan Name" htmlFor="plan_name" required>
                <Input
                  id="plan_name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Monthly Standard, 3-Month Premium"
                  required
                  maxLength={100}
                />
              </FormField>

              <div className="grid grid-cols-2 gap-4">
                <FormField label="Duration Value" htmlFor="duration_value" required>
                  <Input
                    id="duration_value"
                    type="number"
                    min="1"
                    value={formData.duration_value}
                    onChange={(e) => setFormData({ ...formData, duration_value: e.target.value })}
                    required
                  />
                </FormField>

                <FormField label="Duration Unit" htmlFor="duration_unit" required>
                  <select
                    id="duration_unit"
                    value={formData.duration_unit}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        duration_unit: e.target.value as "days" | "months",
                      })
                    }
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px]"
                  >
                    <option value="months">Months (e.g. 1 month)</option>
                    <option value="days">Days (e.g. 15 days)</option>
                  </select>
                </FormField>
              </div>

              <FormField label="Price in ETB" htmlFor="price_etb" required>
                <Input
                  id="price_etb"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.price_etb}
                  onChange={(e) => setFormData({ ...formData, price_etb: e.target.value })}
                  placeholder="e.g. 1500.00"
                  required
                />
              </FormField>

              <FormField label="Description (Optional)">
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="What is included in this membership package?"
                  className="w-full bg-bg border border-border rounded-lg p-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary min-h-[80px]"
                />
              </FormField>

              <div className="p-3 bg-bg border border-border rounded-lg flex items-start gap-3">
                <input
                  type="checkbox"
                  id="trainer_inclusive"
                  checked={formData.trainer_inclusive}
                  onChange={(e) =>
                    setFormData({ ...formData, trainer_inclusive: e.target.checked })
                  }
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
                <label htmlFor="trainer_inclusive" className="text-sm cursor-pointer">
                  <span className="font-semibold text-text block">
                    Include Personal Training
                  </span>
                  <span className="text-xs text-text-muted">
                    Check if this plan entitles the member to a certified personal trainer.
                    (Warns if your gym currently has no active trainers.)
                  </span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-border">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setIsModalOpen(false)}
                  disabled={modalSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={modalSubmitting}>
                  {modalSubmitting ? <Spinner size="sm" /> : editingPlan ? "Update Plan" : "Create Plan"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Deactivate Confirmation Modal */}
      {deactivatingPlan && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface border border-border rounded-card max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-text">Deactivate Plan</h3>
            <p className="text-sm text-text-muted">
              Are you sure you want to deactivate{" "}
              <strong className="text-text">{deactivatingPlan.name}</strong>?
            </p>
            <div className="bg-surface-2/40 border border-border rounded-lg p-3 text-xs text-text-muted space-y-1">
              <p>• This plan will be hidden from new member registrations and signups.</p>
              <p>• All existing active subscriptions under this plan remain completely intact.</p>
            </div>
            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="secondary"
                onClick={() => setDeactivatingPlan(null)}
                disabled={deactivatingSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={handleConfirmDeactivate}
                disabled={deactivatingSubmitting}
              >
                {deactivatingSubmitting ? <Spinner size="sm" /> : "Deactivate Plan"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};
