import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  listExpenses,
  createExpense,
  voidExpense,
  getFinancialReport,
  getAttendanceReport,
} from "../../api/expenses";
import type {
  Expense,
  FinancialReport,
  AttendanceReport,
} from "../../types/expenses";
import { EXPENSE_CATEGORIES } from "../../types/expenses";
import { Card, Button, Badge, Modal, Input, Spinner, Alert } from "../ui";

interface ExpensesSectionProps {
  userRole?: string;
}

export const ExpensesSection: React.FC<ExpensesSectionProps> = ({ userRole }) => {
  const canManage = userRole === "owner" || userRole === "manager";

  const [activeTab, setActiveTab] = useState<"ledger" | "financial" | "attendance">("ledger");

  // Expenses Ledger state
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loadingExpenses, setLoadingExpenses] = useState<boolean>(true);
  const [expensesError, setExpensesError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [showVoided, setShowVoided] = useState<boolean>(false);

  // Modals state
  const [isAddOpen, setIsAddOpen] = useState<boolean>(false);
  const [voidingExpense, setVoidingExpense] = useState<Expense | null>(null);
  const [formAmount, setFormAmount] = useState<string>("");
  const [formCategory, setFormCategory] = useState<string>("other");
  const [formIncurredOn, setFormIncurredOn] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [formNote, setFormNote] = useState<string>("");
  const [voidReason, setVoidReason] = useState<string>("");
  const [modalSubmitting, setModalSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Reports state
  const [financialReport, setFinancialReport] = useState<FinancialReport | null>(null);
  const [attendanceReport, setAttendanceReport] = useState<AttendanceReport | null>(null);
  const [loadingReport, setLoadingReport] = useState<boolean>(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportStartDate, setReportStartDate] = useState<string>("");
  const [reportEndDate, setReportEndDate] = useState<string>("");

  const fetchExpensesList = useCallback(async () => {
    try {
      setLoadingExpenses(true);
      setExpensesError(null);
      const data = await listExpenses({
        category: selectedCategory === "all" ? undefined : selectedCategory,
        include_void: true,
      });
      setExpenses(data);
    } catch (err: unknown) {
      setExpensesError(err instanceof Error ? err.message : "Failed to load expenses.");
    } finally {
      setLoadingExpenses(false);
    }
  }, [selectedCategory]);

  const fetchFinancialData = useCallback(async () => {
    try {
      setLoadingReport(true);
      setReportError(null);
      const data = await getFinancialReport({
        start_date: reportStartDate || undefined,
        end_date: reportEndDate || undefined,
      });
      setFinancialReport(data);
    } catch (err: unknown) {
      setReportError(err instanceof Error ? err.message : "Failed to load financial report.");
    } finally {
      setLoadingReport(false);
    }
  }, [reportStartDate, reportEndDate]);

  const fetchAttendanceData = useCallback(async () => {
    try {
      setLoadingReport(true);
      setReportError(null);
      const data = await getAttendanceReport({
        start_date: reportStartDate || undefined,
        end_date: reportEndDate || undefined,
      });
      setAttendanceReport(data);
    } catch (err: unknown) {
      setReportError(err instanceof Error ? err.message : "Failed to load attendance report.");
    } finally {
      setLoadingReport(false);
    }
  }, [reportStartDate, reportEndDate]);

  useEffect(() => {
    if (activeTab === "ledger") {
      fetchExpensesList();
    } else if (activeTab === "financial") {
      fetchFinancialData();
    } else if (activeTab === "attendance") {
      fetchAttendanceData();
    }
  }, [activeTab, fetchExpensesList, fetchFinancialData, fetchAttendanceData]);

  const handleOpenAdd = () => {
    setFormAmount("");
    setFormCategory("other");
    setFormIncurredOn(new Date().toISOString().split("T")[0]);
    setFormNote("");
    setModalError(null);
    setIsAddOpen(true);
  };

  const handleSaveExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalSubmitting(true);
    setModalError(null);
    try {
      const amountNum = parseFloat(formAmount);
      if (isNaN(amountNum) || amountNum <= 0) {
        throw new Error("Amount must be greater than zero.");
      }
      if (amountNum > 10000000) {
        throw new Error("Amount cannot exceed 10,000,000 ETB.");
      }

      await createExpense({
        amount_etb: amountNum,
        category: formCategory,
        incurred_on: formIncurredOn,
        note: formNote.trim() || undefined,
      });

      setIsAddOpen(false);
      await fetchExpensesList();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : "Failed to record expense.");
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleConfirmVoid = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!voidingExpense) return;
    setModalSubmitting(true);
    setModalError(null);
    try {
      if (!voidReason.trim() || voidReason.trim().length < 2) {
        throw new Error("Please provide a reason for voiding (at least 2 characters).");
      }

      await voidExpense(voidingExpense.id, voidReason.trim());
      setVoidingExpense(null);
      setVoidReason("");
      await fetchExpensesList();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : "Failed to void expense.");
    } finally {
      setModalSubmitting(false);
    }
  };

  const filteredExpenses = useMemo(() => {
    return expenses.filter((item) => {
      if (!showVoided && item.is_void) return false;
      return true;
    });
  }, [expenses, showVoided]);

  const activeTotalETB = useMemo(() => {
    return expenses
      .filter((e) => !e.is_void)
      .reduce((sum, e) => sum + Number(e.amount_etb), 0);
  }, [expenses]);

  const getCategoryLabel = (catCode: string) => {
    const found = EXPENSE_CATEGORIES.find((c) => c.code === catCode);
    return found ? found.label : catCode;
  };

  if (!canManage) {
    return (
      <Alert variant="danger" title="Access Denied">
        Expense tracking and financial reports are restricted to gym Owners and Managers.
      </Alert>
    );
  }

  return (
    <div className="space-y-6" data-testid="expenses-section">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Expenses & Reports</h1>
          <p className="text-sm text-text-muted mt-1">
            Track gym expenditures, review net financial income, and monitor attendance summaries.
          </p>
        </div>
        {activeTab === "ledger" && (
          <Button variant="primary" onClick={handleOpenAdd} data-testid="btn-open-log-expense">
            Log Expense
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border space-x-4">
        <button
          onClick={() => setActiveTab("ledger")}
          className={`pb-2 px-1 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "ledger"
              ? "border-primary text-primary"
              : "border-transparent text-text-muted hover:text-text"
          }`}
          data-testid="tab-expenses-ledger"
        >
          Expenses Ledger
        </button>
        <button
          onClick={() => setActiveTab("financial")}
          className={`pb-2 px-1 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "financial"
              ? "border-primary text-primary"
              : "border-transparent text-text-muted hover:text-text"
          }`}
          data-testid="tab-financial-report"
        >
          Financial Report
        </button>
        <button
          onClick={() => setActiveTab("attendance")}
          className={`pb-2 px-1 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "attendance"
              ? "border-primary text-primary"
              : "border-transparent text-text-muted hover:text-text"
          }`}
          data-testid="tab-attendance-report"
        >
          Attendance Report
        </button>
      </div>

      {/* TAB 1: Expenses Ledger */}
      {activeTab === "ledger" && (
        <div className="space-y-6">
          {/* Stat Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="p-4 bg-surface border-border">
              <span className="text-xs uppercase tracking-wider text-text-muted font-semibold block">
                Total Active Expenses
              </span>
              <span className="text-2xl font-bold text-text mt-1 block" data-testid="total-active-expenses">
                {activeTotalETB.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{" "}
                ETB
              </span>
              <span className="text-xs text-text-muted mt-1 block">
                Excludes voided and cancelled entries
              </span>
            </Card>

            <Card className="p-4 bg-surface border-border">
              <span className="text-xs uppercase tracking-wider text-text-muted font-semibold block">
                Recorded Entries
              </span>
              <span className="text-2xl font-bold text-text mt-1 block">
                {expenses.filter((e) => !e.is_void).length}
              </span>
              <span className="text-xs text-text-muted mt-1 block">
                {expenses.filter((e) => e.is_void).length} voided records
              </span>
            </Card>

            <Card className="p-4 bg-surface border-border">
              <span className="text-xs uppercase tracking-wider text-text-muted font-semibold block">
                Audit Guarantee
              </span>
              <span className="text-xs text-text-muted mt-2 block leading-relaxed">
                Immutable records: expenses are never deleted from database. Corrections create void audit entries.
              </span>
            </Card>
          </div>

          {/* Filters */}
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <label className="text-xs font-medium text-text-muted">Category:</label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="h-9 px-3 py-1 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
                  data-testid="filter-category"
                >
                  <option value="all">All Categories</option>
                  {EXPENSE_CATEGORIES.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              <label className="flex items-center gap-2 cursor-pointer text-xs text-text-muted">
                <input
                  type="checkbox"
                  checked={showVoided}
                  onChange={(e) => setShowVoided(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary h-4 w-4"
                  data-testid="toggle-show-voided"
                />
                Show voided expenses
              </label>
            </div>
          </Card>

          {expensesError && <Alert variant="danger">{expensesError}</Alert>}

          {/* Table */}
          <Card className="overflow-hidden">
            {loadingExpenses ? (
              <div className="p-8 flex justify-center">
                <Spinner size="md" />
              </div>
            ) : filteredExpenses.length === 0 ? (
              <div className="p-8 text-center text-sm text-text-muted">
                No expenses found matching the selected filters.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-text border-collapse">
                  <thead className="bg-surface-2/60 text-xs uppercase tracking-wider text-text-muted border-b border-border">
                    <tr>
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Amount (ETB)</th>
                      <th className="py-3 px-4">Note / Equipment</th>
                      <th className="py-3 px-4">Logged By</th>
                      <th className="py-3 px-4 text-right">Status / Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filteredExpenses.map((exp) => (
                      <tr
                        key={exp.id}
                        className={`hover:bg-surface-2/30 transition-colors ${
                          exp.is_void ? "opacity-60 bg-surface-2/20" : ""
                        }`}
                        data-testid={`expense-row-${exp.id}`}
                      >
                        <td className="py-3 px-4 whitespace-nowrap text-xs text-text-muted">
                          {exp.incurred_on}
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-medium text-xs">
                            {getCategoryLabel(exp.category)}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono font-semibold text-xs whitespace-nowrap">
                          {Number(exp.amount_etb).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}{" "}
                          ETB
                        </td>
                        <td className="py-3 px-4 text-xs text-text-muted max-w-xs truncate">
                          {exp.note || "—"}
                          {exp.equipment_name && (
                            <span className="ml-1 text-[11px] text-primary">
                              (Equip: {exp.equipment_name})
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-xs text-text-muted">
                          {exp.logged_by_name || "—"}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          {exp.is_void ? (
                            <div className="flex flex-col items-end">
                              <Badge variant="neutral">Voided</Badge>
                              {exp.void_reason && (
                                <span className="text-[10px] text-text-muted mt-0.5 truncate max-w-[150px]" title={exp.void_reason}>
                                  Reason: {exp.void_reason}
                                </span>
                              )}
                            </div>
                          ) : (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-danger hover:text-danger-hover text-xs"
                              onClick={() => {
                                setVoidingExpense(exp);
                                setVoidReason("");
                                setModalError(null);
                              }}
                              data-testid={`btn-void-${exp.id}`}
                            >
                              Void
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* TAB 2: Financial Report */}
      {activeTab === "financial" && (
        <div className="space-y-6">
          {/* Date Range Selector */}
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-medium text-text-muted">Period:</span>
                <Input
                  type="date"
                  value={reportStartDate}
                  onChange={(e) => setReportStartDate(e.target.value)}
                  className="w-36 h-9 text-xs"
                />
                <span className="text-xs text-text-muted">to</span>
                <Input
                  type="date"
                  value={reportEndDate}
                  onChange={(e) => setReportEndDate(e.target.value)}
                  className="w-36 h-9 text-xs"
                />
                <Button size="sm" variant="secondary" onClick={fetchFinancialData} disabled={loadingReport}>
                  Apply
                </Button>
                {(reportStartDate || reportEndDate) && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setReportStartDate("");
                      setReportEndDate("");
                    }}
                  >
                    Clear Filter
                  </Button>
                )}
              </div>
              <span className="text-xs text-text-muted">
                {financialReport?.period?.start_date && financialReport?.period?.end_date
                  ? `${financialReport.period.start_date} to ${financialReport.period.end_date}`
                  : "All-time to date"}
              </span>
            </div>
          </Card>

          {reportError && <Alert variant="danger">{reportError}</Alert>}

          {loadingReport ? (
            <div className="p-12 flex justify-center">
              <Spinner size="md" />
            </div>
          ) : financialReport ? (
            <div className="space-y-6">
              {/* Core Financial Stat Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    Confirmed Revenue
                  </span>
                  <span className="text-xl font-bold text-text block">
                    {Number(financialReport.confirmed_gross_revenue_etb).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{" "}
                    ETB
                  </span>
                  <span className="text-[11px] text-text-muted block">
                    Reversals: {Number(financialReport.reversed_payments_etb).toLocaleString()} ETB
                  </span>
                </Card>

                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    Net Revenue
                  </span>
                  <span className="text-xl font-bold text-emerald-500 block" data-testid="stat-net-revenue">
                    {Number(financialReport.net_revenue_etb).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{" "}
                    ETB
                  </span>
                  <span className="text-[11px] text-text-muted block">
                    Confirmed receipts minus refunds
                  </span>
                </Card>

                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    Active Expenses
                  </span>
                  <span className="text-xl font-bold text-amber-500 block" data-testid="stat-total-expenses">
                    {Number(financialReport.total_expenses_etb).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{" "}
                    ETB
                  </span>
                  <span className="text-[11px] text-text-muted block">
                    Non-voided operational costs
                  </span>
                </Card>

                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    Net Income
                  </span>
                  <span
                    className={`text-xl font-bold block ${
                      Number(financialReport.net_income_etb) >= 0 ? "text-emerald-500" : "text-rose-500"
                    }`}
                    data-testid="stat-net-income"
                  >
                    {Number(financialReport.net_income_etb).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{" "}
                    ETB
                  </span>
                  <span className="text-[11px] text-text-muted block">
                    Net Revenue − Total Expenses
                  </span>
                </Card>
              </div>

              {/* Breakdowns */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Expenses by Category */}
                <Card className="p-5 space-y-4">
                  <div className="border-b border-border pb-3">
                    <h3 className="text-sm font-bold text-text">Expenses by Category</h3>
                    <p className="text-xs text-text-muted">Breakdown of operational expenditures.</p>
                  </div>
                  {Object.keys(financialReport.expenses_by_category).length === 0 ? (
                    <p className="text-xs text-text-muted py-4 text-center">No expenses recorded for this period.</p>
                  ) : (
                    <div className="space-y-3">
                      {Object.entries(financialReport.expenses_by_category).map(([catKey, item]) => (
                        <div key={catKey} className="flex items-center justify-between text-xs">
                          <span className="font-medium text-text">{getCategoryLabel(catKey)}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-text-muted">({item.count} items)</span>
                            <span className="font-mono font-semibold text-text">
                              {Number(item.total_etb).toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}{" "}
                              ETB
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>

                {/* Revenue by Plan */}
                <Card className="p-5 space-y-4">
                  <div className="border-b border-border pb-3">
                    <h3 className="text-sm font-bold text-text">Revenue by Membership Plan</h3>
                    <p className="text-xs text-text-muted">Confirmed income collected per membership tier.</p>
                  </div>
                  {financialReport.revenue_by_plan.length === 0 ? (
                    <p className="text-xs text-text-muted py-4 text-center">No plan payment revenue recorded for this period.</p>
                  ) : (
                    <div className="space-y-3">
                      {financialReport.revenue_by_plan.map((p) => (
                        <div key={p.plan_id} className="flex items-center justify-between text-xs">
                          <span className="font-medium text-text">{p.plan_name}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-text-muted">({p.payment_count} payments)</span>
                            <span className="font-mono font-semibold text-emerald-500">
                              {Number(p.total_etb).toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}{" "}
                              ETB
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* TAB 3: Attendance Report */}
      {activeTab === "attendance" && (
        <div className="space-y-6">
          {/* Date Range Selector */}
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-medium text-text-muted">Period:</span>
                <Input
                  type="date"
                  value={reportStartDate}
                  onChange={(e) => setReportStartDate(e.target.value)}
                  className="w-36 h-9 text-xs"
                />
                <span className="text-xs text-text-muted">to</span>
                <Input
                  type="date"
                  value={reportEndDate}
                  onChange={(e) => setReportEndDate(e.target.value)}
                  className="w-36 h-9 text-xs"
                />
                <Button size="sm" variant="secondary" onClick={fetchAttendanceData} disabled={loadingReport}>
                  Apply
                </Button>
                {(reportStartDate || reportEndDate) && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setReportStartDate("");
                      setReportEndDate("");
                    }}
                  >
                    Clear Filter
                  </Button>
                )}
              </div>
              <span className="text-xs text-text-muted">
                {attendanceReport?.period?.start_date && attendanceReport?.period?.end_date
                  ? `${attendanceReport.period.start_date} to ${attendanceReport.period.end_date}`
                  : "All-time to date"}
              </span>
            </div>
          </Card>

          {reportError && <Alert variant="danger">{reportError}</Alert>}

          {loadingReport ? (
            <div className="p-12 flex justify-center">
              <Spinner size="md" />
            </div>
          ) : attendanceReport ? (
            <div className="space-y-6">
              {/* Stat Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    Total Check-ins
                  </span>
                  <span className="text-2xl font-bold text-text block" data-testid="stat-total-checkins">
                    {attendanceReport.total_check_ins}
                  </span>
                  <span className="text-[11px] text-text-muted block">Gym visits logged</span>
                </Card>

                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    Unique Members
                  </span>
                  <span className="text-2xl font-bold text-primary block" data-testid="stat-unique-members">
                    {attendanceReport.unique_members}
                  </span>
                  <span className="text-[11px] text-text-muted block">Distinct members who visited</span>
                </Card>

                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    QR Scans
                  </span>
                  <span className="text-2xl font-bold text-emerald-500 block">
                    {attendanceReport.qr_check_ins}
                  </span>
                  <span className="text-[11px] text-text-muted block">
                    {attendanceReport.total_check_ins > 0
                      ? `${Math.round((attendanceReport.qr_check_ins / attendanceReport.total_check_ins) * 100)}% of check-ins`
                      : "0%"}
                  </span>
                </Card>

                <Card className="p-4 bg-surface border-border space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                    Manual Overrides
                  </span>
                  <span className="text-2xl font-bold text-amber-500 block">
                    {attendanceReport.manual_override_check_ins}
                  </span>
                  <span className="text-[11px] text-text-muted block">Staff verified admissions</span>
                </Card>
              </div>

              {/* Daily Breakdown List */}
              <Card className="p-5 space-y-4">
                <div className="border-b border-border pb-3">
                  <h3 className="text-sm font-bold text-text">Daily Check-in Activity</h3>
                  <p className="text-xs text-text-muted">Recorded check-in volume per day.</p>
                </div>
                {attendanceReport.daily_counts.length === 0 ? (
                  <p className="text-xs text-text-muted py-4 text-center">No attendance records found for this period.</p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {attendanceReport.daily_counts.map((d) => (
                      <div
                        key={d.date}
                        className="p-3 bg-surface-2/40 border border-border rounded-lg flex items-center justify-between text-xs"
                      >
                        <span className="font-medium text-text">{d.date}</span>
                        <span className="font-semibold text-primary">{d.count} visits</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          ) : null}
        </div>
      )}

      {/* Log Expense Modal */}
      <Modal isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} title="Log New Expense">
        <form onSubmit={handleSaveExpense} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Amount (ETB) *</label>
            <Input
              type="number"
              step="0.01"
              min="0.01"
              max="10000000"
              required
              placeholder="e.g. 15000.00"
              value={formAmount}
              onChange={(e) => setFormAmount(e.target.value)}
              data-testid="input-expense-amount"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Category *</label>
            <select
              required
              className="w-full h-10 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary"
              value={formCategory}
              onChange={(e) => setFormCategory(e.target.value)}
              data-testid="select-expense-category"
            >
              {EXPENSE_CATEGORIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Date Incurred *</label>
            <Input
              type="date"
              required
              max={new Date().toISOString().split("T")[0]}
              value={formIncurredOn}
              onChange={(e) => setFormIncurredOn(e.target.value)}
              data-testid="input-expense-date"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Note / Description (optional)</label>
            <textarea
              maxLength={500}
              className="w-full h-20 px-3 py-2 text-sm rounded-md border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              placeholder="e.g. Monthly internet broadband bill"
              value={formNote}
              onChange={(e) => setFormNote(e.target.value)}
              data-testid="input-expense-note"
            />
            <span className="text-[10px] text-text-muted block text-right">{formNote.length}/500</span>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button type="button" variant="ghost" onClick={() => setIsAddOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={modalSubmitting} data-testid="btn-save-expense">
              {modalSubmitting ? "Recording..." : "Record Expense"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Void Expense Modal */}
      <Modal
        isOpen={!!voidingExpense}
        onClose={() => setVoidingExpense(null)}
        title="Void Expense Entry"
      >
        <form onSubmit={handleConfirmVoid} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}
          <div className="p-3 bg-surface-2/60 border border-border rounded-lg text-xs space-y-1">
            <div className="flex justify-between">
              <span className="text-text-muted">Category:</span>
              <span className="font-semibold text-text">
                {voidingExpense ? getCategoryLabel(voidingExpense.category) : ""}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Amount:</span>
              <span className="font-semibold text-text font-mono">
                {voidingExpense ? Number(voidingExpense.amount_etb).toLocaleString() : ""} ETB
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Date:</span>
              <span className="text-text">{voidingExpense?.incurred_on}</span>
            </div>
          </div>

          <Alert variant="warning">
            Voiding removes this expense from financial totals and reports. For auditing integrity, this entry remains on the ledger marked as voided.
          </Alert>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Reason for Voiding *
            </label>
            <Input
              required
              minLength={2}
              maxLength={255}
              placeholder="e.g. Duplicate entry logged by mistake"
              value={voidReason}
              onChange={(e) => setVoidReason(e.target.value)}
              data-testid="input-void-reason"
            />
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button type="button" variant="ghost" onClick={() => setVoidingExpense(null)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              className="bg-danger hover:bg-danger-hover text-white border-transparent"
              disabled={modalSubmitting}
              data-testid="btn-confirm-void"
            >
              {modalSubmitting ? "Voiding..." : "Confirm Void"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
