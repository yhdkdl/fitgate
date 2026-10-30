import React, { useEffect, useState } from "react";
import {
  listTrainers,
  updateTrainerCapacity,
  type Trainer,
} from "../../api/trainers";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";

export const TrainersManagementSection: React.FC = () => {
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [warningMsg, setWarningMsg] = useState<string | null>(null);

  // Edit capacity modal state
  const [editingTrainer, setEditingTrainer] = useState<Trainer | null>(null);
  const [capacityInput, setCapacityInput] = useState<string>("20");
  const [specializationInput, setSpecializationInput] = useState<string>("");
  const [modalError, setModalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchTrainers = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const res = await listTrainers();
      setTrainers(res);
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load trainers.";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrainers();
  }, []);

  const openEditModal = (trainer: Trainer) => {
    setEditingTrainer(trainer);
    setCapacityInput(String(trainer.max_clients));
    setSpecializationInput(trainer.specialization || "");
    setModalError(null);
  };

  const closeEditModal = () => {
    setEditingTrainer(null);
    setCapacityInput("20");
    setSpecializationInput("");
    setModalError(null);
  };

  const handleCapacitySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTrainer) return;

    setModalError(null);
    setSuccessMsg(null);
    setWarningMsg(null);

    const parsed = parseInt(capacityInput, 10);
    if (isNaN(parsed) || parsed < 1 || parsed > 200) {
      setModalError(
        "Maximum clients must be a whole number between 1 and 200."
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await updateTrainerCapacity(editingTrainer.id, {
        max_clients: parsed,
        specialization: specializationInput.trim() || null,
      });

      setSuccessMsg(res.detail || "Trainer capacity updated successfully.");
      if (res.warning) {
        setWarningMsg(res.warning);
      }

      setTrainers((prev) =>
        prev.map((t) => (t.id === editingTrainer.id ? res.trainer : t))
      );
      closeEditModal();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string; max_clients?: string[] } })?.data
          ?.detail ||
        (err as { data?: { max_clients?: string[] } })?.data
          ?.max_clients?.[0] ||
        "Failed to update trainer capacity.";
      setModalError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const parsedCurrentInput = parseInt(capacityInput, 10);
  const showPreWarning =
    editingTrainer &&
    !isNaN(parsedCurrentInput) &&
    parsedCurrentInput < editingTrainer.client_count;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-text">Trainers & Capacity</h2>
          <p className="text-sm text-text-muted mt-1">
            Manage trainer client capacity and view live client workloads.
          </p>
        </div>
      </div>

      {errorMsg && (
        <Alert variant="error" dismissible onDismiss={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      )}

      {warningMsg && (
        <Alert
          variant="warning"
          dismissible
          onDismiss={() => setWarningMsg(null)}
        >
          {warningMsg}
        </Alert>
      )}

      {successMsg && (
        <Alert
          variant="success"
          dismissible
          onDismiss={() => setSuccessMsg(null)}
        >
          {successMsg}
        </Alert>
      )}

      <Card className="p-0 overflow-hidden bg-surface">
        {loading ? (
          <div className="p-12 flex justify-center items-center">
            <Spinner size="lg" />
          </div>
        ) : trainers.length === 0 ? (
          <div className="p-12 text-center text-text-muted">
            <p className="font-medium text-text">No trainers found</p>
            <p className="text-sm mt-1">
              Invite a trainer in the Staff section to begin assigning clients.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2/50 text-text-muted text-xs uppercase font-semibold">
                  <th className="py-3 px-4">Trainer</th>
                  <th className="py-3 px-4">Contact</th>
                  <th className="py-3 px-4">Specialization</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Active Clients / Capacity</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {trainers.map((trainer) => {
                  const isOver = trainer.client_count >= trainer.max_clients;
                  return (
                    <tr
                      key={trainer.id}
                      className="hover:bg-surface-2/30 transition-colors"
                    >
                      <td className="py-3 px-4 font-medium text-text">
                        {trainer.user.full_name || "—"}
                      </td>
                      <td className="py-3 px-4 text-text-muted">
                        <div>{trainer.user.email}</div>
                        {trainer.user.phone && (
                          <div className="text-xs">{trainer.user.phone}</div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-text-muted">
                        {trainer.specialization || "General Fitness"}
                      </td>
                      <td className="py-3 px-4">
                        {trainer.user.is_active ? (
                          <Badge variant="success">Active</Badge>
                        ) : (
                          <Badge variant="neutral">Inactive</Badge>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span
                            className={`font-semibold ${
                              isOver ? "text-amber-400" : "text-text"
                            }`}
                          >
                            {trainer.client_count} / {trainer.max_clients}
                          </span>
                          {isOver && (
                            <Badge variant="warning">At Capacity</Badge>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => openEditModal(trainer)}
                        >
                          Edit Capacity
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Edit Capacity Modal */}
      {editingTrainer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-5">
            <div>
              <h3 className="text-lg font-bold text-text">
                Edit Trainer Capacity
              </h3>
              <p className="text-sm text-text-muted mt-1">
                {editingTrainer.user.full_name || editingTrainer.user.email}
              </p>
            </div>

            {modalError && (
              <Alert
                variant="error"
                dismissible
                onDismiss={() => setModalError(null)}
              >
                {modalError}
              </Alert>
            )}

            {showPreWarning && (
              <Alert variant="warning">
                Warning: Lowering capacity below the current client count (
                {editingTrainer.client_count}) is allowed, but new automatic
                assignments will not be assigned to this trainer until their
                active clients drop below the new capacity.
              </Alert>
            )}

            <form onSubmit={handleCapacitySubmit} className="space-y-4">
              <FormField
                label="Maximum Clients (1 – 200)"
                htmlFor="trainer-capacity"
                required
              >
                <Input
                  id="trainer-capacity"
                  type="number"
                  min="1"
                  max="200"
                  value={capacityInput}
                  onChange={(e) => setCapacityInput(e.target.value)}
                  disabled={isSubmitting}
                />
              </FormField>

              <FormField
                label="Specialization (optional)"
                htmlFor="trainer-specialization"
              >
                <Input
                  id="trainer-specialization"
                  type="text"
                  placeholder="e.g. Strength & Conditioning"
                  value={specializationInput}
                  onChange={(e) => setSpecializationInput(e.target.value)}
                  disabled={isSubmitting}
                />
              </FormField>

              <div className="flex items-center justify-end gap-3 pt-3">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={closeEditModal}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={isSubmitting}>
                  {isSubmitting ? "Saving..." : "Save Changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
