import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  listClasses,
  createClasses,
  updateClass,
  cancelClass,
  getClassRoster,
  bookClass,
  cancelClassBooking,
  markClassAttendance,
  getMyBookings,
  getTrainerSessions,
} from "../../api/classes";
import { listTrainers, type Trainer } from "../../api/trainers";
import { listGymMembers, type Member } from "../../api/members";
import type {
  ClassSession,
  ClassBooking,
  ClassTitle,
  ClassRosterResponse,
} from "../../types/classes";
import {
  CLASS_TITLE_OPTIONS,
  CLASS_DURATION_OPTIONS,
} from "../../types/classes";
import { Card, Button, Badge, Modal, Input, Spinner, Alert } from "../ui";

interface ClassScheduleSectionProps {
  userRole?: string;
}

export const ClassScheduleSection: React.FC<ClassScheduleSectionProps> = ({
  userRole = "member",
}) => {
  const isOwnerOrManager = userRole === "owner" || userRole === "manager";
  const isTrainer = userRole === "trainer";
  const isReception = userRole === "reception";
  const isMember = userRole === "member";
  const canMarkAttendance = isOwnerOrManager || isTrainer;

  // Active Tab for member: schedule vs my-bookings
  const [activeTab, setActiveTab] = useState<"schedule" | "my-bookings">(
    "schedule"
  );

  // Class sessions state
  const [sessions, setSessions] = useState<ClassSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [dayFilter, setDayFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("scheduled");

  // Member bookings state
  const [myBookings, setMyBookings] = useState<ClassBooking[]>([]);
  const [loadingBookings, setLoadingBookings] = useState<boolean>(false);
  const [bookingsError, setBookingsError] = useState<string | null>(null);

  // Trainers for scheduling
  const [trainers, setTrainers] = useState<Trainer[]>([]);

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [editingSession, setEditingSession] = useState<ClassSession | null>(
    null
  );
  const [cancellingSession, setCancellingSession] =
    useState<ClassSession | null>(null);
  const [rosterSession, setRosterSession] = useState<ClassSession | null>(null);
  const [rosterData, setRosterData] = useState<ClassRosterResponse | null>(
    null
  );
  const [loadingRoster, setLoadingRoster] = useState<boolean>(false);
  const [rosterError, setRosterError] = useState<string | null>(null);

  // Staff booking for member state
  const [bookingForMemberSession, setBookingForMemberSession] =
    useState<ClassSession | null>(null);
  const [memberSearchQuery, setMemberSearchQuery] = useState<string>("");
  const [memberSearchResults, setMemberSearchResults] = useState<Member[]>([]);
  const [searchingMembers, setSearchingMembers] = useState<boolean>(false);
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);

  // Form states for Create / Edit
  const [formTitle, setFormTitle] = useState<ClassTitle>("yoga");
  const [formOtherTitle, setFormOtherTitle] = useState<string>("");
  const [formTrainerId, setFormTrainerId] = useState<string>("");
  const [formStartTime, setFormStartTime] = useState<string>("");
  const [formDuration, setFormDuration] = useState<number>(60);
  const [formCapacity, setFormCapacity] = useState<number>(20);
  const [formRepeatWeeks, setFormRepeatWeeks] = useState<number>(1);
  const [modalSubmitting, setModalSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Action status notification
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Fetch classes
  const fetchClassesList = useCallback(async () => {
    try {
      setLoadingSessions(true);
      setSessionsError(null);
      let data: ClassSession[] = [];
      if (isTrainer) {
        data = await getTrainerSessions();
      } else {
        data = await listClasses({
          status: statusFilter === "all" ? undefined : statusFilter,
        });
      }
      setSessions(data);
    } catch (err: unknown) {
      setSessionsError(
        err instanceof Error ? err.message : "Failed to load classes."
      );
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  }, [isTrainer, statusFilter]);

  // Fetch member's bookings
  const fetchMemberBookings = useCallback(async () => {
    try {
      setLoadingBookings(true);
      setBookingsError(null);
      const data = await getMyBookings();
      setMyBookings(data);
    } catch (err: unknown) {
      setBookingsError(
        err instanceof Error ? err.message : "Failed to load bookings."
      );
      setMyBookings([]);
    } finally {
      setLoadingBookings(false);
    }
  }, []);

  // Fetch trainers for Owner/Manager
  useEffect(() => {
    if (isOwnerOrManager) {
      listTrainers()
        .then((data) => {
          setTrainers(data || []);
          if (data && data.length > 0 && !formTrainerId) {
            setFormTrainerId(data[0].id);
          }
        })
        .catch(() => {});
    }
  }, [isOwnerOrManager]);

  useEffect(() => {
    if (activeTab === "schedule") {
      fetchClassesList();
    } else if (activeTab === "my-bookings") {
      fetchMemberBookings();
    }
  }, [activeTab, fetchClassesList, fetchMemberBookings]);

  // Load roster
  const openRosterModal = async (session: ClassSession) => {
    setRosterSession(session);
    setLoadingRoster(true);
    setRosterError(null);
    try {
      const res = await getClassRoster(session.id);
      setRosterData(res);
    } catch (err: unknown) {
      setRosterError(
        err instanceof Error ? err.message : "Failed to load class roster."
      );
    } finally {
      setLoadingRoster(false);
    }
  };

  // Open Create Modal
  const handleOpenCreate = () => {
    setFormTitle("yoga");
    setFormOtherTitle("");
    if (trainers.length > 0) {
      setFormTrainerId(trainers[0].id);
    }
    // Default to tomorrow 10:00 AM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(10, 0, 0, 0);
    // Format YYYY-MM-DDTHH:mm
    const tzOffset = tomorrow.getTimezoneOffset() * 60000;
    const localISOTime = new Date(tomorrow.getTime() - tzOffset)
      .toISOString()
      .slice(0, 16);
    setFormStartTime(localISOTime);
    setFormDuration(60);
    setFormCapacity(20);
    setFormRepeatWeeks(1);
    setModalError(null);
    setIsCreateOpen(true);
  };

  // Open Edit Modal
  const handleOpenEdit = (session: ClassSession) => {
    setEditingSession(session);
    setFormTitle(session.title);
    setFormOtherTitle(session.other_title || "");
    setFormTrainerId(session.trainer);
    const dt = new Date(session.start_time);
    const tzOffset = dt.getTimezoneOffset() * 60000;
    const localISOTime = new Date(dt.getTime() - tzOffset)
      .toISOString()
      .slice(0, 16);
    setFormStartTime(localISOTime);
    setFormDuration(session.duration_minutes);
    setFormCapacity(session.capacity);
    setModalError(null);
  };

  // Handle Create Class
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalSubmitting(true);
    setModalError(null);
    try {
      if (formTitle === "other" && !formOtherTitle.trim()) {
        throw new Error("Custom title is required when title is Other.");
      }
      if (!formTrainerId) {
        throw new Error("Please select a trainer.");
      }
      if (!formStartTime) {
        throw new Error("Please select a start date and time.");
      }

      const res = await createClasses({
        title: formTitle,
        other_title: formTitle === "other" ? formOtherTitle.trim() : "",
        trainer_id: formTrainerId,
        start_time: new Date(formStartTime).toISOString(),
        duration_minutes: Number(formDuration),
        capacity: Number(formCapacity),
        repeat_weeks: Number(formRepeatWeeks),
      });

      setIsCreateOpen(false);
      setActionSuccess(res.message || "Class session(s) scheduled.");
      fetchClassesList();
    } catch (err: unknown) {
      setModalError(
        err instanceof Error ? err.message : "Failed to create class."
      );
    } finally {
      setModalSubmitting(false);
    }
  };

  // Handle Edit Class
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSession) return;
    setModalSubmitting(true);
    setModalError(null);
    try {
      if (formTitle === "other" && !formOtherTitle.trim()) {
        throw new Error("Custom title is required when title is Other.");
      }

      const res = await updateClass(editingSession.id, {
        title: formTitle,
        other_title: formTitle === "other" ? formOtherTitle.trim() : "",
        trainer_id: formTrainerId,
        start_time: new Date(formStartTime).toISOString(),
        duration_minutes: Number(formDuration),
        capacity: Number(formCapacity),
      });

      setEditingSession(null);
      setActionSuccess(res.message || "Class session updated.");
      fetchClassesList();
    } catch (err: unknown) {
      setModalError(
        err instanceof Error ? err.message : "Failed to update class."
      );
    } finally {
      setModalSubmitting(false);
    }
  };

  // Handle Cancel Class
  const handleCancelSubmit = async () => {
    if (!cancellingSession) return;
    setModalSubmitting(true);
    setModalError(null);
    try {
      const res = await cancelClass(cancellingSession.id);
      setCancellingSession(null);
      setActionSuccess(res.message || "Class session cancelled.");
      fetchClassesList();
    } catch (err: unknown) {
      setModalError(
        err instanceof Error ? err.message : "Failed to cancel class."
      );
    } finally {
      setModalSubmitting(false);
    }
  };

  // Handle Member Booking
  const handleBookSession = async (session: ClassSession) => {
    try {
      setSessionsError(null);
      const res = await bookClass(session.id);
      setActionSuccess(res.message || "Session booked successfully!");
      fetchClassesList();
      if (activeTab === "my-bookings") {
        fetchMemberBookings();
      }
    } catch (err: unknown) {
      setSessionsError(
        err instanceof Error ? err.message : "Failed to book class session."
      );
    }
  };

  // Handle Member Cancel Booking
  const handleCancelMemberBooking = async (
    sessionId: string,
    bookingId?: string
  ) => {
    try {
      setBookingsError(null);
      setSessionsError(null);
      const res = await cancelClassBooking(sessionId, bookingId);
      setActionSuccess(res.message || "Booking cancelled successfully.");
      if (activeTab === "my-bookings") {
        fetchMemberBookings();
      }
      fetchClassesList();
      if (rosterSession && rosterSession.id === sessionId) {
        const updatedRoster = await getClassRoster(sessionId);
        setRosterData(updatedRoster);
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to cancel booking.";
      if (activeTab === "my-bookings") {
        setBookingsError(msg);
      } else {
        setSessionsError(msg);
      }
    }
  };

  // Handle Attendance Toggle
  const handleToggleAttendance = async (
    sessionId: string,
    memberId: string,
    currentAttended: boolean
  ) => {
    try {
      await markClassAttendance(sessionId, {
        member_id: memberId,
        attended: !currentAttended,
      });
      // Refresh roster
      const updatedRoster = await getClassRoster(sessionId);
      setRosterData(updatedRoster);
    } catch (err: unknown) {
      setRosterError(
        err instanceof Error ? err.message : "Failed to mark attendance."
      );
    }
  };

  // Member search for staff booking
  useEffect(() => {
    if (!bookingForMemberSession || !memberSearchQuery.trim()) {
      setMemberSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearchingMembers(true);
      try {
        const results = await listGymMembers({
          search: memberSearchQuery.trim(),
        });
        setMemberSearchResults(results || []);
      } catch {
        setMemberSearchResults([]);
      } finally {
        setSearchingMembers(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [bookingForMemberSession, memberSearchQuery]);

  // Handle Staff Booking For Member
  const handleStaffBookForMember = async () => {
    if (!bookingForMemberSession || !selectedMember) return;
    setModalSubmitting(true);
    setModalError(null);
    try {
      const res = await bookClass(
        bookingForMemberSession.id,
        selectedMember.id
      );
      setBookingForMemberSession(null);
      setSelectedMember(null);
      setMemberSearchQuery("");
      setActionSuccess(res.message || "Member booked into class successfully.");
      fetchClassesList();
    } catch (err: unknown) {
      setModalError(
        err instanceof Error ? err.message : "Failed to book member into class."
      );
    } finally {
      setModalSubmitting(false);
    }
  };

  // Helper: check if attendance can be marked (start_time <= now <= end_time + 24 hours)
  const isAttendanceWindowOpen = (startIso: string, endIso: string) => {
    const now = Date.now();
    const start = new Date(startIso).getTime();
    const end = new Date(endIso).getTime();
    const windowEnd = end + 24 * 60 * 60 * 1000;
    return now >= start && now <= windowEnd;
  };

  // Helper: check if cancellation is within 2 hours
  const isWithinTwoHours = (startIso: string) => {
    const now = Date.now();
    const start = new Date(startIso).getTime();
    return start - now < 2 * 60 * 60 * 1000;
  };

  // Format date readable
  const formatSessionTime = (startIso: string, endIso: string) => {
    const start = new Date(startIso);
    const end = new Date(endIso);
    const dateStr = start.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    const startTimeStr = start.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
    const endTimeStr = end.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
    return `${dateStr}, ${startTimeStr} – ${endTimeStr}`;
  };

  // Filtered sessions
  const filteredSessions = useMemo(() => {
    return sessions.filter((session) => {
      if (dayFilter === "all") return true;
      const sessionDate = new Date(session.start_time);
      const today = new Date();
      if (dayFilter === "today") {
        return sessionDate.toDateString() === today.toDateString();
      }
      if (dayFilter === "tomorrow") {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        return sessionDate.toDateString() === tomorrow.toDateString();
      }
      if (dayFilter === "week") {
        const weekAhead = new Date();
        weekAhead.setDate(weekAhead.getDate() + 7);
        return sessionDate >= today && sessionDate <= weekAhead;
      }
      return true;
    });
  }, [sessions, dayFilter]);

  return (
    <div className="space-y-6" data-testid="class-schedule-section">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold text-text">
            {isTrainer ? "My Classes" : "Group Classes"}
          </h1>
          <p className="text-sm text-text-muted">
            {isTrainer
              ? "View your assigned class sessions and mark attendance."
              : isMember
                ? "Discover and book upcoming group fitness sessions."
                : "Schedule, manage, and track attendance for group classes."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isOwnerOrManager && (
            <Button
              variant="primary"
              size="md"
              onClick={handleOpenCreate}
              data-testid="btn-schedule-class"
            >
              + Schedule Class
            </Button>
          )}
        </div>
      </div>

      {/* Action success alert */}
      {actionSuccess && (
        <Alert
          variant="success"
          onClose={() => setActionSuccess(null)}
          data-testid="classes-success-alert"
        >
          {actionSuccess}
        </Alert>
      )}

      {/* Member Tabs */}
      {isMember && (
        <div className="flex border-b border-border">
          <button
            type="button"
            className={`py-2 px-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "schedule"
                ? "border-primary text-primary"
                : "border-transparent text-text-muted hover:text-text"
            }`}
            onClick={() => setActiveTab("schedule")}
            data-testid="tab-class-schedule"
          >
            Class Schedule
          </button>
          <button
            type="button"
            className={`py-2 px-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "my-bookings"
                ? "border-primary text-primary"
                : "border-transparent text-text-muted hover:text-text"
            }`}
            onClick={() => setActiveTab("my-bookings")}
            data-testid="tab-my-bookings"
          >
            My Bookings
          </button>
        </div>
      )}

      {/* SCHEDULE VIEW */}
      {activeTab === "schedule" && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <Card className="p-4 bg-surface border-border">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-text-muted mr-1">
                  Day:
                </span>
                <Button
                  size="sm"
                  variant={dayFilter === "all" ? "primary" : "ghost"}
                  onClick={() => setDayFilter("all")}
                >
                  All Days
                </Button>
                <Button
                  size="sm"
                  variant={dayFilter === "today" ? "primary" : "ghost"}
                  onClick={() => setDayFilter("today")}
                >
                  Today
                </Button>
                <Button
                  size="sm"
                  variant={dayFilter === "tomorrow" ? "primary" : "ghost"}
                  onClick={() => setDayFilter("tomorrow")}
                >
                  Tomorrow
                </Button>
                <Button
                  size="sm"
                  variant={dayFilter === "week" ? "primary" : "ghost"}
                  onClick={() => setDayFilter("week")}
                >
                  Next 7 Days
                </Button>
              </div>

              {!isTrainer && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-text-muted">
                    Status:
                  </span>
                  <select
                    className="bg-surface-2 border border-border rounded px-2.5 py-1 text-xs text-text focus:outline-none focus:border-primary"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="scheduled">Scheduled</option>
                    <option value="all">All (including cancelled)</option>
                  </select>
                </div>
              )}
            </div>
          </Card>

          {/* Session Error */}
          {sessionsError && (
            <Alert variant="danger" onClose={() => setSessionsError(null)}>
              {sessionsError}
            </Alert>
          )}

          {/* Loading */}
          {loadingSessions ? (
            <div className="p-12 flex justify-center">
              <Spinner size="md" />
            </div>
          ) : filteredSessions.length === 0 ? (
            <Card className="p-10 text-center space-y-3">
              <p className="text-base font-semibold text-text">
                No class sessions found.
              </p>
              <p className="text-xs text-text-muted max-w-sm mx-auto">
                {isOwnerOrManager
                  ? "Get started by scheduling group classes for your members."
                  : "Check back later for newly scheduled sessions."}
              </p>
              {isOwnerOrManager && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleOpenCreate}
                  className="mt-2"
                >
                  Schedule First Class
                </Button>
              )}
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredSessions.map((session) => {
                const isCancelled = session.status === "cancelled";
                const isPast = session.is_past;
                const isBookedByMe = !!session.user_booking;

                return (
                  <Card
                    key={session.id}
                    className={`p-5 flex flex-col justify-between space-y-4 border transition-shadow hover:shadow-md ${
                      isCancelled
                        ? "border-danger/30 bg-danger/5 opacity-80"
                        : "border-border bg-surface"
                    }`}
                    data-testid={`class-card-${session.id}`}
                  >
                    {/* Top Row: Title, Badge */}
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-bold text-lg text-text">
                          {session.display_title}
                        </h3>
                        {isCancelled ? (
                          <Badge variant="danger">Cancelled</Badge>
                        ) : isPast ? (
                          <Badge variant="neutral">Completed</Badge>
                        ) : session.is_full ? (
                          <Badge variant="warning">Full</Badge>
                        ) : (
                          <Badge variant="success">Open</Badge>
                        )}
                      </div>

                      {/* Time & Duration */}
                      <p className="text-xs text-text-muted font-medium">
                        ⏱️{" "}
                        {formatSessionTime(
                          session.start_time,
                          session.end_time
                        )}{" "}
                        ({session.duration_minutes} min)
                      </p>
                    </div>

                    {/* Trainer & Capacity Details */}
                    <div className="p-3 bg-surface-2/60 rounded-lg space-y-2 text-xs">
                      <div className="flex items-center gap-2.5">
                        {session.trainer_photo_url ? (
                          <img
                            src={session.trainer_photo_url}
                            alt={session.trainer_name}
                            className="w-7 h-7 rounded-full object-cover border border-border"
                          />
                        ) : (
                          <div className="w-7 h-7 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-xs">
                            {session.trainer_name.charAt(0).toUpperCase()}
                          </div>
                        )}
                        <div>
                          <span className="text-[10px] uppercase font-bold text-text-muted block">
                            Trainer
                          </span>
                          <span className="font-semibold text-text">
                            {session.trainer_name}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[11px]">
                        <span className="text-text-muted">Attendance:</span>
                        <span className="font-semibold text-text">
                          {session.booked_count} / {session.capacity} spots
                          booked
                          {!session.is_full && !isCancelled && !isPast && (
                            <span className="text-primary font-normal ml-1">
                              ({session.spots_remaining} left)
                            </span>
                          )}
                        </span>
                      </div>
                    </div>

                    {/* Actions based on role */}
                    <div className="pt-2 border-t border-border flex flex-wrap items-center justify-between gap-2">
                      {/* Owner & Manager Actions */}
                      {isOwnerOrManager && (
                        <>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => openRosterModal(session)}
                            data-testid={`btn-roster-${session.id}`}
                          >
                            Roster ({session.booked_count})
                          </Button>
                          <div className="flex items-center gap-1.5">
                            {!isPast && !isCancelled && (
                              <>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleOpenEdit(session)}
                                  data-testid={`btn-edit-${session.id}`}
                                >
                                  Edit
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="text-danger hover:text-danger-hover"
                                  onClick={() => setCancellingSession(session)}
                                  data-testid={`btn-cancel-${session.id}`}
                                >
                                  Cancel
                                </Button>
                              </>
                            )}
                          </div>
                        </>
                      )}

                      {/* Trainer Actions */}
                      {isTrainer && (
                        <Button
                          size="sm"
                          variant="primary"
                          className="w-full"
                          onClick={() => openRosterModal(session)}
                          data-testid={`btn-trainer-roster-${session.id}`}
                        >
                          View Roster & Attendance ({session.booked_count})
                        </Button>
                      )}

                      {/* Reception Actions */}
                      {isReception && (
                        <>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => openRosterModal(session)}
                            data-testid={`btn-reception-roster-${session.id}`}
                          >
                            Roster ({session.booked_count})
                          </Button>
                          {!isPast && !isCancelled && (
                            <Button
                              size="sm"
                              variant="primary"
                              disabled={session.is_full}
                              onClick={() => {
                                setBookingForMemberSession(session);
                                setSelectedMember(null);
                                setMemberSearchQuery("");
                                setModalError(null);
                              }}
                              data-testid={`btn-reception-book-${session.id}`}
                            >
                              {session.is_full ? "Class Full" : "Book Member"}
                            </Button>
                          )}
                        </>
                      )}

                      {/* Member Actions */}
                      {isMember && (
                        <div className="w-full">
                          {isCancelled ? (
                            <span className="text-xs text-danger font-medium">
                              Session cancelled
                            </span>
                          ) : isPast ? (
                            <span className="text-xs text-text-muted">
                              Session finished
                            </span>
                          ) : isBookedByMe ? (
                            <div className="flex items-center justify-between w-full">
                              <Badge variant="success">✓ Booked</Badge>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-xs text-danger hover:text-danger-hover"
                                onClick={() =>
                                  handleCancelMemberBooking(session.id)
                                }
                                disabled={isWithinTwoHours(session.start_time)}
                                title={
                                  isWithinTwoHours(session.start_time)
                                    ? "Bookings can only be cancelled up to 2 hours before the class begins"
                                    : "Cancel booking"
                                }
                                data-testid={`btn-cancel-my-booking-${session.id}`}
                              >
                                Cancel Booking
                              </Button>
                            </div>
                          ) : session.is_full ? (
                            <Button
                              size="sm"
                              variant="secondary"
                              disabled
                              className="w-full"
                            >
                              Class Full
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="primary"
                              className="w-full"
                              onClick={() => handleBookSession(session)}
                              data-testid={`btn-member-book-${session.id}`}
                            >
                              Book Class
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* MEMBER MY BOOKINGS VIEW */}
      {isMember && activeTab === "my-bookings" && (
        <div className="space-y-4">
          {bookingsError && (
            <Alert variant="danger" onClose={() => setBookingsError(null)}>
              {bookingsError}
            </Alert>
          )}

          {loadingBookings ? (
            <div className="p-12 flex justify-center">
              <Spinner size="md" />
            </div>
          ) : myBookings.length === 0 ? (
            <Card className="p-10 text-center space-y-3">
              <p className="text-base font-semibold text-text">
                You haven't booked any classes yet.
              </p>
              <p className="text-xs text-text-muted max-w-sm mx-auto">
                Explore our upcoming group classes and reserve your spot!
              </p>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setActiveTab("schedule")}
                className="mt-2"
              >
                Browse Schedule
              </Button>
            </Card>
          ) : (
            <div className="space-y-3">
              {myBookings.map((booking) => {
                const isWithin2h = isWithinTwoHours(booking.session_start_time);
                const isCancelled =
                  booking.status === "cancelled" ||
                  booking.session_status === "cancelled";
                const isPast =
                  new Date(booking.session_end_time).getTime() < Date.now();

                return (
                  <Card
                    key={booking.id}
                    className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border border-border bg-surface"
                    data-testid={`booking-card-${booking.id}`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-base text-text">
                          {booking.session_title}
                        </h4>
                        {isCancelled ? (
                          <Badge variant="danger">Cancelled</Badge>
                        ) : booking.attended ? (
                          <Badge variant="success">Attended</Badge>
                        ) : isPast ? (
                          <Badge variant="neutral">Missed</Badge>
                        ) : (
                          <Badge variant="primary">Upcoming</Badge>
                        )}
                      </div>
                      <p className="text-xs text-text-muted">
                        ⏱️{" "}
                        {formatSessionTime(
                          booking.session_start_time,
                          booking.session_end_time
                        )}{" "}
                        • Trainer: {booking.trainer_name}
                      </p>
                    </div>

                    <div>
                      {!isCancelled && !isPast && (
                        <div className="flex flex-col items-end gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-xs text-danger hover:text-danger-hover"
                            disabled={isWithin2h}
                            onClick={() =>
                              handleCancelMemberBooking(
                                booking.session,
                                booking.id
                              )
                            }
                            data-testid={`btn-cancel-booking-tab-${booking.id}`}
                          >
                            Cancel Booking
                          </Button>
                          {isWithin2h && (
                            <span className="text-[11px] text-text-muted">
                              Bookings can only be cancelled up to 2 hours
                              before the class begins.
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* CREATE CLASS MODAL (Owner/Manager) */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Schedule Group Class"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Class Title *
            </label>
            <select
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value as ClassTitle)}
              data-testid="select-class-title"
            >
              {CLASS_TITLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {formTitle === "other" && (
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Custom Title * (max 50 characters)
              </label>
              <Input
                required
                maxLength={50}
                placeholder="e.g. Pilates Flow"
                value={formOtherTitle}
                onChange={(e) => setFormOtherTitle(e.target.value)}
                data-testid="input-other-title"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Assigned Trainer *
            </label>
            <select
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              value={formTrainerId}
              onChange={(e) => setFormTrainerId(e.target.value)}
              required
              data-testid="select-class-trainer"
            >
              {trainers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.user.full_name || t.user.email}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Start Date & Time *
              </label>
              <Input
                type="datetime-local"
                required
                value={formStartTime}
                onChange={(e) => setFormStartTime(e.target.value)}
                data-testid="input-class-start-time"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Duration *
              </label>
              <select
                className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                value={formDuration}
                onChange={(e) => setFormDuration(Number(e.target.value))}
                data-testid="select-class-duration"
              >
                {CLASS_DURATION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Capacity * (1 - 200)
              </label>
              <Input
                type="number"
                min={1}
                max={200}
                required
                value={formCapacity}
                onChange={(e) => setFormCapacity(Number(e.target.value))}
                data-testid="input-class-capacity"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Repeat weekly for N weeks (1 - 12)
              </label>
              <Input
                type="number"
                min={1}
                max={12}
                value={formRepeatWeeks}
                onChange={(e) => setFormRepeatWeeks(Number(e.target.value))}
                data-testid="input-repeat-weeks"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={modalSubmitting}
              data-testid="btn-submit-create-class"
            >
              {modalSubmitting ? "Scheduling..." : "Schedule Class"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* EDIT CLASS MODAL (Owner/Manager) */}
      <Modal
        isOpen={!!editingSession}
        onClose={() => setEditingSession(null)}
        title="Edit Class Session"
      >
        <form onSubmit={handleEditSubmit} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}

          <Alert variant="warning">
            Modifying class time or trainer will notify all booked members
            in-app.
          </Alert>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Class Title *
            </label>
            <select
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value as ClassTitle)}
              data-testid="edit-class-title"
            >
              {CLASS_TITLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {formTitle === "other" && (
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Custom Title * (max 50 characters)
              </label>
              <Input
                required
                maxLength={50}
                placeholder="e.g. Pilates Flow"
                value={formOtherTitle}
                onChange={(e) => setFormOtherTitle(e.target.value)}
                data-testid="edit-other-title"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Assigned Trainer *
            </label>
            <select
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              value={formTrainerId}
              onChange={(e) => setFormTrainerId(e.target.value)}
              required
              data-testid="edit-class-trainer"
            >
              {trainers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.user.full_name || t.user.email}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Start Date & Time *
              </label>
              <Input
                type="datetime-local"
                required
                value={formStartTime}
                onChange={(e) => setFormStartTime(e.target.value)}
                data-testid="edit-class-start-time"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Duration *
              </label>
              <select
                className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                value={formDuration}
                onChange={(e) => setFormDuration(Number(e.target.value))}
                data-testid="edit-class-duration"
              >
                {CLASS_DURATION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Capacity * (1 - 200)
            </label>
            <Input
              type="number"
              min={1}
              max={200}
              required
              value={formCapacity}
              onChange={(e) => setFormCapacity(Number(e.target.value))}
              data-testid="edit-class-capacity"
            />
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setEditingSession(null)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={modalSubmitting}
              data-testid="btn-submit-edit-class"
            >
              {modalSubmitting ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* CANCEL CLASS MODAL (Owner/Manager) */}
      <Modal
        isOpen={!!cancellingSession}
        onClose={() => setCancellingSession(null)}
        title="Cancel Class Session"
      >
        <div className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}

          <div className="p-3 bg-surface-2/60 border border-border rounded-lg text-xs space-y-1">
            <div className="flex justify-between">
              <span className="text-text-muted">Class:</span>
              <span className="font-semibold text-text">
                {cancellingSession?.display_title}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Time:</span>
              <span className="text-text">
                {cancellingSession &&
                  formatSessionTime(
                    cancellingSession.start_time,
                    cancellingSession.end_time
                  )}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Booked Members:</span>
              <span className="font-semibold text-text">
                {cancellingSession?.booked_count}
              </span>
            </div>
          </div>

          <Alert variant="danger">
            Cancelling will mark this session as Cancelled and send in-app
            notifications to all booked members.
          </Alert>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setCancellingSession(null)}
            >
              Keep Session
            </Button>
            <Button
              type="button"
              variant="primary"
              className="bg-danger hover:bg-danger-hover text-white border-transparent"
              disabled={modalSubmitting}
              onClick={handleCancelSubmit}
              data-testid="btn-confirm-cancel-class"
            >
              {modalSubmitting ? "Cancelling..." : "Confirm Cancellation"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ROSTER & ATTENDANCE MODAL (Owner, Manager, Trainer, Reception) */}
      <Modal
        isOpen={!!rosterSession}
        onClose={() => {
          setRosterSession(null);
          setRosterData(null);
        }}
        title={`Roster — ${rosterSession?.display_title || "Class"}`}
      >
        <div className="space-y-4">
          {rosterError && <Alert variant="danger">{rosterError}</Alert>}

          {rosterSession && (
            <div className="p-3 bg-surface-2/60 border border-border rounded-lg text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-text-muted">Schedule:</span>
                <span className="font-medium text-text">
                  {formatSessionTime(
                    rosterSession.start_time,
                    rosterSession.end_time
                  )}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Trainer:</span>
                <span className="font-medium text-text">
                  {rosterSession.trainer_name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Capacity:</span>
                <span className="font-medium text-text">
                  {rosterSession.booked_count} / {rosterSession.capacity} booked
                </span>
              </div>
            </div>
          )}

          {canMarkAttendance && rosterSession && (
            <p className="text-[11px] text-text-muted">
              {isAttendanceWindowOpen(
                rosterSession.start_time,
                rosterSession.end_time
              )
                ? "Attendance window is open. Toggle attendance for members below."
                : "Attendance can be marked starting from class start time up to 24 hours after class end."}
            </p>
          )}

          {loadingRoster ? (
            <div className="p-8 flex justify-center">
              <Spinner size="md" />
            </div>
          ) : !rosterData || rosterData.bookings.length === 0 ? (
            <p className="text-xs text-text-muted text-center py-6">
              No members are currently booked for this session.
            </p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {rosterData.bookings.map((booking) => {
                const canToggle =
                  canMarkAttendance &&
                  rosterSession &&
                  isAttendanceWindowOpen(
                    rosterSession.start_time,
                    rosterSession.end_time
                  );

                return (
                  <div
                    key={booking.id}
                    className="p-3 bg-surface border border-border rounded-lg flex items-center justify-between gap-3 text-xs"
                    data-testid={`roster-row-${booking.id}`}
                  >
                    <div>
                      <span className="font-bold text-text block">
                        {booking.member.full_name}
                      </span>
                      <span className="text-text-muted block text-[11px]">
                        📞 {booking.member.phone} • Status:{" "}
                        {booking.member.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      {/* Attendance Toggle */}
                      {canMarkAttendance && (
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={booking.attended}
                            disabled={!canToggle}
                            onChange={() =>
                              handleToggleAttendance(
                                rosterSession!.id,
                                booking.member.id,
                                booking.attended
                              )
                            }
                            className="rounded border-border text-primary focus:ring-primary w-4 h-4 cursor-pointer disabled:cursor-not-allowed"
                            data-testid={`checkbox-attendance-${booking.id}`}
                          />
                          <span
                            className={`text-xs font-semibold ${
                              booking.attended
                                ? "text-emerald-500"
                                : "text-text-muted"
                            }`}
                          >
                            {booking.attended ? "Attended" : "Not Attended"}
                          </span>
                        </label>
                      )}

                      {/* Staff Cancellation Action */}
                      {(isOwnerOrManager || isReception) &&
                        rosterSession &&
                        !rosterSession.is_past &&
                        rosterSession.status !== "cancelled" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-[11px] text-danger hover:text-danger-hover py-0.5 px-1.5"
                            onClick={() =>
                              handleCancelMemberBooking(
                                rosterSession.id,
                                booking.id
                              )
                            }
                            data-testid={`btn-staff-cancel-booking-${booking.id}`}
                          >
                            Remove
                          </Button>
                        )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex justify-end pt-3 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setRosterSession(null);
                setRosterData(null);
              }}
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* BOOK FOR MEMBER MODAL (Reception / Staff) */}
      <Modal
        isOpen={!!bookingForMemberSession}
        onClose={() => {
          setBookingForMemberSession(null);
          setSelectedMember(null);
          setMemberSearchQuery("");
        }}
        title={`Book Member — ${bookingForMemberSession?.display_title || ""}`}
      >
        <div className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}

          {bookingForMemberSession && (
            <div className="p-3 bg-surface-2/60 border border-border rounded-lg text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-text-muted">Schedule:</span>
                <span className="font-medium text-text">
                  {formatSessionTime(
                    bookingForMemberSession.start_time,
                    bookingForMemberSession.end_time
                  )}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Available:</span>
                <span className="font-semibold text-primary">
                  {bookingForMemberSession.spots_remaining} spots remaining
                </span>
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Search Member (by name or phone) *
            </label>
            <Input
              placeholder="e.g. Abebe or 0911..."
              value={memberSearchQuery}
              onChange={(e) => setMemberSearchQuery(e.target.value)}
              data-testid="input-search-member-for-class"
            />
          </div>

          {searchingMembers ? (
            <div className="p-4 flex justify-center">
              <Spinner size="sm" />
            </div>
          ) : memberSearchResults.length > 0 ? (
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {memberSearchResults.map((m) => {
                const isSelected = selectedMember?.id === m.id;
                return (
                  <div
                    key={m.id}
                    onClick={() => setSelectedMember(m)}
                    className={`p-2.5 rounded-lg border cursor-pointer text-xs flex items-center justify-between transition-colors ${
                      isSelected
                        ? "border-primary bg-primary/10"
                        : "border-border hover:bg-surface-2"
                    }`}
                    data-testid={`member-search-row-${m.id}`}
                  >
                    <div>
                      <span className="font-semibold text-text block">
                        {m.full_name}
                      </span>
                      <span className="text-text-muted block text-[11px]">
                        📞 {m.phone}
                      </span>
                    </div>
                    <Badge
                      variant={m.status === "active" ? "success" : "warning"}
                    >
                      {m.status}
                    </Badge>
                  </div>
                );
              })}
            </div>
          ) : memberSearchQuery.trim() ? (
            <p className="text-xs text-text-muted text-center py-2">
              No matching members found.
            </p>
          ) : null}

          {selectedMember && (
            <div className="p-2.5 bg-primary/5 border border-primary/30 rounded-lg text-xs">
              Selected:{" "}
              <strong className="text-text">{selectedMember.full_name}</strong>{" "}
              (Status: {selectedMember.status})
            </div>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setBookingForMemberSession(null);
                setSelectedMember(null);
                setMemberSearchQuery("");
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={!selectedMember || modalSubmitting}
              onClick={handleStaffBookForMember}
              data-testid="btn-confirm-staff-booking"
            >
              {modalSubmitting ? "Booking..." : "Confirm Booking"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
