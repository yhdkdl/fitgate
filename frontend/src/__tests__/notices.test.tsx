import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { NoticeBoardSection } from "../components/notices/NoticeBoardSection";
import { MemberNoticesCard } from "../components/member/MemberNoticesCard";
import * as noticesApi from "../api/notices";
import type { GymNotice } from "../types/notice";

vi.mock("../api/notices");

const mockNotices: GymNotice[] = [
  {
    id: "notice-1",
    title: "Holiday Schedule Update",
    body: "The gym will remain open with modified hours this coming weekend.",
    posted_by: "user-owner",
    posted_by_name: "Owner Abebe",
    created_at: "2026-11-02T10:00:00Z",
    updated_at: "2026-11-02T10:00:00Z",
  },
  {
    id: "notice-2",
    title: "New Weightlifting Barbells",
    body: "Five new Olympic power barbells have arrived in the free weight area.",
    posted_by: "user-mgr",
    posted_by_name: "Manager Sara",
    created_at: "2026-11-01T15:30:00Z",
    updated_at: "2026-11-01T15:30:00Z",
  },
];

describe("Sprint 28: NoticeBoardSection and MemberNoticesCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(noticesApi, "listNotices").mockResolvedValue(mockNotices);
  });

  it("renders notice board for member without post or delete controls", async () => {
    render(
      <MemoryRouter>
        <NoticeBoardSection userRole="member" />
      </MemoryRouter>
    );

    expect(await screen.findByText("Notice Board")).toBeInTheDocument();
    expect(
      await screen.findByText("Holiday Schedule Update")
    ).toBeInTheDocument();
    expect(screen.getByText("New Weightlifting Barbells")).toBeInTheDocument();
    expect(screen.getByText(/Owner Abebe/i)).toBeInTheDocument();

    // Member should NOT see post or delete buttons
    expect(
      screen.queryByRole("button", { name: /Post Notice/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Delete/i })
    ).not.toBeInTheDocument();
  });

  it("allows owner to open post modal, publish notice, and view Telegram broadcast status", async () => {
    vi.spyOn(noticesApi, "createNotice").mockResolvedValue({
      id: "notice-new",
      title: "Saturday Calisthenics Workshop",
      body: "Free bodyweight masterclass with coach Dawit at 9:00 AM.",
      posted_by: "user-owner",
      posted_by_name: "Owner Abebe",
      created_at: "2026-11-02T12:00:00Z",
      updated_at: "2026-11-02T12:00:00Z",
      telegram_sent: true,
      telegram_note: "Broadcast recorded via development mock sender.",
    });

    render(
      <MemoryRouter>
        <NoticeBoardSection userRole="owner" />
      </MemoryRouter>
    );

    expect(await screen.findByText("Notice Board")).toBeInTheDocument();
    const postBtn = screen.getByRole("button", { name: /Post Notice/i });
    expect(postBtn).toBeInTheDocument();

    fireEvent.click(postBtn);

    // Modal is open
    expect(
      await screen.findByText("Post Notice Announcement")
    ).toBeInTheDocument();

    const titleInput = screen.getByPlaceholderText(/Holiday Hours/i);
    const bodyInput = screen.getByPlaceholderText(
      /Write announcement details/i
    );

    fireEvent.change(titleInput, {
      target: { value: "Saturday Calisthenics Workshop" },
    });
    fireEvent.change(bodyInput, {
      target: {
        value: "Free bodyweight masterclass with coach Dawit at 9:00 AM.",
      },
    });

    const publishBtn = screen.getByRole("button", { name: /Publish Notice/i });
    fireEvent.click(publishBtn);

    await waitFor(() => {
      expect(noticesApi.createNotice).toHaveBeenCalledWith({
        title: "Saturday Calisthenics Workshop",
        body: "Free bodyweight masterclass with coach Dawit at 9:00 AM.",
      });
    });

    expect(
      await screen.findByText(
        /Notice published in-app and broadcast to Telegram channel/i
      )
    ).toBeInTheDocument();
  });

  it("renders member latest announcement card on Member Home", async () => {
    render(
      <MemoryRouter>
        <MemberNoticesCard />
      </MemoryRouter>
    );

    expect(await screen.findByText("Latest Announcement")).toBeInTheDocument();
    expect(screen.getByText("Holiday Schedule Update")).toBeInTheDocument();
    expect(screen.getByText(/View all notices →/i)).toBeInTheDocument();
  });
});
