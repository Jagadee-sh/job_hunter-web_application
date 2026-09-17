import { StrictMode, useState, useEffect, useRef, type ChangeEvent, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Job = {
  id: string;
  title: string;
  company: string;
  location: string;
  application_url: string;
  source: string;
  description: string;
  fit_score?: number;
  matched_skills?: string[];
  rationale?: string;
  tailored_resume?: string;
  status?: string;
  reason?: string;
};

type Profile = {
  name: string;
  email: string;
  phone: string;
  target_roles: string;
  locations: string;
  resume_path: string;
};

type PortalSession = {
  open: boolean;
  logged_in: boolean;
  user_name?: string;
  message?: string;
};

type HunterStats = {
  jobs_found: number;
  jobs_scored: number;
  resumes_tailored: number;
  applications_submitted: number;
  review_required: number;
  blocked: number;
  skipped: number;
};

type LogEvent = {
  id?: string;
  timestamp: string;
  event: string;
  message: string;
  job_title?: string;
  company?: string;
  url?: string;
  status?: string;
};

const defaultProfile: Profile = {
  name: "Maddi Jagadeesh",
  email: "new192975@gmail.com",
  phone: "9963475211",
  target_roles: "ML Engineer, AI Engineer, AI Associate",
  locations: "Hyderabad, Remote",
  resume_path: "C:\\Users\\hp\\Downloads\\Maddi_Jagadeesh_AI_Resume.docx",
};

export function App() {
  const [activeTab, setActiveTab] = useState<"Live Operations" | "Discovered Jobs" | "Applications" | "Settings">("Live Operations");
  const [profile, setProfile] = useState<Profile>(() => {
    const saved = localStorage.getItem("jobhunter_profile");
    return saved ? JSON.parse(saved) : defaultProfile;
  });

  const [portalSession, setPortalSession] = useState<PortalSession>({ open: false, logged_in: false, message: "Checking..." });
  const [hunterStatus, setHunterStatus] = useState<string>("idle");
  const [currentStep, setCurrentStep] = useState<string>("Ready to hunt");
  const [stats, setStats] = useState<HunterStats>({
    jobs_found: 0,
    jobs_scored: 0,
    resumes_tailored: 0,
    applications_submitted: 0,
    review_required: 0,
    blocked: 0,
    skipped: 0,
  });

  const [discoveredJobs, setDiscoveredJobs] = useState<Job[]>([]);
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [autoApplyMode, setAutoApplyMode] = useState<boolean>(true);
  const [maxJobs, setMaxJobs] = useState<number>(15);
  const [useNaukri, setUseNaukri] = useState<boolean>(false);
  const [useJobicy, setUseJobicy] = useState<boolean>(true);
  const [useArbeitnow, setUseArbeitnow] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [uploadingResume, setUploadingResume] = useState<boolean>(false);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);

  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Persist profile
  useEffect(() => {
    localStorage.setItem("jobhunter_profile", JSON.stringify(profile));
  }, [profile]);

  // Scroll terminal
  useEffect(() => {
    if (autoScroll) {
      terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  // Check portal session periodically
  const checkSession = async () => {
    try {
      const res = await fetch("/api/integrations/naukri/session");
      if (res.ok) {
        const data = (await res.json()) as PortalSession;
        setPortalSession(data);
      }
    } catch {
      // Backend may be starting
    }
  };

  // Poll status fallback
  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/hunt/status");
      if (res.ok) {
        const data = await res.json();
        setHunterStatus(data.status);
        setCurrentStep(data.current_step);
        if (data.stats) setStats(data.stats);
        if (data.jobs && data.jobs.length > 0) setDiscoveredJobs(data.jobs);
        if (data.recent_activity && data.recent_activity.length > 0) {
          setLogs((prev) => (prev.length === 0 ? data.recent_activity : prev));
        }
      }
    } catch {
      // ignore
    }
  };

  // Connect SSE Live Stream
  useEffect(() => {
    checkSession();
    fetchStatus();

    const eventSource = new EventSource("/api/hunt/stream");

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const { event: evtType, data, timestamp } = payload;

        if (evtType === "INIT") {
          setHunterStatus(data.status);
          setCurrentStep(data.current_step);
          if (data.stats) setStats(data.stats);
          if (data.jobs) setDiscoveredJobs(data.jobs);
          if (data.recent_activity) setLogs(data.recent_activity);
          return;
        }

        // Add to log
        setLogs((prev) => [
          ...prev,
          {
            timestamp: timestamp || new Date().toLocaleTimeString(),
            event: evtType,
            message: data?.message || JSON.stringify(data),
            job_title: data?.job_title,
            company: data?.company,
            url: data?.url,
            status: data?.status,
          },
        ]);

        if (evtType === "HUNT_STARTED") {
          setHunterStatus("running");
        } else if (evtType === "HUNT_STOPPED") {
          setHunterStatus("stopped");
        } else if (evtType === "HUNT_COMPLETED") {
          setHunterStatus("completed");
          fetchStatus();
        } else if (evtType === "PROCESSING_JOB") {
          setCurrentStep(`Evaluating: ${data.job_title} at ${data.company}`);
        } else if (evtType === "APPLYING") {
          setCurrentStep(`Submitting: ${data.job_title} at ${data.company}`);
        }

        // Incrementally update stats if present
        if (data?.stats) {
          setStats(data.stats);
        }
      } catch (err) {
        console.error("SSE parse error", err);
      }
    };

    const sessionInterval = setInterval(checkSession, 5000);

    return () => {
      eventSource.close();
      clearInterval(sessionInterval);
    };
  }, []);

  // Launch browser for manual portal login
  const launchBrowser = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/integrations/naukri/launch", { method: "POST" });
      const data = await res.json();
      setPortalSession((prev) => ({ ...prev, open: true, message: data.reason || "Browser opened." }));
      setTimeout(checkSession, 2000);
    } catch {
      alert("Failed to launch browser.");
    } finally {
      setLoading(false);
    }
  };

  // Close browser
  const closeBrowser = async () => {
    setLoading(true);
    try {
      await fetch("/api/integrations/naukri/close", { method: "POST" });
      setPortalSession({ open: false, logged_in: false, message: "Browser closed." });
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  // Start autonomous hunt
  const startHunt = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!profile.resume_path) {
      setActiveTab("Settings");
      alert("Upload your base DOCX resume before starting a hunt. JobHunter uses it to create truthful tailored resumes.");
      return;
    }
    setLoading(true);
    try {
      const sources: string[] = [];
      if (useNaukri) sources.push("naukri");
      if (useJobicy) sources.push("jobicy");
      if (useArbeitnow) sources.push("arbeitnow");

      const res = await fetch("/api/hunt/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: profile.name,
          email: profile.email,
          phone: profile.phone,
          resume_path: profile.resume_path,
          target_roles: profile.target_roles.split(",").map((s) => s.trim()).filter(Boolean),
          locations: profile.locations.split(",").map((s) => s.trim()).filter(Boolean),
          auto_apply: autoApplyMode,
          sources,
          max_jobs: Number(maxJobs),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        alert(data.message || "Failed to start hunt.");
      } else {
        setHunterStatus("running");
      }
    } catch (err) {
      alert(`Error starting hunt: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const uploadResume = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".docx")) {
      alert("Please choose a DOCX resume. This lets JobHunter tailor the document safely for each role.");
      event.target.value = "";
      return;
    }

    setUploadingResume(true);
    try {
      const form = new FormData();
      form.append("resume", file);
      const response = await fetch("/api/profile/resume", { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Upload failed");
      setProfile((current) => ({ ...current, resume_path: data.resume_path }));
    } catch (error) {
      alert(`Resume upload failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setUploadingResume(false);
      event.target.value = "";
    }
  };

  // Stop autonomous hunt
  const stopHunt = async () => {
    setLoading(true);
    try {
      await fetch("/api/hunt/stop", { method: "POST" });
      setHunterStatus("stopped");
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  // Single job on-demand apply
  const applySingle = async (job: Job) => {
    try {
      setCurrentStep(`Applying to ${job.title}...`);
      const res = await fetch("/api/applications/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_url: job.application_url,
          job_description: job.description,
          name: profile.name,
          email: profile.email,
          phone: profile.phone,
          resume_path: profile.resume_path,
          submit: true,
          approved: true,
        }),
      });
      const data = await res.json();
      alert(`Result: ${data.status} - ${data.reason || "Processed"}`);
      fetchStatus();
    } catch (err) {
      alert(`Application error: ${err}`);
    }
  };

  return (
    <div className="shell">
      {/* Sidebar */}
      <aside>
        <div className="brand">
          <div className="brand-icon">⚡</div>
          <div>
            <h2>JobHunter<span>.AI</span></h2>
            <p>Autonomous Career Ops</p>
          </div>
        </div>

        <nav>
          {(["Live Operations", "Discovered Jobs", "Applications", "Settings"] as const).map((tab) => (
            <button
              key={tab}
              className={activeTab === tab ? "active" : ""}
              onClick={() => setActiveTab(tab)}
            >
              {tab === "Live Operations" && "⚡"}
              {tab === "Discovered Jobs" && "💼"}
              {tab === "Applications" && "📋"}
              {tab === "Settings" && "⚙️"}
              <span>{tab}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-profile">
          <div className="avatar">{profile.name.charAt(0)}</div>
          <div className="profile-info">
            <strong>{profile.name}</strong>
            <small>{profile.email}</small>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="content">
        {/* Header */}
        <header>
          <div className="header-title">
            <h1>{activeTab}</h1>
            <p>AI-driven job discovery, automated keyword resume tailoring, and instant application submission</p>
          </div>
          {hunterStatus === "running" && (
            <button className="btn btn-danger" onClick={stopHunt} disabled={loading}>
              ⏹ Stop Hunt Session
            </button>
          )}
        </header>

        {/* Portal Login & Session Status Bar */}
        <div className="portal-bar">
          <div className="portal-status-group">
            <div className={`portal-dot ${portalSession.logged_in ? "active" : ""}`} />
            <div className="portal-text">
              <h3>
                Naukri Portal:{" "}
                <span style={{ color: portalSession.logged_in ? "#10b981" : "#f59e0b" }}>
                  {portalSession.logged_in
                    ? `Logged In (${portalSession.user_name || profile.name})`
                    : portalSession.open
                    ? "Browser Open - Log In on Browser Window"
                    : "Not Connected"}
                </span>
              </h3>
              <p>
                {portalSession.message ||
                  (portalSession.logged_in
                    ? "Authenticated session ready. The AI can search and submit applications directly."
                    : "Launch browser once to log in and solve OTP/CAPTCHA. AI takes over afterwards.")}
              </p>
            </div>
          </div>
          <div className="portal-actions">
            {!portalSession.open ? (
              <button className="btn btn-primary" onClick={launchBrowser} disabled={loading}>
                🚀 Launch Portal Browser
              </button>
            ) : (
              <>
                <button className="btn btn-secondary" onClick={checkSession} disabled={loading}>
                  🔄 Verify Login
                </button>
                <button className="btn btn-danger" onClick={closeBrowser} disabled={loading}>
                  Close
                </button>
              </>
            )}
          </div>
        </div>

        {/* Metrics Bar */}
        <div className="metrics-grid">
          <div className="metric-card">
            <span>Jobs Discovered</span>
            <strong>{stats.jobs_found}</strong>
          </div>
          <div className="metric-card">
            <span>Scored & Analyzed</span>
            <strong>{stats.jobs_scored}</strong>
          </div>
          <div className="metric-card">
            <span>Resumes Tailored</span>
            <strong>{stats.resumes_tailored}</strong>
          </div>
          <div className="metric-card">
            <span>Auto-Submitted</span>
            <strong style={{ color: "#10b981" }}>{stats.applications_submitted}</strong>
          </div>
          <div className="metric-card">
            <span>Review / Blocked</span>
            <strong style={{ color: stats.review_required > 0 ? "#f59e0b" : "#94a3b8" }}>
              {stats.review_required + stats.blocked}
            </strong>
          </div>
        </div>

        {/* Active Step Indicator */}
        {hunterStatus === "running" && (
          <div className="step-banner">
            <div className="step-spinner" />
            <span>Active: {currentStep}</span>
          </div>
        )}

        {/* TAB: Live Operations */}
        {activeTab === "Live Operations" && (
          <div className="control-grid">
            {/* Left Column: Hunt Configuration */}
            <div className="panel">
              <div className="panel-header">
                <h2>Autonomous Hunter Settings</h2>
                <span>{hunterStatus.toUpperCase()}</span>
              </div>

              <form onSubmit={startHunt} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div className="form-group">
                  <label>Target Job Roles (comma-separated)</label>
                  <input
                    className="form-input"
                    value={profile.target_roles}
                    onChange={(e) => setProfile({ ...profile, target_roles: e.target.value })}
                    placeholder="ML Engineer, AI Engineer, AI Associate"
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Target Locations</label>
                  <input
                    className="form-input"
                    value={profile.locations}
                    onChange={(e) => setProfile({ ...profile, locations: e.target.value })}
                    placeholder="Hyderabad, Remote, Bengaluru"
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Max Applications Per Run</label>
                    <input
                      type="number"
                      className="form-input"
                      value={maxJobs}
                      onChange={(e) => setMaxJobs(Math.max(1, parseInt(e.target.value) || 10))}
                      min="1"
                      max="50"
                    />
                  </div>
                  <div className="form-group">
                    <label>Job Sources</label>
                    <div style={{ display: "flex", gap: "12px", marginTop: "8px", fontSize: "13px" }}>
                      <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={useNaukri}
                          onChange={(e) => setUseNaukri(e.target.checked)}
                        />
                        Naukri
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={useJobicy}
                          onChange={(e) => setUseJobicy(e.target.checked)}
                        />
                        Jobicy Remote
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={useArbeitnow}
                          onChange={(e) => setUseArbeitnow(e.target.checked)}
                        />
                        Direct ATS
                      </label>
                    </div>
                  </div>
                </div>

                <div className="toggle-group">
                  <div>
                    <span>⚡ Auto-Apply Mode</span>
                    <small>
                      {autoApplyMode
                        ? "AI fills screening questions truthfully and automatically submits"
                        : "AI fills form and leaves ready for 1-click human verification"}
                    </small>
                  </div>
                  <input
                    type="checkbox"
                    style={{ width: "20px", height: "20px", cursor: "pointer" }}
                    checked={autoApplyMode}
                    onChange={(e) => setAutoApplyMode(e.target.checked)}
                  />
                </div>

                <div style={{ display: "flex", gap: "12px", marginTop: "10px" }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ flex: 1, padding: "12px", fontSize: "15px" }}
                    disabled={hunterStatus === "running" || loading}
                  >
                    {hunterStatus === "running" ? "⏳ Hunter Active..." : "▶ Start Autonomous Job Hunter"}
                  </button>
                  {hunterStatus === "running" && (
                    <button type="button" className="btn btn-danger" onClick={stopHunt} disabled={loading}>
                      ⏹ Stop
                    </button>
                  )}
                </div>
              </form>
            </div>

            {/* Right Column: Real-Time Event Stream Terminal */}
            <div className="terminal-window">
              <div className="terminal-header">
                <div className="terminal-title">
                  <span>●</span> Real-Time Hunting & Action Stream
                </div>
                <div className="terminal-actions">
                  <button
                    className="btn btn-secondary"
                    style={{ padding: "4px 8px", fontSize: "11px" }}
                    onClick={() => setAutoScroll(!autoScroll)}
                  >
                    Auto-scroll: {autoScroll ? "ON" : "OFF"}
                  </button>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: "4px 8px", fontSize: "11px" }}
                    onClick={() => setLogs([])}
                  >
                    Clear
                  </button>
                </div>
              </div>

              <div className="terminal-body">
                {logs.length === 0 ? (
                  <div style={{ color: "#64748b", margin: "auto", textAlign: "center" }}>
                    No events yet. Launch portal browser or click "Start Autonomous Job Hunter" to begin.
                  </div>
                ) : (
                  logs.map((item, idx) => {
                    let badgeClass = "info";
                    if (item.event.includes("SUBMITTED") || item.event.includes("COMPLETED")) badgeClass = "success";
                    else if (item.event.includes("REVIEW") || item.event.includes("WARNING")) badgeClass = "warn";
                    else if (item.event.includes("ERROR") || item.event.includes("BLOCKED")) badgeClass = "error";

                    return (
                      <div key={idx} className="log-line">
                        <span className="log-time">{item.timestamp}</span>
                        <span className={`log-badge ${badgeClass}`}>{item.event}</span>
                        <span className="log-msg">
                          {item.message}
                          {item.url && (
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: "#38bdf8", marginLeft: "6px" }}
                            >
                              [View Job]
                            </a>
                          )}
                        </span>
                      </div>
                    );
                  })
                )}
                <div ref={terminalEndRef} />
              </div>
            </div>
          </div>
        )}

        {/* TAB: Discovered Jobs */}
        {activeTab === "Discovered Jobs" && (
          <div className="jobs-list">
            {discoveredJobs.length === 0 ? (
              <div style={{ padding: "60px 0", textAlign: "center", color: "#64748b" }}>
                <h2>No jobs discovered yet</h2>
                <p>Run the Autonomous Job Hunter to search and tailor jobs in real-time.</p>
              </div>
            ) : (
              discoveredJobs.map((job) => (
                <div key={job.id} className="job-item">
                  <div className="job-main">
                    <div className="job-meta">
                      <strong>{job.company}</strong>
                      <span>•</span>
                      <span>{job.location}</span>
                      <span>•</span>
                      <span style={{ textTransform: "uppercase", color: "#38bdf8" }}>{job.source}</span>
                    </div>
                    <h3>{job.title}</h3>
                    <p className="job-desc">{job.description}</p>
                    {job.matched_skills && job.matched_skills.length > 0 && (
                      <div className="skills-tags">
                        {job.matched_skills.map((skill, sIdx) => (
                          <span key={sIdx} className="skill-tag">
                            {skill}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="job-actions">
                    {job.fit_score !== undefined && (
                      <div className="score-badge">{Math.round(job.fit_score)}% Match</div>
                    )}
                    <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                      <a
                        href={job.application_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-secondary"
                        style={{ fontSize: "12px", textDecoration: "none" }}
                      >
                        Open Listing ↗
                      </a>
                      <button
                        className="btn btn-primary"
                        style={{ fontSize: "12px" }}
                        onClick={() => applySingle(job)}
                      >
                        Apply / Review
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB: Applications */}
        {activeTab === "Applications" && (
          <div className="jobs-list">
            <div className="panel">
              <h2>Tracked Applications</h2>
              <p style={{ color: "#94a3b8", fontSize: "13px" }}>
                Review real submissions and applications prepared by the AI engine.
              </p>
            </div>
            {discoveredJobs.filter((j) => j.status).length === 0 ? (
              <div style={{ padding: "60px 0", textAlign: "center", color: "#64748b" }}>
                <h2>No applications processed yet</h2>
                <p>Start a hunt session to see applications tracked live.</p>
              </div>
            ) : (
              discoveredJobs
                .filter((j) => j.status)
                .map((job) => (
                  <div key={job.id} className="job-item">
                    <div>
                      <h3>{job.title}</h3>
                      <div className="job-meta">
                        <strong>{job.company}</strong>
                        <span>•</span>
                        <span>{job.location}</span>
                      </div>
                      <p style={{ fontSize: "13px", color: "#94a3b8", marginTop: "6px" }}>
                        Status Note: {job.reason || "Application recorded."}
                      </p>
                    </div>
                    <div className="job-actions">
                      <span
                        className={`log-badge ${
                          job.status === "submitted"
                            ? "success"
                            : job.status === "blocked"
                            ? "error"
                            : "warn"
                        }`}
                        style={{ fontSize: "13px", padding: "6px 12px" }}
                      >
                        {(job.status || "pending").toUpperCase()}
                      </span>
                    </div>
                  </div>
                ))
            )}
          </div>
        )}

        {/* TAB: Settings */}
        {activeTab === "Settings" && (
          <div className="panel" style={{ maxWidth: "700px" }}>
            <h2>Candidate Profile & Resume Configuration</h2>
            <div className="form-group">
              <label>Full Name</label>
              <input
                className="form-input"
                value={profile.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Email Address</label>
              <input
                className="form-input"
                type="email"
                value={profile.email}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Phone Number</label>
              <input
                className="form-input"
                value={profile.phone}
                onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Base Resume (.docx)</label>
              <input
                className="form-input"
                type="file"
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={uploadResume}
                disabled={uploadingResume}
              />
              <small style={{ color: "#94a3b8", marginTop: "6px" }}>
                {uploadingResume
                  ? "Uploading your resume..."
                  : profile.resume_path
                  ? "Base resume uploaded and ready for truthful tailoring."
                  : "Upload your latest DOCX resume. It is required before auto-apply can start."}
              </small>
              <input
                className="form-input"
                value={profile.resume_path}
                onChange={(e) => setProfile({ ...profile, resume_path: e.target.value })}
                placeholder="Uploaded resume path appears here"
              />
            </div>
            <p style={{ fontSize: "12px", color: "#64748b" }}>
              Tailored resumes are generated as `.docx` and `.pdf` files in the `.generated-resumes/` folder during each hunt.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
