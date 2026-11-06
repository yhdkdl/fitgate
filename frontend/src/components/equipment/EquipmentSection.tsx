import React, { useEffect, useState } from "react";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { useAuth } from "../../context/AuthContext";
import { Spinner } from "../ui/Spinner";
import {
  listEquipment,
  createEquipment,
  updateEquipment,
  deleteEquipment,
  reportEquipmentIssue,
  updateEquipmentCondition,
} from "../../api/equipment";
import {
  EquipmentItem,
  EQUIPMENT_CATEGORIES,
  CONDITION_LABELS,
  ISSUE_REASONS,
} from "../../types/equipment";

interface EquipmentSectionProps {
  userRole: string;
}

function getErrorMessage(err: unknown, fallback: string): string {
  if (typeof err === "object" && err !== null) {
    const obj = err as Record<string, unknown>;
    if (typeof obj.detail === "string") return obj.detail;
    if (typeof obj.message === "string") return obj.message;
  }
  return fallback;
}

export const EquipmentSection: React.FC<EquipmentSectionProps> = ({
  userRole,
}) => {
  const { capabilities } = useAuth();
  const [equipmentList, setEquipmentList] = useState<EquipmentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [filterCondition, setFilterCondition] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modals state
  const [isAddOpen, setIsAddOpen] = useState<boolean>(false);
  const [editingItem, setEditingItem] = useState<EquipmentItem | null>(null);
  const [issueItem, setIssueItem] = useState<EquipmentItem | null>(null);
  const [conditionItem, setConditionItem] = useState<EquipmentItem | null>(
    null
  );
  const [logsItem, setLogsItem] = useState<EquipmentItem | null>(null);

  // Form states
  const [formName, setFormName] = useState<string>("");
  const [formCategory, setFormCategory] = useState<string>("barbell");
  const [formSerial, setFormSerial] = useState<string>("");
  const [formQuantity, setFormQuantity] = useState<number>(1);
  const [formMinQty, setFormMinQty] = useState<number | "">("");
  const [formCondition, setFormCondition] = useState<string>("good");
  const [formPurchaseDate, setFormPurchaseDate] = useState<string>("");
  const [formUnitPrice, setFormUnitPrice] = useState<string>("");
  const [formRecordAsExpense, setFormRecordAsExpense] =
    useState<boolean>(false);
  const [formSubmitting, setFormSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Issue report form state
  const [issueReason, setIssueReason] = useState<string>("broken");
  const [issueDetails, setIssueDetails] = useState<string>("");

  // Update condition form state
  const [newCondition, setNewCondition] = useState<string>("good");
  const [resolutionNotes, setResolutionNotes] = useState<string>("");

  const canManage = userRole === "owner" || userRole === "manager";
  const canReportIssue =
    userRole === "owner" ||
    userRole === "manager" ||
    userRole === "trainer" ||
    userRole === "reception";

  const fetchEquipment = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listEquipment();
      setEquipmentList(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to load equipment list."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEquipment();
  }, []);

  const handleOpenAdd = () => {
    setFormName("");
    setFormCategory("barbell");
    setFormSerial("");
    setFormQuantity(1);
    setFormMinQty("");
    setFormCondition("good");
    setFormPurchaseDate("");
    setFormUnitPrice("");
    setFormRecordAsExpense(false);
    setModalError(null);
    setIsAddOpen(true);
  };

  const handleOpenEdit = (item: EquipmentItem) => {
    setEditingItem(item);
    setFormName(item.name);
    setFormCategory(item.category);
    setFormSerial(item.serial_number || "");
    setFormQuantity(item.quantity);
    setFormMinQty(
      item.min_qty_threshold !== null ? item.min_qty_threshold : ""
    );
    setFormCondition(item.condition);
    setFormPurchaseDate(item.purchase_date || "");
    setFormUnitPrice(
      item.unit_purchase_price_etb !== null &&
        item.unit_purchase_price_etb !== undefined
        ? String(item.unit_purchase_price_etb)
        : ""
    );
    setFormRecordAsExpense(false);
    setModalError(null);
  };

  const handleSaveAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormSubmitting(true);
    setModalError(null);
    try {
      await createEquipment({
        name: formName.trim(),
        category: formCategory,
        serial_number: formSerial.trim() || undefined,
        quantity: Number(formQuantity),
        min_qty_threshold: formMinQty === "" ? null : Number(formMinQty),
        condition: formCondition,
        purchase_date: formPurchaseDate || null,
        unit_purchase_price_etb: formUnitPrice.trim()
          ? parseFloat(formUnitPrice)
          : null,
        record_as_expense:
          formRecordAsExpense &&
          !!formUnitPrice.trim() &&
          parseFloat(formUnitPrice) > 0,
      });
      setIsAddOpen(false);
      await fetchEquipment();
    } catch (err: unknown) {
      setModalError(getErrorMessage(err, "Failed to add equipment."));
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem) return;
    setFormSubmitting(true);
    setModalError(null);
    try {
      await updateEquipment(editingItem.id, {
        name: formName.trim(),
        category: formCategory,
        serial_number: formSerial.trim() || undefined,
        quantity: Number(formQuantity),
        min_qty_threshold: formMinQty === "" ? null : Number(formMinQty),
        condition: formCondition,
        purchase_date: formPurchaseDate || null,
        unit_purchase_price_etb: formUnitPrice.trim()
          ? parseFloat(formUnitPrice)
          : null,
        record_as_expense:
          formRecordAsExpense &&
          !!formUnitPrice.trim() &&
          parseFloat(formUnitPrice) > 0,
      });
      setEditingItem(null);
      await fetchEquipment();
    } catch (err: unknown) {
      setModalError(getErrorMessage(err, "Failed to update equipment."));
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to remove '${name}'?`)) return;
    try {
      await deleteEquipment(id);
      await fetchEquipment();
    } catch (err: unknown) {
      alert(getErrorMessage(err, "Failed to delete equipment."));
    }
  };

  const handleReportIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!issueItem) return;
    setFormSubmitting(true);
    setModalError(null);
    try {
      await reportEquipmentIssue(issueItem.id, {
        issue_reason: issueReason,
        other_details: issueDetails.trim(),
      });
      setIssueItem(null);
      setIssueDetails("");
      await fetchEquipment();
    } catch (err: unknown) {
      setModalError(getErrorMessage(err, "Failed to submit issue report."));
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleUpdateCondition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conditionItem) return;
    setFormSubmitting(true);
    setModalError(null);
    try {
      await updateEquipmentCondition(conditionItem.id, {
        condition: newCondition,
        resolution_notes: resolutionNotes.trim(),
      });
      setConditionItem(null);
      setResolutionNotes("");
      await fetchEquipment();
    } catch (err: unknown) {
      setModalError(getErrorMessage(err, "Failed to update condition."));
    } finally {
      setFormSubmitting(false);
    }
  };

  // Filtered equipment list
  const filteredList = equipmentList.filter((item) => {
    if (filterCategory !== "all" && item.category !== filterCategory)
      return false;
    if (filterCondition !== "all" && item.condition !== filterCondition)
      return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = item.name.toLowerCase().includes(q);
      const matchSerial = (item.serial_number || "").toLowerCase().includes(q);
      if (!matchName && !matchSerial) return false;
    }
    return true;
  });

  const lowQuantityItems = equipmentList.filter((item) => item.is_low_quantity);

  const distinctCategoriesCount = new Set(
    equipmentList.map((item) => item.category)
  ).size;
  const totalCategoriesCount = EQUIPMENT_CATEGORIES.length;

  let totalInvestment = 0;
  let noPriceCount = 0;
  equipmentList.forEach((item) => {
    const price = Number(item.unit_purchase_price_etb);
    if (price && price > 0) {
      totalInvestment += price * item.quantity;
    } else {
      noPriceCount += 1;
    }
  });

  const getCategoryLabel = (code: string) => {
    const found = EQUIPMENT_CATEGORIES.find((c) => c.code === code);
    return found ? found.label : code;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">
            Gym Equipment
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {canManage
              ? "Track, manage, and service gym machines and free weights."
              : "Catalog of workout equipment and active condition status."}
          </p>
        </div>
        {canManage && (
          <Button variant="primary" onClick={handleOpenAdd}>
            Add Equipment
          </Button>
        )}
      </div>

      {/* Low Quantity Warning Banner */}
      {canManage && lowQuantityItems.length > 0 && (
        <Alert variant="warning">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <span className="font-semibold">Low Quantity Alert:</span>{" "}
              {lowQuantityItems.length} item
              {lowQuantityItems.length > 1 ? "s have" : " has"} reached or
              fallen below the minimum stock threshold:
              <span className="ml-1 font-medium">
                {lowQuantityItems
                  .map(
                    (i) => `${i.name} (${i.quantity}/${i.min_qty_threshold})`
                  )
                  .join(", ")}
              </span>
            </div>
          </div>
        </Alert>
      )}

      {error && <Alert variant="danger">{error}</Alert>}

      {/* Categories Registered Note */}
      <div className="p-3 bg-surface-2/60 border border-border rounded-lg text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-1">
        <span className="text-text-muted">
          Register all available machines and gear to keep member workout
          routines accurate.
        </span>
        <span className="font-semibold text-text whitespace-nowrap">
          Categories registered: {distinctCategoriesCount} of{" "}
          {totalCategoriesCount}
        </span>
      </div>

      {/* Total Investment Card for Owner / Manager */}
      {canManage && (
        <Card className="p-4 bg-surface border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-xs uppercase tracking-wider text-text-muted block font-semibold">
              Total Investment
            </span>
            <span className="text-xl font-bold text-text">
              {totalInvestment.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{" "}
              ETB
            </span>
          </div>
          <div className="text-xs text-text-muted">
            {noPriceCount === 0
              ? "All registered equipment items have purchase prices recorded."
              : noPriceCount === 1
                ? "1 item has no price."
                : `${noPriceCount} items have no price.`}
          </div>
        </Card>
      )}

      {/* Filter and Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Search
            </label>
            <Input
              type="text"
              placeholder="Filter by name or serial..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Category
            </label>
            <select
              className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
            >
              <option value="all">All Categories</option>
              {EQUIPMENT_CATEGORIES.map((cat) => (
                <option key={cat.code} value={cat.code}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Condition
            </label>
            <select
              className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
              value={filterCondition}
              onChange={(e) => setFilterCondition(e.target.value)}
            >
              <option value="all">All Conditions</option>
              <option value="good">Good</option>
              <option value="needs_maintenance">Needs Maintenance</option>
              <option value="under_maintenance">Under Maintenance</option>
              <option value="out_of_service">Out of Service</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Equipment Table */}
      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center items-center">
            <Spinner size="lg" />
          </div>
        ) : filteredList.length === 0 ? (
          <div className="p-12 text-center text-text-muted">
            No equipment found matching criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-text border-collapse">
              <thead className="bg-surface-2/60 text-xs uppercase tracking-wider text-text-muted border-b border-border">
                <tr>
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">Category</th>
                  {userRole !== "member" && (
                    <th className="py-3 px-4">Serial #</th>
                  )}
                  <th className="py-3 px-4">Qty</th>
                  <th className="py-3 px-4">Condition</th>
                  <th className="py-3 px-4">Purchase Date</th>
                  {canManage && <th className="py-3 px-4">Price (ETB)</th>}
                  {canReportIssue && (
                    <th className="py-3 px-4 text-right">Actions</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredList.map((item) => {
                  const cond = CONDITION_LABELS[item.condition] || {
                    label: item.condition,
                    variant: "neutral",
                  };
                  return (
                    <tr
                      key={item.id}
                      className="hover:bg-surface-2/30 transition-colors"
                    >
                      <td className="py-3 px-4 font-medium">
                        <div>{item.name}</div>
                        {item.is_low_quantity && (
                          <span className="inline-block mt-0.5 text-xs text-amber-500 font-semibold">
                            ⚠️ Low Stock ({item.quantity} remaining)
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-text-muted">
                        {getCategoryLabel(item.category)}
                      </td>
                      {userRole !== "member" && (
                        <td className="py-3 px-4 text-text-muted font-mono text-xs">
                          {item.serial_number || "—"}
                        </td>
                      )}
                      <td className="py-3 px-4">
                        <span className="font-semibold">{item.quantity}</span>
                        {item.min_qty_threshold !== null && (
                          <span className="text-text-muted text-xs ml-1">
                            (min: {item.min_qty_threshold})
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={cond.variant}>{cond.label}</Badge>
                      </td>
                      <td className="py-3 px-4 text-text-muted">
                        {item.purchase_date || "—"}
                      </td>
                      {canManage && (
                        <td className="py-3 px-4 font-mono text-xs">
                          {item.unit_purchase_price_etb
                            ? `${Number(
                                item.unit_purchase_price_etb
                              ).toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })} ETB`
                            : "—"}
                        </td>
                      )}
                      {canReportIssue && (
                        <td className="py-3 px-4 text-right space-x-2 whitespace-nowrap">
                          {canManage && (
                            <>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleOpenEdit(item)}
                              >
                                Edit
                              </Button>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => {
                                  setConditionItem(item);
                                  setNewCondition(item.condition);
                                  setResolutionNotes("");
                                  setModalError(null);
                                }}
                              >
                                Status
                              </Button>
                            </>
                          )}
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => {
                              setIssueItem(item);
                              setIssueReason("broken");
                              setIssueDetails("");
                              setModalError(null);
                            }}
                          >
                            Report Issue
                          </Button>
                          {item.maintenance_logs &&
                            item.maintenance_logs.length > 0 && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setLogsItem(item)}
                              >
                                Logs ({item.maintenance_logs.length})
                              </Button>
                            )}
                          {canManage && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-danger hover:text-danger-hover"
                              onClick={() => handleDelete(item.id, item.name)}
                            >
                              Delete
                            </Button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Add Equipment Modal */}
      <Modal
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title="Add Gym Equipment"
      >
        <form onSubmit={handleSaveAdd} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Equipment Name *
            </label>
            <Input
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. Olympic Barbell 20kg"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Category *
            </label>
            <select
              required
              className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
              value={formCategory}
              onChange={(e) => setFormCategory(e.target.value)}
            >
              {EQUIPMENT_CATEGORIES.map((cat) => (
                <option key={cat.code} value={cat.code}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Serial Number (optional)
            </label>
            <Input
              value={formSerial}
              onChange={(e) => setFormSerial(e.target.value)}
              placeholder="Unique within gym"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Quantity *
              </label>
              <Input
                type="number"
                min="0"
                required
                value={formQuantity}
                onChange={(e) =>
                  setFormQuantity(parseInt(e.target.value, 10) || 0)
                }
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Low Stock Alert Min (optional)
              </label>
              <Input
                type="number"
                min="0"
                value={formMinQty}
                onChange={(e) =>
                  setFormMinQty(
                    e.target.value === "" ? "" : parseInt(e.target.value, 10)
                  )
                }
                placeholder="Alert threshold"
              />
            </div>
          </div>
          {canManage && (
            <div className="space-y-2">
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">
                  Unit Purchase Price (ETB, optional)
                </label>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="10000000"
                  placeholder="e.g. 45000.00"
                  value={formUnitPrice}
                  onChange={(e) => setFormUnitPrice(e.target.value)}
                />
              </div>
              {capabilities?.has_expenses && formUnitPrice && parseFloat(formUnitPrice) > 0 && (
                <label className="flex items-center gap-2 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formRecordAsExpense}
                    onChange={(e) => setFormRecordAsExpense(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary h-4 w-4"
                  />
                  <span className="text-xs text-text font-medium">
                    Also record as an expense
                  </span>
                </label>
              )}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Condition
              </label>
              <select
                className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
                value={formCondition}
                onChange={(e) => setFormCondition(e.target.value)}
              >
                <option value="good">Good</option>
                <option value="needs_maintenance">Needs Maintenance</option>
                <option value="under_maintenance">Under Maintenance</option>
                <option value="out_of_service">Out of Service</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Purchase Date
              </label>
              <Input
                type="date"
                value={formPurchaseDate}
                onChange={(e) => setFormPurchaseDate(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsAddOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={formSubmitting}>
              {formSubmitting ? "Adding..." : "Add Equipment"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Equipment Modal */}
      <Modal
        isOpen={!!editingItem}
        onClose={() => setEditingItem(null)}
        title="Edit Equipment"
      >
        <form onSubmit={handleSaveEdit} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Equipment Name *
            </label>
            <Input
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Category *
            </label>
            <select
              required
              className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
              value={formCategory}
              onChange={(e) => setFormCategory(e.target.value)}
            >
              {EQUIPMENT_CATEGORIES.map((cat) => (
                <option key={cat.code} value={cat.code}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Serial Number (optional)
            </label>
            <Input
              value={formSerial}
              onChange={(e) => setFormSerial(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Quantity *
              </label>
              <Input
                type="number"
                min="0"
                required
                value={formQuantity}
                onChange={(e) =>
                  setFormQuantity(parseInt(e.target.value, 10) || 0)
                }
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Low Stock Alert Min (optional)
              </label>
              <Input
                type="number"
                min="0"
                value={formMinQty}
                onChange={(e) =>
                  setFormMinQty(
                    e.target.value === "" ? "" : parseInt(e.target.value, 10)
                  )
                }
              />
            </div>
          </div>
          {canManage && (
            <div className="space-y-2">
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">
                  Unit Purchase Price (ETB, optional)
                </label>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="10000000"
                  placeholder="e.g. 45000.00"
                  value={formUnitPrice}
                  onChange={(e) => setFormUnitPrice(e.target.value)}
                />
              </div>
              {capabilities?.has_expenses && formUnitPrice && parseFloat(formUnitPrice) > 0 && (
                <label className="flex items-center gap-2 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formRecordAsExpense}
                    onChange={(e) => setFormRecordAsExpense(e.target.checked)}
                    className="rounded border-border text-primary focus:ring-primary h-4 w-4"
                  />
                  <span className="text-xs text-text font-medium">
                    Also record as an expense
                  </span>
                </label>
              )}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Condition
              </label>
              <select
                className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
                value={formCondition}
                onChange={(e) => setFormCondition(e.target.value)}
              >
                <option value="good">Good</option>
                <option value="needs_maintenance">Needs Maintenance</option>
                <option value="under_maintenance">Under Maintenance</option>
                <option value="out_of_service">Out of Service</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Purchase Date
              </label>
              <Input
                type="date"
                value={formPurchaseDate}
                onChange={(e) => setFormPurchaseDate(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setEditingItem(null)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={formSubmitting}>
              {formSubmitting ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Report Issue Modal */}
      <Modal
        isOpen={!!issueItem}
        onClose={() => setIssueItem(null)}
        title={`Report Issue: ${issueItem?.name}`}
      >
        <form onSubmit={handleReportIssue} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}
          <p className="text-sm text-text-muted">
            Reporting an issue flags this equipment as needing maintenance and
            alerts the gym owner.
          </p>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Issue Reason *
            </label>
            <select
              required
              className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
              value={issueReason}
              onChange={(e) => setIssueReason(e.target.value)}
            >
              {ISSUE_REASONS.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Additional Details
            </label>
            <textarea
              className="w-full h-24 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              placeholder="Describe symptoms, safety hazards, or specific broken parts..."
              value={issueDetails}
              onChange={(e) => setIssueDetails(e.target.value)}
              maxLength={200}
            />
            <div className="text-right text-xs text-text-muted">
              {issueDetails.length}/200
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIssueItem(null)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={formSubmitting}>
              {formSubmitting ? "Submitting..." : "Submit Report"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Update Condition Modal */}
      <Modal
        isOpen={!!conditionItem}
        onClose={() => setConditionItem(null)}
        title={`Update Condition: ${conditionItem?.name}`}
      >
        <form onSubmit={handleUpdateCondition} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Target Condition *
            </label>
            <select
              required
              className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
              value={newCondition}
              onChange={(e) => setNewCondition(e.target.value)}
            >
              <option value="good">
                Good (Resolves open maintenance logs)
              </option>
              <option value="needs_maintenance">Needs Maintenance</option>
              <option value="under_maintenance">Under Maintenance</option>
              <option value="out_of_service">Out of Service</option>
            </select>
          </div>
          {newCondition === "good" && (
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Resolution Notes
              </label>
              <textarea
                className="w-full h-20 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                placeholder="Notes on repair or inspection (saved to maintenance logs)..."
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                maxLength={500}
              />
            </div>
          )}
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setConditionItem(null)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={formSubmitting}>
              {formSubmitting ? "Updating..." : "Update Condition"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Maintenance Logs Modal */}
      <Modal
        isOpen={!!logsItem}
        onClose={() => setLogsItem(null)}
        title={`Maintenance History: ${logsItem?.name}`}
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
          {logsItem?.maintenance_logs?.length === 0 ? (
            <p className="text-sm text-text-muted">
              No maintenance events recorded.
            </p>
          ) : (
            logsItem?.maintenance_logs?.map((log) => (
              <div
                key={log.id}
                className="p-3 rounded-lg border border-border bg-surface-2/30 space-y-1"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-text uppercase">
                    {ISSUE_REASONS.find((r) => r.code === log.issue_reason)
                      ?.label || log.issue_reason}
                  </span>
                  <span className="text-text-muted">
                    {new Date(log.reported_at).toLocaleDateString()}
                  </span>
                </div>
                {log.other_details && (
                  <p className="text-xs text-text">{log.other_details}</p>
                )}
                <div className="text-xs text-text-muted">
                  Reported by: {log.reported_by_name}
                </div>
                {log.resolved_at ? (
                  <div className="pt-2 border-t border-border/50 text-xs text-emerald-500">
                    <span className="font-medium">Resolved:</span>{" "}
                    {new Date(log.resolved_at).toLocaleDateString()} by{" "}
                    {log.resolved_by_name}
                    {log.resolution_notes && (
                      <p className="text-text mt-0.5">{log.resolution_notes}</p>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-amber-500 font-medium pt-1">
                    Status: Open / Under Investigation
                  </div>
                )}
              </div>
            ))
          )}
        </div>
        <div className="flex justify-end pt-4 border-t border-border mt-4">
          <Button variant="ghost" onClick={() => setLogsItem(null)}>
            Close
          </Button>
        </div>
      </Modal>
    </div>
  );
};
