import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LandingScreen } from "../screens/LandingScreen";
import { App } from "../App";
import * as tenantUtils from "../utils/tenant";

describe("Sprint 4d: Public Platform Landing Page", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();

    // Mock window.location
    Object.defineProperty(window, "location", {
      value: {
        ...originalLocation,
        hostname: "localhost",
        port: "5173",
        protocol: "http:",
        assign: vi.fn(),
      },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  describe("Subdomain and URL Utility Functions", () => {
    it("validates subdomains according to single DNS label rules and rejects reserved names", () => {
      // Valid subdomains
      expect(tenantUtils.validateSubdomain("bolehub").valid).toBe(true);
      expect(tenantUtils.validateSubdomain("fit-zone-addis").valid).toBe(true);
      expect(tenantUtils.validateSubdomain("gym123").valid).toBe(true);

      // Invalid subdomains
      expect(tenantUtils.validateSubdomain("").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("   ").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("Bole Hub").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("gym!").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("-leadinghyphen").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("trailinghyphen-").valid).toBe(
        false
      );

      // Reserved subdomains
      expect(tenantUtils.validateSubdomain("api").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("admin").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("www").valid).toBe(false);
      expect(tenantUtils.validateSubdomain("localhost").valid).toBe(false);
    });

    it("dynamically constructs tenant URLs on localhost and production without hardcoding", () => {
      // On localhost dev with port 5173
      const localUrl = tenantUtils.buildTenantUrl(
        "bolehub",
        "localhost",
        "http:",
        "5173"
      );
      expect(localUrl).toBe("http://bolehub.localhost:5173/");

      // On localhost without port
      const localNoPortUrl = tenantUtils.buildTenantUrl(
        "bolehub",
        "localhost",
        "http:",
        ""
      );
      expect(localNoPortUrl).toBe("http://bolehub.localhost/");

      // On production apex (fitgate.tebebtech.com)
      const prodUrl = tenantUtils.buildTenantUrl(
        "bolehub",
        "fitgate.tebebtech.com",
        "https:",
        ""
      );
      expect(prodUrl).toBe("https://bolehub.fitgate.tebebtech.com/");

      // On alternative apex (fitgate.org)
      const altProdUrl = tenantUtils.buildTenantUrl(
        "bolehub",
        "fitgate.org",
        "https:",
        ""
      );
      expect(altProdUrl).toBe("https://bolehub.fitgate.org/");

      // On apex with www prefix
      const wwwUrl = tenantUtils.buildTenantUrl(
        "bolehub",
        "www.fitgate.org",
        "https:",
        ""
      );
      expect(wwwUrl).toBe("https://bolehub.fitgate.org/");
    });
  });

  describe("LandingScreen Component", () => {
    it("renders page header, title, and SEO meta tags without requiring login", () => {
      render(
        <MemoryRouter>
          <LandingScreen />
        </MemoryRouter>
      );

      // Brand logo and title
      expect(
        screen.getByRole("heading", {
          name: /the modern all-in-one operating system for gyms/i,
        })
      ).toBeInTheDocument();

      // Navigation links in nav bar
      const nav = screen.getByRole("navigation", {
        name: /platform navigation/i,
      });
      expect(
        within(nav).getByRole("link", { name: /^features$/i })
      ).toHaveAttribute("href", "#features");
      expect(
        within(nav).getByRole("link", { name: /^how it works$/i })
      ).toHaveAttribute("href", "#how-it-works");
      expect(
        within(nav).getByRole("link", { name: /^pricing$/i })
      ).toHaveAttribute("href", "#pricing");
      expect(
        within(nav).getByRole("link", { name: /^go to my gym$/i })
      ).toHaveAttribute("href", "#find-gym");

      // Document title and SEO description
      expect(document.title).toBe("FitGate — All-in-One Gym Operating System");
      const meta = document.querySelector('meta[name="description"]');
      expect(meta?.getAttribute("content")).toContain(
        "all-in-one gym management operating system"
      );
    });

    it("explains core features using only SPEC §1 & §3 features", () => {
      render(
        <MemoryRouter>
          <LandingScreen />
        </MemoryRouter>
      );

      expect(
        screen.getByRole("heading", { name: /membership management/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /qr check-in & attendance/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /trainer tools & body metrics/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /ai personal training plans/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /online & manual payments/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /multi-branch gym networks/i })
      ).toBeInTheDocument();
    });

    it("displays the three tiers with transparent yearly pricing and feature checklists", () => {
      render(
        <MemoryRouter>
          <LandingScreen />
        </MemoryRouter>
      );

      // 3 Tiers present
      expect(
        screen.getByRole("heading", { name: /^starter$/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /^growth$/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /^pro$/i })
      ).toBeInTheDocument();

      // Yearly pricing displayed
      expect(screen.getByText("12,000")).toBeInTheDocument();
      expect(screen.getByText("30,000")).toBeInTheDocument();
      expect(screen.getByText("60,000")).toBeInTheDocument();

      // Each pricing card has a Request a Demo link
      const demoLinks = screen.getAllByRole("link", {
        name: /request a demo/i,
      });
      expect(demoLinks.length).toBeGreaterThanOrEqual(4); // header + hero + 3 cards
      demoLinks.forEach((link) => {
        expect(link).toHaveAttribute("href", "/request-demo");
      });
    });

    it("displays the three-step 'How It Works' section", () => {
      render(
        <MemoryRouter>
          <LandingScreen />
        </MemoryRouter>
      );

      expect(
        screen.getByRole("heading", { name: /how it works/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /^request a demo$/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /^setup after payment$/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", {
          name: /^your gym gets its own address$/i,
        })
      ).toBeInTheDocument();
    });

    it("handles the 'Go to my gym' box with input validation and dynamic redirection", async () => {
      const user = userEvent.setup();

      render(
        <MemoryRouter>
          <LandingScreen />
        </MemoryRouter>
      );

      const input = screen.getByLabelText(/gym subdomain/i);
      const submitButton = screen.getByRole("button", {
        name: /go to gym/i,
      });

      // 1. Submit invalid subdomain
      await user.clear(input);
      await user.type(input, "my invalid gym!");
      await user.click(submitButton);

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Please enter a valid gym subdomain (letters, numbers, and hyphens only)."
      );
      expect(window.location.assign).not.toHaveBeenCalled();

      // 2. Submit valid subdomain
      await user.clear(input);
      await user.type(input, "bolehub");
      await user.click(submitButton);

      expect(window.location.assign).toHaveBeenCalledWith(
        "http://bolehub.localhost:5173/"
      );
    });

    it("includes a discreet 'Platform sign in' link in the footer pointing to /login", () => {
      render(
        <MemoryRouter>
          <LandingScreen />
        </MemoryRouter>
      );

      const superAdminLink = screen.getByRole("link", {
        name: /platform sign in/i,
      });
      expect(superAdminLink).toBeInTheDocument();
      expect(superAdminLink).toHaveAttribute("href", "/login");
    });
  });

  describe("Root Routing Behavior (Apex vs Tenant Subdomain)", () => {
    it("renders LandingScreen at the root path when at the platform apex (tenant is null)", async () => {
      vi.spyOn(tenantUtils, "getTenantFromHostname").mockReturnValue(null);

      render(
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      );

      expect(
        await screen.findByRole("heading", {
          name: /the modern all-in-one operating system for gyms/i,
        })
      ).toBeInTheDocument();
    });

    it("renders GymEntryScreen at the root path when on a gym tenant subdomain", async () => {
      vi.spyOn(tenantUtils, "getTenantFromHostname").mockReturnValue("bolehub");

      // Mock getPublicGymEntry API call made by GymEntryScreen (/api/public/gym-entry/)
      vi.spyOn(global, "fetch").mockImplementation(async (url) => {
        const u = String(url);
        if (u.includes("/api/public/gym-entry/")) {
          return new Response(
            JSON.stringify({
              name: "FitGate Bole Hub",
              subdomain: "bolehub",
              phone: "0911000000",
              location: "Bole Medhanialem",
              brand_color: "#2563EB",
              plans: [],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("Not found", { status: 404 });
      });

      render(
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      );

      // Verify that GymEntryScreen rendered (showing gym details)
      const matching = await screen.findAllByText(/fitgate bole hub/i);
      expect(matching.length).toBeGreaterThanOrEqual(1);
    });
  });
});
