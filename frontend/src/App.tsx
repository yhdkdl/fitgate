import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Database,
  Server,
  Layers,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import type { components } from "./types/api";

type HealthResponse = components["schemas"]["HealthCheckResponse"];

async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health/");
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}

export const App: React.FC = () => {
  const {
    data: health,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: 2,
    refetchInterval: 10000,
  });

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="logo-group">
          <div className="logo-badge">FG</div>
          <div>
            <div className="brand-title">FitGate</div>
            <div className="brand-tagline">
              Ethiopian Gym Management Platform
            </div>
          </div>
        </div>
        <div className="status-chip">
          <span className="pulse-dot" />
          <span>Sprint 0 • Scaffolding Active</span>
        </div>
      </header>

      {/* Hero */}
      <section className="hero">
        <h1>Multi-Tenant Platform Foundation</h1>
        <p>
          Sprint 0 operational baseline. Local development environment running
          Django REST Framework, React (Vite), PostgreSQL, Redis, and pgAdmin.
        </p>
      </section>

      {/* Stack & Service Grid */}
      <div className="grid">
        {/* Backend Status Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-icon">
              <Server size={20} />
            </div>
            <h2>Backend API Status</h2>
          </div>
          <p>
            Django 5.x REST Framework service connected via Vite development
            proxy.
          </p>
          <div className="service-list">
            <div className="service-item">
              <span>API Health Check</span>
              {isLoading && <span className="status-badge">Checking...</span>}
              {isError && (
                <span
                  className="status-badge"
                  style={{
                    background: "rgba(239, 68, 68, 0.15)",
                    color: "#f87171",
                  }}
                  title={(error as Error).message}
                >
                  Offline / Connecting
                </span>
              )}
              {health && (
                <span className="status-badge active">
                  {health.status.toUpperCase()} ({health.app})
                </span>
              )}
            </div>
            <div className="service-item">
              <span>OpenAPI Documentation</span>
              <a
                href="http://localhost:8000/api/docs/"
                target="_blank"
                rel="noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  color: "#34d399",
                  textDecoration: "none",
                  fontSize: "0.8rem",
                }}
              >
                Swagger UI <ExternalLink size={12} />
              </a>
            </div>
            <div className="service-item">
              <span>Settings Module</span>
              <span className="status-badge active">
                fitgate.settings.local
              </span>
            </div>
          </div>
        </div>

        {/* Database & Infrastructure */}
        <div className="card">
          <div className="card-header">
            <div className="card-icon">
              <Database size={20} />
            </div>
            <h2>Infrastructure & Storage</h2>
          </div>
          <p>Containerized local data stores with isolated pgAdmin client.</p>
          <div className="service-list">
            <div className="service-item">
              <span>PostgreSQL 16</span>
              <span className="status-badge active">Port 5432 (Healthy)</span>
            </div>
            <div className="service-item">
              <span>Redis 7 Cache</span>
              <span className="status-badge active">Port 6379 (Healthy)</span>
            </div>
            <div className="service-item">
              <span>pgAdmin (Dev GUI)</span>
              <a
                href="http://localhost:5050"
                target="_blank"
                rel="noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  color: "#34d399",
                  textDecoration: "none",
                  fontSize: "0.8rem",
                }}
              >
                Port 5050 <ExternalLink size={12} />
              </a>
            </div>
          </div>
        </div>

        {/* Architecture & Tenancy Foundation */}
        <div className="card">
          <div className="card-header">
            <div className="card-icon">
              <Layers size={20} />
            </div>
            <h2>Architecture Highlights</h2>
          </div>
          <p>Core design principles enforced across increments.</p>
          <div className="service-list">
            <div className="service-item">
              <span>Tenancy Boundary</span>
              <span style={{ color: "#94a3b8" }}>Row-level (gym_id)</span>
            </div>
            <div className="service-item">
              <span>Subdomain Resolution</span>
              <span style={{ color: "#94a3b8" }}>{`{gym}.DOMAIN`}</span>
            </div>
            <div className="service-item">
              <span>Deployment Target</span>
              <span style={{ color: "#94a3b8" }}>Yegara Host (cPanel)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sprint 0 Definition of Done Checklist Preview */}
      <div className="card" style={{ marginBottom: "3rem" }}>
        <div className="card-header">
          <div className="card-icon">
            <Activity size={20} />
          </div>
          <h2>Sprint 0 Scaffolding Checklist</h2>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "1rem",
          }}
        >
          {[
            "Docker Compose (Django, Postgres, Redis, pgAdmin)",
            "Settings Split (base, local, prod)",
            "Pytest-django harness runnable",
            "drf-spectacular OpenAPI + TypeScript types",
            "Pre-commit hooks (ruff, black, eslint, prettier)",
            "Automated pgAdmin Postgres pre-connection",
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                fontSize: "0.9rem",
                color: "#cbd5e1",
              }}
            >
              <CheckCircle2 size={16} color="#10b981" />
              <span>{item}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <footer className="footer">
        <p>FitGate • Designed for Ethiopian Fitness Communities • Sprint 0</p>
      </footer>
    </div>
  );
};

export default App;
