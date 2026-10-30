import React, { useEffect, useState } from "react";
import {
  listAssignments,
  listUnassignedMembers,
  listTrainers,
  reassignTrainer,
  type TrainerAssignmentDetail,
  type UnassignedMember,
  type Trainer,
} from "../../api/trainers";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Spinner } from "../ui/Spinner";

export const AssignmentsSection: React.FC = () => {
  const [assignments, setAssignments] = useState<TrainerAssignmentDetail[]>([]);
  const [unassigned, setUnassigned] = useState<UnassignedMember[]>([]);
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedMemberId, setSelectedMemberId] = useState<string>("");
  const [selectedMemberName, setSelectedMemberName] = useState<string>("");
  const [currentTrainerName, setCurrentTrainerName] = useState<string>("");
  const [targetTrainerId, setTargetTrainerId] = useState<string>("");
  const [confirmOverCapacity, setConfirmOverCapacity] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const [assignmentsRes, unassignedRes, trainersRes] = await Promise.all([
        listAssignments(),
        listUnassignedMembers(),
        listTrainers(),
      ]);
      setAssignments(assignmentsRes);
      setUnassigned(unassignedRes);
      setTrainers(trainersRes);
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load trainer assignments.";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openReassignModal = (
    memberId: string,
    memberName: string,
    currentTrainer: string
  ) => {
    setSelectedMemberId(memberId);
    setSelectedMemberName(memberName);
    setCurrentTrainerName(currentTrainer);
    setTargetTrainerId("");
    setConfirmOverCapacity(false);
    setModalError(null);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setSelectedMemberId("");
    setSelectedMemberName("");
    setCurrentTrainerName("");
    setTargetTrainerId("");
    setConfirmOverCapacity(false);
    setModalError(null);
  };

  const selectedTargetTrainer = trainers.find((t) => t.id === targetTrainerId);
  const isTargetOverCapacity =
    selectedTargetTrainer &&
    selectedTargetTrainer.client_count >= selectedTargetTrainer.max_clients;

  const handleSubmitReassignment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMemberId || !targetTrainerId) {
      setModalError("Please select a trainer.");
      return;
    }

    if (isTargetOverCapacity && !confirmOverCapacity) {
      setModalError(
        "This trainer is at or over capacity. You must check the confirmation box to assign them."
      );
      return;
    }

    setModalError(null);
    setIsSubmitting(true);
    try {
      const res = await reassignTrainer({
        member_id: selectedMemberId,
        trainer_id: targetTrainerId,
        confirm_over_capacity: confirmOverCapacity,
      });

      setSuccessMsg(res.detail || "Trainer assigned successfully.");
      closeModal();
      await fetchData();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to assign trainer.";
      setModalError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center flex flex-col items-center gap-3">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">
          Loading trainer assignments...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-text">
            Trainer Assignments
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Manage member-to-trainer assignments, reassignments, and review
            members waiting for trainers.
          </p>
        </div>
      </div>

      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}
      {successMsg && (
        <Alert variant="success" onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {/* Unassigned Members Section */}
      {unassigned.length > 0 && (
        <Card className="bg-surface border-warning/40 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-warning inline-block" />
              <h3 className="text-sm font-bold uppercase tracking-wider text-text">
                Unassigned Members on Trainer Plans ({unassigned.length})
              </h3>
            </div>
            <Badge variant="warning">Action Needed</Badge>
          </div>
          <p className="text-xs text-text-muted">
            The following active members have trainer-inclusive plans but no
            assigned trainer (e.g. all trainers were full at payment).
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="py-2 px-3 font-semibold">Member</th>
                  <th className="py-2 px-3 font-semibold">Phone</th>
                  <th className="py-2 px-3 font-semibold">Plan</th>
                  <th className="py-2 px-3 font-semibold">Status</th>
                  <th className="py-2 px-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {unassigned.map((m) => (
                  <tr
                    key={m.member_id}
                    className="hover:bg-surface-elevated/40"
                  >
                    <td className="py-2.5 px-3 font-medium text-text">
                      {m.full_name}
                    </td>
                    <td className="py-2.5 px-3 text-text-muted">{m.phone}</td>
                    <td className="py-2.5 px-3 text-text">{m.plan_name}</td>
                    <td className="py-2.5 px-3">
                      <Badge
                        variant="success"
                        className="capitalize text-[10px]"
                      >
                        {m.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() =>
                          openReassignModal(m.member_id, m.full_name, "None")
                        }
                      >
                        Assign Trainer
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Current Active Assignments */}
      <Card className="bg-surface border-border p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-wider text-text">
            Active Trainer Assignments ({assignments.length})
          </h3>
          <Badge variant="secondary">{assignments.length} Active</Badge>
        </div>

        {assignments.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-xs">
            No active trainer assignments found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="py-2 px-3 font-semibold">Member</th>
                  <th className="py-2 px-3 font-semibold">Plan</th>
                  <th className="py-2 px-3 font-semibold">Assigned Trainer</th>
                  <th className="py-2 px-3 font-semibold">Trainer Load</th>
                  <th className="py-2 px-3 font-semibold">Assigned Date</th>
                  <th className="py-2 px-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {assignments.map((a) => {
                  const trainerName =
                    a.trainer.user?.full_name ||
                    a.trainer.user?.email ||
                    "Unknown";
                  return (
                    <tr key={a.id} className="hover:bg-surface-elevated/40">
                      <td className="py-2.5 px-3">
                        <div className="font-medium text-text">
                          {a.member.full_name}
                        </div>
                        <div className="text-[11px] text-text-muted">
                          {a.member.phone}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-text">
                        {a.member.plan_name || "—"}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-semibold text-text">
                          {trainerName}
                        </span>
                        {a.trainer.specialization && (
                          <div className="text-[10px] text-text-muted">
                            {a.trainer.specialization}
                          </div>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-mono text-xs">
                          {a.trainer.client_count} / {a.trainer.max_clients}
                        </span>
                        {a.trainer.client_count >= a.trainer.max_clients && (
                          <Badge variant="warning" className="ml-2 text-[10px]">
                            Full
                          </Badge>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-text-muted">
                        {a.assigned_at
                          ? new Date(a.assigned_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            openReassignModal(
                              a.member.id,
                              a.member.full_name,
                              trainerName
                            )
                          }
                        >
                          Reassign
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

      {/* Assign / Reassign Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <Card className="w-full max-w-md bg-surface border-border p-6 space-y-5">
            <div>
              <h3 className="text-base font-bold text-text">
                {currentTrainerName === "None"
                  ? "Assign Trainer"
                  : "Reassign Trainer"}
              </h3>
              <p className="text-xs text-text-muted mt-0.5">
                Member:{" "}
                <strong className="text-text">{selectedMemberName}</strong>
              </p>
              {currentTrainerName !== "None" && (
                <p className="text-xs text-text-muted">
                  Current Trainer:{" "}
                  <strong className="text-text">{currentTrainerName}</strong>
                </p>
              )}
            </div>

            {modalError && <Alert variant="danger">{modalError}</Alert>}

            <form onSubmit={handleSubmitReassignment} className="space-y-4">
              <FormField
                label="Select New Trainer"
                htmlFor="target-trainer"
                required
              >
                <select
                  id="target-trainer"
                  value={targetTrainerId}
                  onChange={(e) => {
                    setTargetTrainerId(e.target.value);
                    setConfirmOverCapacity(false);
                    setModalError(null);
                  }}
                  className="w-full bg-surface-elevated border border-border rounded px-3 py-2 text-xs text-text focus:outline-none focus:border-primary"
                  required
                >
                  <option value="">-- Choose an active trainer --</option>
                  {trainers.map((t) => {
                    const name =
                      t.user?.full_name || t.user?.email || "Trainer";
                    const isFull = t.client_count >= t.max_clients;
                    return (
                      <option key={t.id} value={t.id}>
                        {name} ({t.client_count} / {t.max_clients} clients){" "}
                        {isFull ? "[AT CAPACITY]" : ""}
                      </option>
                    );
                  })}
                </select>
              </FormField>

              {/* Over capacity warning & explicit confirmation checkbox */}
              {isTargetOverCapacity && (
                <div className="p-3 bg-warning/10 border border-warning/30 rounded text-xs space-y-2">
                  <p className="text-warning font-semibold">
                    Warning: Selected trainer has reached maximum capacity (
                    {selectedTargetTrainer?.client_count} /{" "}
                    {selectedTargetTrainer?.max_clients} clients).
                  </p>
                  <label className="flex items-start gap-2 cursor-pointer text-text text-xs">
                    <input
                      type="checkbox"
                      checked={confirmOverCapacity}
                      onChange={(e) => setConfirmOverCapacity(e.target.checked)}
                      className="mt-0.5 rounded border-border text-primary focus:ring-0"
                    />
                    <span>
                      I confirm exceeding this trainer&apos;s capacity limit for
                      this member.
                    </span>
                  </label>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={closeModal}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={isSubmitting || !targetTrainerId}
                >
                  {isSubmitting ? "Saving..." : "Confirm Assignment"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};
