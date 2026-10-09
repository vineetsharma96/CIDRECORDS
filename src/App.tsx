import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Check,
  CircleHelp,
  FileText,
  Fingerprint,
  GitBranch,
  LayoutDashboard,
  Network,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Upload,
  Users,
  X,
  History,
  Folder,
  RefreshCw,
} from "lucide-react";
import {
  api,
  Audit,
  Case,
  Dashboard,
  Fact,
  fields,
  Health,
  ImportRecord,
  Job,
  label,
  number,
  date,
  Person,
} from "./api";
const GraphView = lazy(() => import("./GraphView"));
const nav = [
  { id: "dashboard", name: "Overview", icon: LayoutDashboard },
  { id: "uploads", name: "Document Imports", icon: Upload },
  { id: "review", name: "Match Review", icon: GitBranch },
  { id: "people", name: "Entity Directory", icon: Users },
  { id: "graph", name: "Graph Explorer", icon: Network },
  { id: "evidence", name: "Evidence Library", icon: FileText },
  { id: "cases", name: "Cases", icon: Folder },
  { id: "audit", name: "Audit History", icon: History },
  { id: "settings", name: "Settings", icon: Settings },
];
const titles: Record<string, [string, string]> = {
  dashboard: [
    "Investigation Overview",
    "A clearer picture. One source at a time.",
  ],
  uploads: [
    "Document Imports",
    "Turn historical records into sourced, reviewable facts.",
  ],
  review: [
    "Identity Reconciliation",
    "Review the evidence before joining identities.",
  ],
  people: ["Entity Directory", "People, profiles and the sources behind them."],
  graph: ["Knowledge Graph", "Explore connections. Keep the evidence in view."],
  evidence: ["Evidence Library", "Trace every detail to its original record."],
  cases: ["Case Workspace", "A shared view of people and source documents."],
  audit: ["Audit History", "Every decision leaves a trace."],
  settings: ["Workspace Settings", "Local processing. Explainable rules."],
};

function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">
        <FileText aria-hidden="true" size={28} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
function Status({ value }: { value: string }) {
  return <span className={`badge status-${value}`}>{label(value)}</span>;
}
function Dialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="drawer"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-label={title}
    >
      <div className="drawer-head">
        <div>
          <span className="eyebrow">Source & Provenance</span>
          <h2>{title}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Close Details"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function EvidenceDrawer({
  fact,
  onClose,
}: {
  fact: Fact;
  onClose: () => void;
}) {
  return (
    <Dialog title={label(fact.field)} onClose={onClose}>
      <div className="fact-value">{fact.value}</div>
      <Status value={fact.review_state} />
      <dl className="detail-list">
        <dt>Original Value</dt>
        <dd>{fact.original ?? "Unknown"}</dd>
        <dt>Normalised Value</dt>
        <dd>{fact.normalized}</dd>
        <dt>Source Document</dt>
        <dd>{fact.filename}</dd>
        <dt>Location</dt>
        <dd>
          {fact.page
            ? `Page ${fact.page} · text span ${fact.span?.join("–") ?? "unavailable"}`
            : `Row ${fact.row ?? "unknown"} · column ${fact.column ?? "unknown"}`}
        </dd>
        <dt>Extraction</dt>
        <dd>
          {label(fact.method)} ·{" "}
          {fact.confidence === null
            ? "Confidence unavailable"
            : `confidence ${fact.confidence}`}
        </dd>
        <dt>Reviewed By</dt>
        <dd>{fact.approved_by ?? "Awaiting Review"}</dd>
        <dt>Approval Reason</dt>
        <dd>{fact.approval_reason ?? "No approval recorded"}</dd>
        <dt>Import Job</dt>
        <dd translate="no">{fact.job_id}</dd>
        <dt>Claim State</dt>
        <dd>
          {fact.active ? "Active" : "Superseded"} ·{" "}
          {fact.committed ? "Committed" : "Proposed"}
        </dd>
      </dl>
      <a
        className="primary link-button"
        href={`/api/imports/${fact.job_id}/source`}
        target="_blank"
        rel="noreferrer"
      >
        Open Original File <ArrowUpRight size={16} aria-hidden="true" />
      </a>
      <p className="muted">
        Sources stay intact when records are corrected, merged or split.
      </p>
    </Dialog>
  );
}

export default function App() {
  const [entered, setEntered] = useState(false),
    [tab, setTab] = useState("dashboard"),
    [visitedGraph, setVisitedGraph] = useState(false);
  const [health, setHealth] = useState<Health | null>(null),
    [dashboard, setDashboard] = useState<Dashboard | null>(null),
    [jobs, setJobs] = useState<Job[]>([]),
    [people, setPeople] = useState<Person[]>([]),
    [claims, setClaims] = useState<Fact[]>([]),
    [cases, setCases] = useState<Case[]>([]),
    [audit, setAudit] = useState<Audit[]>([]);
  const [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [job, setJob] = useState<Job | null>(null),
    [person, setPerson] = useState<Person | null>(null),
    [fact, setFact] = useState<Fact | null>(null);
  const [query, setQuery] = useState(""),
    [role, setRole] = useState(""),
    [actor, setActor] = useState(
      () => sessionStorage.getItem("reviewer") || "Local Investigator",
    ),
    [reason, setReason] = useState(""),
    [file, setFile] = useState<File | null>(null);
  const [pendingUndo, setPendingUndo] = useState<Audit | null>(null);
  const report = useCallback((text: string) => setError(text), []);
  const refreshing = useRef(false);
  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const [h, d, j, p, c, e, a] = await Promise.all([
        api<Health>("/health"),
        api<Dashboard>("/dashboard"),
        api<Job[]>("/imports"),
        api<{ people: Person[] }>("/people?limit=200"),
        api<Case[]>("/cases"),
        api<{ claims: Fact[] }>("/evidence?limit=500"),
        api<Audit[]>("/audit"),
      ]);
      setHealth(h);
      setDashboard(d);
      setJobs(j);
      setPeople(p.people);
      setCases(c);
      setClaims(e.claims);
      setAudit(a);
    } catch (e) {
      report((e as Error).message);
    } finally {
      setLoading(false);
      refreshing.current = false;
    }
  }, [report]);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    sessionStorage.setItem("reviewer", actor);
  }, [actor]);
  useEffect(() => {
    const before = (event: BeforeUnloadEvent) => {
      if (file || reason) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", before);
    return () => window.removeEventListener("beforeunload", before);
  }, [file, reason]);
  const selectedJob = job?.id;
  useEffect(() => {
    if (!selectedJob) return;
    let stopped = false;
    const update = async () => {
      try {
        const latest = await api<Job>("/imports/" + selectedJob);
        if (!stopped) setJob(latest);
      } catch (e) {
        report((e as Error).message);
      }
    };
    update();
    const interval = setInterval(update, 4000);
    return () => {
      stopped = true;
      clearInterval(interval);
    };
  }, [selectedJob, report]);
  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    try {
      await action();
      setMessage(success);
      await refresh();
      if (job) setJob(await api<Job>("/imports/" + job.id));
      return true;
    } catch (e) {
      report((e as Error).message);
      if (/reviewer|reason/i.test((e as Error).message)) {
        document
          .querySelector<HTMLInputElement>('input[name="review-reason"]')
          ?.focus();
      }
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function openJob(id: string) {
    setBusy(true);
    try {
      setJob(await api<Job>("/imports/" + id));
      setTab("uploads");
    } catch (e) {
      report((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function switchTab(id: string) {
    setTab(id);
    if (id === "graph") setVisitedGraph(true);
    document.getElementById("workspace-title")?.focus();
  }
  async function uploadFile(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      report("Choose a PDF or CSV file before starting an import.");
      document.getElementById("upload-file")?.focus();
      return;
    }
    await run(async () => {
      const body = new FormData();
      body.set("file", file);
      const response = await api<{ job: Job; repeated: boolean }>(
        "/imports",
        body,
      );
      setJob(response.job);
      setFile(null);
      setMessage(
        response.repeated
          ? "This file was already uploaded. Its existing job has been opened."
          : "Upload saved. Local extraction is running.",
      );
    }, "Import job saved.");
  }
  async function review(
    record: ImportRecord,
    action: string,
    target: string | null,
    corrected?: Record<string, string | null>,
  ) {
    if (!job) return false;
    if (!actor.trim() || !reason.trim()) {
      report("Enter a reviewer name and decision reason before saving.");
      document
        .querySelector<HTMLInputElement>('input[name="review-reason"]')
        ?.focus();
      return false;
    }
    return run(
      () =>
        api("/imports/" + job.id + "/records/" + record.id + "/review", {
          action,
          target,
          actor,
          reason,
          corrected,
        }),
      "Review decision saved. Preview the changes before committing.",
    );
  }
  const filteredPeople = people.filter(
    (p) =>
      (!role || p.roles.includes(role)) &&
      JSON.stringify(p).toLowerCase().includes(query.toLowerCase()),
  );
  const filteredClaims = claims.filter((c) =>
    JSON.stringify(c).toLowerCase().includes(query.toLowerCase()),
  );
  const reviews = jobs.filter((j) => j.status === "review");

  return (
    <>
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        Skip to Content
      </a>
      <AnimatePresence mode="wait">
        {!entered ? (
          <motion.div
            className="welcome"
            key="welcome"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -24 }}
          >
            <header className="welcome-header">
              <div className="brand">
                <span className="brand-symbol">N</span>
                <span>NULLVERSE</span>
              </div>
              <span className="welcome-team">Team NULLVERSE / Dev2Hack</span>
            </header>
            <main id="main" tabIndex={-1} className="welcome-main">
              <span className="eyebrow">Evidence. Identity. Connection.</span>
              <h1>
                See the connections.
                <br />
                <em>Keep the context.</em>
              </h1>
              <p className="welcome-description">
                Criminal Network Analysis System
              </p>
              <p className="welcome-copy">
                Bring historical records into one investigation workspace.
                Follow every fact back to its source.
              </p>
              <button
                className="welcome-enter"
                onClick={() => setEntered(true)}
              >
                Enter Workspace <ArrowRight aria-hidden="true" size={21} />
              </button>
              <div className="welcome-art" aria-hidden="true">
                <svg viewBox="0 0 720 230">
                  <path
                    d="M120 115L270 50L450 95L590 50M120 115L290 190L450 95L590 175M270 50L290 190L590 175"
                    fill="none"
                    stroke="#bdc8c5"
                    strokeWidth="2"
                  />
                  <circle cx="120" cy="115" r="37" fill="#f2e3c5" />
                  <circle cx="270" cy="50" r="24" fill="#cfdfd7" />
                  <circle cx="290" cy="190" r="28" fill="#e2dcd0" />
                  <circle cx="450" cy="95" r="49" fill="#173b35" />
                  <circle cx="590" cy="50" r="22" fill="#e4cec0" />
                  <circle cx="590" cy="175" r="29" fill="#cfdfd7" />
                  <path
                    d="M432 112V78l36 34V78"
                    fill="none"
                    stroke="#d1e5d7"
                    strokeWidth="3"
                  />
                </svg>
                <span className="art-label art-left">
                  01 / Source Documents
                </span>
                <span className="art-label art-right">
                  02 / Sourced Connections
                </span>
              </div>
              <p className="welcome-note">
                Built to support investigation. Network connections do not
                establish guilt.
              </p>
            </main>
            <footer className="welcome-footer">
              <span>Team NULLVERSE / Dev2Hack</span>
              <span>Historical Document Intelligence</span>
            </footer>
          </motion.div>
        ) : (
          <motion.div
            key="workspace"
            className="workspace"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <aside className="sidebar">
              <div className="brand">
                <span className="brand-symbol">N</span>
                <div>
                  NULLVERSE<small>INVESTIGATION WORKSPACE</small>
                </div>
              </div>
              <div className="workspace-label">
                <span className="live-dot" />
                Historical Records<span className="workspace-id">01</span>
              </div>
              <div className="nav-caption">Workspace</div>
              <nav aria-label="Workspace Views">
                {nav.map(({ id, name, icon: Icon }) => (
                  <button
                    key={id}
                    aria-label={name}
                    className={tab === id ? "nav-item active" : "nav-item"}
                    aria-current={tab === id ? "page" : undefined}
                    onClick={() => switchTab(id)}
                  >
                    <Icon size={18} aria-hidden="true" />
                    <span>{name}</span>
                    {id === "review" && dashboard?.pending ? (
                      <span className="nav-count">{dashboard.pending}</span>
                    ) : null}
                  </button>
                ))}
              </nav>
              <div className="sidebar-note">
                <ShieldCheck size={21} aria-hidden="true" />
                <strong>Evidence Comes First</strong>
                <p>
                  A connection is a starting point for review, never a verdict.
                </p>
              </div>
              <div className="operator">
                <div className="avatar">LI</div>
                <div>
                  Local Investigator<small>Team NULLVERSE / Dev2Hack</small>
                </div>
              </div>
            </aside>
            <div className="workspace-body">
              <header className="topbar">
                <div className="breadcrumb">
                  Workspace <span>/</span> {nav.find((n) => n.id === tab)?.name}
                </div>
                <div className="topbar-right">
                  <span className="connection">
                    <span className={error ? "error-dot" : "live-dot"} />
                    {health
                      ? health.backend === "neo4j"
                        ? "Neo4j Connected"
                        : "SQLite Demo"
                      : loading
                        ? "Connecting…"
                        : "Service Unavailable"}
                  </span>
                  <button
                    className="icon-button"
                    onClick={() => {
                      setError("");
                      refresh();
                    }}
                    aria-label="Refresh Workspace"
                  >
                    <RefreshCw size={17} aria-hidden="true" />
                  </button>
                  <button
                    className="icon-button"
                    onClick={() => switchTab("settings")}
                    aria-label="Workspace Help"
                  >
                    <CircleHelp size={18} aria-hidden="true" />
                  </button>
                </div>
              </header>
              <main id="main" tabIndex={-1} className="content">
                <div className="page-heading">
                  <div>
                    <div className="eyebrow">
                      {health?.demo
                        ? "SYNTHETIC DEMO WORKSPACE"
                        : "INVESTIGATION SUPPORT"}
                    </div>
                    <h1 id="workspace-title" tabIndex={-1}>
                      {titles[tab][0]}
                    </h1>
                    <p>{titles[tab][1]}</p>
                  </div>
                  <button
                    className="primary"
                    onClick={() => switchTab("uploads")}
                  >
                    <Plus size={18} aria-hidden="true" />
                    Import Documents
                  </button>
                </div>
                {error && (
                  <div className="error-banner" role="alert">
                    <span>{error}</span>
                    <button
                      onClick={() => {
                        setError("");
                        refresh();
                      }}
                    >
                      Retry Connection
                    </button>
                  </div>
                )}
                <div className="sr-only" aria-live="polite">
                  {message}
                  {busy ? " Processing…" : ""}
                </div>
                {message && (
                  <div className="success-banner">
                    <Check size={17} aria-hidden="true" />
                    <span>{message}</span>
                    <button
                      className="icon-button"
                      onClick={() => setMessage("")}
                      aria-label="Dismiss Notification"
                    >
                      <X size={15} aria-hidden="true" />
                    </button>
                  </div>
                )}
                {loading && (
                  <div className="loading" role="status">
                    Loading Workspace…
                  </div>
                )}
                <section hidden={tab !== "dashboard"} className="view">
                  <div className="overview-banner">
                    <div className="overview-copy">
                      <span className="eyebrow">
                        FROM RECORDS TO RELATIONSHIPS
                      </span>
                      <h2>
                        Follow the evidence.
                        <br />
                        <em>Find the bigger picture.</em>
                      </h2>
                      <p>
                        Import. Reconcile. Explore.
                        <br />
                        Every connection stays linked to its source.
                      </p>
                      <button
                        className="text-action"
                        onClick={() => switchTab("graph")}
                      >
                        Explore the Knowledge Graph{" "}
                        <ArrowUpRight size={17} aria-hidden="true" />
                      </button>
                    </div>
                    <div className="overview-network" aria-hidden="true">
                      <svg viewBox="0 0 420 270">
                        <g fill="none" stroke="#315b5f">
                          <path d="M35 135L137 55L240 118L355 40M137 55L150 224L240 118L355 225M35 135L150 224L355 225M240 118L380 135" />
                          <circle cx="240" cy="118" r="65" />
                          <circle
                            cx="240"
                            cy="118"
                            r="87"
                            strokeDasharray="2 8"
                          />
                        </g>
                        <g fill="#66cbb2">
                          <circle cx="35" cy="135" r="7" />
                          <circle cx="137" cy="55" r="10" />
                          <circle cx="150" cy="224" r="9" />
                          <circle cx="355" cy="40" r="6" />
                          <circle cx="355" cy="225" r="7" />
                          <circle cx="380" cy="135" r="9" />
                        </g>
                        <circle cx="240" cy="118" r="23" fill="#68d0b6" />
                        <path
                          d="M232 128V108l16 20v-20"
                          fill="none"
                          stroke="#0a2927"
                          strokeWidth="2"
                        />
                      </svg>
                      <span className="visual-caption">
                        EVIDENCE-LINKED INTELLIGENCE
                      </span>
                    </div>
                  </div>
                  <div className="metrics">
                    {[
                      {
                        title: "People in the Network",
                        value: dashboard?.people,
                        icon: Users,
                        note: "Source-supported identities",
                      },
                      {
                        title: "Source Documents",
                        value: dashboard?.documents,
                        icon: FileText,
                        note: "Persisted historical imports",
                      },
                      {
                        title: "Pending Review",
                        value: dashboard?.pending,
                        icon: GitBranch,
                        note: "Identity decisions awaiting review",
                      },
                      {
                        title: "Sourced Connections",
                        value: dashboard?.relationships,
                        icon: Network,
                        note: "Evidence attached to every edge",
                      },
                    ].map(({ title, value, icon: Icon, note }) => (
                      <article className="metric" key={title}>
                        <div>
                          {title}
                          <Icon size={18} aria-hidden="true" />
                        </div>
                        <strong>
                          {value === undefined ? "—" : number(value)}
                        </strong>
                        <span>{note}</span>
                      </article>
                    ))}
                  </div>
                  <div className="dashboard-lower">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <span className="eyebrow">Import Activity</span>
                          <h3>Recent Documents</h3>
                        </div>
                        <button
                          className="text-action"
                          onClick={() => switchTab("uploads")}
                        >
                          View All <ArrowRight size={15} aria-hidden="true" />
                        </button>
                      </div>
                      <JobTable
                        jobs={dashboard?.recent_imports ?? []}
                        open={openJob}
                      />
                    </section>
                    <aside className="panel review-summary">
                      <span className="eyebrow">Reconciliation Queue</span>
                      <div className="queue-icon">
                        <Fingerprint size={34} aria-hidden="true" />
                      </div>
                      <h3>
                        Resolve Identities
                        <br />
                        With Confidence
                      </h3>
                      <p>
                        {dashboard?.pending ?? 0} records are awaiting review.
                        Compare original details, matching signals and
                        conflicts.
                      </p>
                      <button onClick={() => switchTab("review")}>
                        Open Review Queue{" "}
                        <ArrowRight size={16} aria-hidden="true" />
                      </button>
                      <div className="mini-stat">
                        <span>Connected Components</span>
                        <strong>
                          {dashboard?.analytics.component_count ?? "—"}
                        </strong>
                      </div>
                      <div className="mini-stat">
                        <span>Committed Facts</span>
                        <strong>{dashboard?.facts ?? "—"}</strong>
                      </div>
                      <div className="mini-stat">
                        <span>Import Warnings</span>
                        <strong>{dashboard?.warnings ?? "—"}</strong>
                      </div>
                    </aside>
                  </div>
                  {!dashboard?.people && health?.demo && (
                    <div className="seed-bar">
                      <div>
                        <strong>Start With a Fictional Dataset</strong>
                        <p>
                          Load 6 source-linked profiles to test exact matches,
                          conflicts and new identities.
                        </p>
                      </div>
                      <button
                        disabled={busy}
                        onClick={() =>
                          run(
                            () => api("/demo/seed", {}),
                            "Synthetic seed dataset loaded.",
                          )
                        }
                      >
                        Load Seed Dataset
                      </button>
                    </div>
                  )}
                </section>

                <section hidden={tab !== "uploads"} className="view">
                  <div className="upload-grid">
                    <form onSubmit={uploadFile} className="upload-panel panel">
                      <div className="upload-icon">
                        <Upload size={28} aria-hidden="true" />
                      </div>
                      <h2>Bring Your Records Together</h2>
                      <p>
                        Upload authorised PDF or CSV records. Parsing runs
                        locally, and proposed changes wait for review.
                      </p>
                      <label className="file-label" htmlFor="upload-file">
                        Choose Historical Document
                        <input
                          id="upload-file"
                          name="historical-document"
                          type="file"
                          accept=".csv,.pdf"
                          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                        />
                      </label>
                      <span className="muted">
                        {file
                          ? file.name
                          : "PDF or CSV · up to 20 MB · 100 pages or 5,000 rows"}
                      </span>
                      <button type="submit" className="primary" disabled={busy}>
                        {busy ? "Uploading…" : "Upload & Extract"}
                        <ArrowRight aria-hidden="true" size={16} />
                      </button>
                    </form>
                    <aside className="panel">
                      <span className="eyebrow">The Import Workflow</span>
                      <ol className="pipeline">
                        {[
                          "Upload & Parse",
                          "Extract & Normalise",
                          "Compare Identities",
                          "Review Proposed Changes",
                          "Commit & Explore",
                        ].map((step, i) => (
                          <li key={step}>
                            <span>{String(i + 1).padStart(2, "0")}</span>
                            {step}
                          </li>
                        ))}
                      </ol>
                      {health?.demo && (
                        <a
                          className="text-action"
                          href="/api/demo/samples"
                          download
                        >
                          <ArrowDownToLine size={17} aria-hidden="true" />
                          Download Sample Files
                        </a>
                      )}
                      <p className="muted">
                        Missing information stays unknown. Shared identifiers
                        never prove that two people are the same.
                      </p>
                    </aside>
                  </div>
                  {job && (
                    <div className="panel job-review">
                      <div className="panel-heading">
                        <div>
                          <span className="eyebrow">Persisted Import Job</span>
                          <h2>{job.filename}</h2>
                        </div>
                        <Status value={job.status} />
                      </div>
                      <div className="progress-track">
                        <div
                          style={{ transform: `scaleX(${job.progress / 100})` }}
                        />
                      </div>
                      <div className="job-meta">
                        <span>
                          {number(job.records.length)} extracted records
                        </span>
                        <span translate="no">
                          SHA-256 {job.hash.slice(0, 16)}…
                        </span>
                        <a
                          href={`/api/imports/${job.id}/source`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open Source File ↗
                        </a>
                      </div>
                      {job.error && (
                        <div className="error-banner">
                          <span>{job.error}</span>
                          <button
                            disabled={busy}
                            onClick={() =>
                              run(
                                () => api("/imports/" + job.id + "/retry", {}),
                                "Import retry queued.",
                              )
                            }
                          >
                            Retry Extraction
                          </button>
                        </div>
                      )}
                      {job.warnings.map((w) => (
                        <p className="notice" key={w}>
                          {w}
                        </p>
                      ))}
                      {job.headers.length > 0 && job.status === "review" && (
                        <ColumnMapping
                          job={job}
                          busy={busy}
                          save={(mapping) =>
                            run(
                              () =>
                                api(
                                  "/imports/" + job.id + "/mapping",
                                  { mapping },
                                  "PUT",
                                ),
                              "Column mapping saved.",
                            )
                          }
                        />
                      )}
                      {job.records.length > 0 && (
                        <>
                          <div className="review-approval">
                            <label>
                              Reviewer Name
                              <input
                                name="reviewer"
                                autoComplete="name"
                                value={actor}
                                onChange={(e) => setActor(e.target.value)}
                              />
                            </label>
                            <label>
                              Decision / Commit Reason
                              <input
                                name="review-reason"
                                autoComplete="off"
                                placeholder="Explain the supporting evidence…"
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                              />
                            </label>
                          </div>
                          <div className="record-list">
                            {job.records.map((record) => (
                              <RecordReview
                                key={record.id}
                                record={record}
                                sourcePage={
                                  record.page
                                    ? {
                                        jobId: job.id,
                                        ...job.pages.find(
                                          (p) => p.number === record.page,
                                        ),
                                      }
                                    : undefined
                                }
                                people={people}
                                onEvidence={setFact}
                                onEvidenceById={(id) =>
                                  api<Fact>("/evidence/" + id)
                                    .then(setFact)
                                    .catch((e) => report(e.message))
                                }
                                busy={busy}
                                decide={review}
                              />
                            ))}
                          </div>
                          <div className="commit-bar">
                            <div>
                              <strong>Preview Before Commit</strong>
                              <p>
                                {
                                  job.records.filter(
                                    (r) =>
                                      !r.committed && !r.blank && !r.duplicate,
                                  ).length
                                }{" "}
                                records remaining. Safe matches enrich;
                                uncertain records stay in review.
                              </p>
                            </div>
                            <button
                              className="primary"
                              disabled={busy || job.status === "committed"}
                              onClick={() =>
                                run(
                                  () =>
                                    api("/imports/" + job.id + "/commit", {
                                      actor,
                                      reason,
                                    }),
                                  "Supported changes committed. Uncertain records remain in review.",
                                )
                              }
                            >
                              {busy ? "Committing…" : "Commit Reviewed Changes"}
                              <Check size={17} aria-hidden="true" />
                            </button>
                          </div>
                          {job.result && (
                            <div className="result-summary">
                              {Object.entries(job.result).map(
                                ([key, value]) => (
                                  <span key={key}>
                                    {label(key)} <strong>{value}</strong>
                                  </span>
                                ),
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                  <section className="panel">
                    <div className="panel-heading">
                      <h2>Import History</h2>
                      <span className="muted">
                        {jobs.length} persisted jobs
                      </span>
                    </div>
                    <JobTable jobs={jobs} open={openJob} />
                  </section>
                </section>

                <section hidden={tab !== "review"} className="view">
                  <div className="notice">
                    Scores show weighted attribute agreement, not identity
                    probabilities. Name-only matches and contradictory evidence
                    require review.
                  </div>
                  {reviews.length ? (
                    <div className="review-jobs">
                      {reviews.map((j) => (
                        <button
                          className="panel review-job"
                          key={j.id}
                          onClick={() => openJob(j.id)}
                        >
                          <FileText size={24} aria-hidden="true" />
                          <div>
                            <strong>{j.filename}</strong>
                            <span>
                              {j.record_count ?? 0} extracted records ·{" "}
                              {date(j.created)}
                            </span>
                          </div>
                          <Status value="review" />
                          <ArrowRight aria-hidden="true" size={18} />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      title="No Pending Matches"
                      description="Import a historical document to compare its identities against the committed dataset."
                      action={
                        <button onClick={() => switchTab("uploads")}>
                          Import Documents
                        </button>
                      }
                    />
                  )}
                </section>

                <section hidden={tab !== "people"} className="view">
                  <div className="filters">
                    <label className="search-field">
                      <Search size={17} aria-hidden="true" />
                      <span className="sr-only">Search Profiles</span>
                      <input
                        name="profile-search"
                        autoComplete="off"
                        placeholder="Search names, identifiers or cases…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </label>
                    <label>
                      Source-Supported Role
                      <select
                        name="role-filter"
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                      >
                        <option value="">All Roles</option>
                        {[
                          "suspect",
                          "witness",
                          "victim",
                          "investigator",
                          "unknown",
                          "recorded offender",
                        ].map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="panel directory">
                    {filteredPeople.length ? (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Person</th>
                              <th>Canonical ID</th>
                              <th>Recorded Roles</th>
                              <th>Sources</th>
                              <th>Details</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredPeople.map((p) => (
                              <tr key={p.id}>
                                <td>
                                  <div className="person-cell">
                                    <span className="avatar">
                                      {p.name
                                        .split(" ")
                                        .map((n) => n[0])
                                        .slice(0, 2)
                                        .join("")}
                                    </span>
                                    <strong>{p.name}</strong>
                                  </div>
                                </td>
                                <td className="mono" translate="no">
                                  {p.id}
                                </td>
                                <td>
                                  {p.roles.map((r) => (
                                    <Status key={r} value={r} />
                                  ))}
                                </td>
                                <td>{p.source_count}</td>
                                <td>
                                  <button
                                    className="text-action"
                                    onClick={() => setPerson(p)}
                                  >
                                    View Profile{" "}
                                    <ArrowUpRight
                                      size={15}
                                      aria-hidden="true"
                                    />
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <Empty
                        title="No Matching Profiles"
                        description="Change your search or commit supported identities from a document import."
                      />
                    )}
                  </div>
                  <p className="muted">
                    Showing up to 200 profiles. Facts and identifiers are
                    searchable; names never determine guilt.
                  </p>
                </section>

                <section hidden={tab !== "graph"} className="view">
                  {visitedGraph && (
                    <Suspense
                      fallback={
                        <div className="loading">Loading Graph Explorer…</div>
                      }
                    >
                      <GraphView
                        active={tab === "graph"}
                        revision={dashboard?.revision ?? 0}
                        onEvidence={setFact}
                        report={report}
                      />
                    </Suspense>
                  )}
                </section>

                <section hidden={tab !== "evidence"} className="view">
                  <label className="search-field">
                    <Search size={17} aria-hidden="true" />
                    <span className="sr-only">Search Evidence</span>
                    <input
                      name="evidence-search"
                      autoComplete="off"
                      placeholder="Search values, files or review states…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <div className="panel evidence-grid">
                    {filteredClaims.length ? (
                      filteredClaims.map((c) => (
                        <button
                          className="evidence-item"
                          key={c.id}
                          onClick={() => setFact(c)}
                        >
                          <div>
                            <span className="eyebrow">{label(c.field)}</span>
                            <strong>{c.value}</strong>
                            <span>
                              {c.filename} ·{" "}
                              {c.page ? `Page ${c.page}` : `Row ${c.row}`}
                            </span>
                          </div>
                          <Status value={c.review_state} />
                          <ArrowUpRight size={18} aria-hidden="true" />
                        </button>
                      ))
                    ) : (
                      <Empty
                        title="No Evidence Found"
                        description="Upload records or adjust your search. Original and superseded claims remain available for audit."
                      />
                    )}
                  </div>
                  <p className="muted">
                    Displaying up to 500 claims, including proposed and
                    superseded evidence.
                  </p>
                </section>

                <section hidden={tab !== "cases"} className="view">
                  {cases.length ? (
                    <div className="cases-grid">
                      {cases.map((c) => (
                        <article className="panel case-card" key={c.reference}>
                          <Folder size={26} aria-hidden="true" />
                          <span className="eyebrow">
                            Source-Supported Case Reference
                          </span>
                          <h2>{c.reference}</h2>
                          <div className="case-counts">
                            <span>{c.people.length} people</span>
                            <span>{c.documents.length} documents</span>
                          </div>
                          <div className="case-people">
                            {c.people.map((id) => (
                              <button
                                key={id}
                                onClick={() =>
                                  api<Person>(
                                    "/people/" + encodeURIComponent(id),
                                  )
                                    .then(setPerson)
                                    .catch((e) => report(e.message))
                                }
                              >
                                {people.find((p) => p.id === id)?.name ?? id}
                                <ArrowUpRight size={14} aria-hidden="true" />
                              </button>
                            ))}
                          </div>
                          {c.evidence.map((id) => (
                            <button
                              className="source-link"
                              key={id}
                              onClick={() =>
                                api<Fact>("/evidence/" + id)
                                  .then(setFact)
                                  .catch((e) => report(e.message))
                              }
                            >
                              Case Evidence {id.slice(-6)} ↗
                            </button>
                          ))}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      title="No Cases Recorded"
                      description="Case references appear here when supported source records are committed."
                    />
                  )}
                </section>

                <section hidden={tab !== "audit"} className="view">
                  <div className="panel audit-list">
                    {audit.length ? (
                      audit.map((a) => (
                        <article key={a.id} className="audit-event">
                          <span className="audit-dot" />
                          <div>
                            <div>
                              <strong>{label(a.action)}</strong>
                              <span className="muted">{date(a.time)}</span>
                            </div>
                            <p>{a.reason}</p>
                            <span className="muted">
                              {a.actor} {a.job_id ? `· ${a.job_id}` : ""}
                            </span>
                            {a.result && (
                              <div className="result-summary">
                                {Object.entries(a.result).map(([k, v]) => (
                                  <span key={k}>
                                    {label(k)}: {v}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          {a.action === "commit" && (
                            <button
                              disabled={a.undone || !a.changes?.length}
                              onClick={() => setPendingUndo(a)}
                            >
                              {a.undone ? "Undone" : "Undo / Split"}
                            </button>
                          )}
                        </article>
                      ))
                    ) : (
                      <Empty
                        title="No Decisions Yet"
                        description="Uploads, corrections, approvals, commits and reversals appear here."
                      />
                    )}
                  </div>
                </section>

                <section hidden={tab !== "settings"} className="view">
                  <div className="settings-grid">
                    <section className="panel">
                      <span className="eyebrow">Storage & Processing</span>
                      <h2>Your Local Workspace</h2>
                      <dl className="detail-list">
                        <dt>Database</dt>
                        <dd>{health?.backend ?? "Unavailable"}</dd>
                        <dt>Extraction Provider</dt>
                        <dd>
                          Local PDF text, Tesseract OCR & conservative labelled
                          extraction
                        </dd>
                        <dt>Identity Threshold</dt>
                        <dd>
                          {health?.auto_threshold ?? 80} weighted points; not a
                          probability
                        </dd>
                        <dt>Automatic Enrichment</dt>
                        <dd>
                          Existing profile ID, or name plus at least 2
                          independent corroborating identity attributes;
                          contradictions block automatic matching
                        </dd>
                        <dt>Cloud Processing</dt>
                        <dd>Disabled. No files are sent to paid APIs.</dd>
                        <dt>Reviewer</dt>
                        <dd>{actor}</dd>
                      </dl>
                      <p>
                        Configure database and matching thresholds in the
                        backend environment. Credentials remain on the backend.
                      </p>
                    </section>
                    <section className="panel">
                      <span className="eyebrow">Demo & Accessibility</span>
                      <h2>Test the Complete Workflow</h2>
                      <p>
                        Seed fictional profiles, upload a sample, review
                        identities, commit supported changes and inspect graph
                        evidence.
                      </p>
                      {health?.demo && (
                        <div className="stack">
                          <button
                            disabled={busy}
                            onClick={() =>
                              run(
                                () => api("/demo/seed", {}),
                                "Synthetic dataset is ready.",
                              )
                            }
                          >
                            Load Synthetic Seed Dataset
                          </button>
                          <a
                            className="link-button"
                            href="/api/demo/samples"
                            download
                          >
                            Download Sample Files{" "}
                            <ArrowDownToLine size={16} aria-hidden="true" />
                          </a>
                        </div>
                      )}
                      <p className="muted">
                        Reduced motion follows your operating system preference.
                        Every graph interaction has a keyboard-accessible list
                        or button alternative.
                      </p>
                      <button onClick={() => setEntered(false)}>
                        Return to Welcome
                      </button>
                    </section>
                  </div>
                </section>
                <footer className="workspace-footer">
                  <span>
                    <ShieldCheck size={14} aria-hidden="true" />
                    Evidence-linked investigation support
                  </span>
                  <span>Team NULLVERSE / Dev2Hack</span>
                </footer>
              </main>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {person && (
        <Dialog title={person.name} onClose={() => setPerson(null)}>
          <div className="profile-id mono" translate="no">
            {person.id}
          </div>
          <div className="role-row">
            {person.roles.map((r) => (
              <Status key={r} value={r} />
            ))}
          </div>
          <p>
            {person.source_count} source documents · {person.facts.length}{" "}
            sourced facts
          </p>
          <h3>Supported Facts & Conflicting Claims</h3>
          <div className="sourced-facts">
            {person.facts.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setPerson(null);
                  setFact(c);
                }}
              >
                <span>{label(c.field)}</span>
                <strong>{c.value}</strong>
                <small>
                  {c.filename} · {c.page ? `Page ${c.page}` : `Row ${c.row}`}
                </small>
                <ArrowUpRight size={15} aria-hidden="true" />
              </button>
            ))}
          </div>
        </Dialog>
      )}
      {fact && <EvidenceDrawer fact={fact} onClose={() => setFact(null)} />}
      {pendingUndo && (
        <Dialog
          title="Undo Commit / Split Claims"
          onClose={() => setPendingUndo(null)}
        >
          <p>
            Return {pendingUndo.changes?.length} records to review. Original
            evidence stays intact, and later commits remain attached to their
            profiles.
          </p>
          <label>
            Reviewer
            <input
              name="undo-reviewer"
              autoComplete="name"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
            />
          </label>
          <label>
            Reason
            <input
              name="undo-reason"
              autoComplete="off"
              placeholder="Why should these claims be separated…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await api("/audit/" + pendingUndo.id + "/undo", {
                  actor,
                  reason,
                });
                setPendingUndo(null);
              }, "Commit undone; evidence preserved.")
            }
          >
            Confirm Undo
          </button>
        </Dialog>
      )}
    </>
  );
}

function JobTable({ jobs, open }: { jobs: Job[]; open: (id: string) => void }) {
  return jobs.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Document</th>
            <th>Imported</th>
            <th>Status</th>
            <th>Review</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>
                <div className="document-cell">
                  <span className="file-icon">
                    <FileText size={18} aria-hidden="true" />
                  </span>
                  <div>
                    <strong>{job.filename}</strong>
                    <small>
                      {job.filename.split(".").pop()?.toUpperCase()} · Local
                      Extraction
                    </small>
                  </div>
                </div>
              </td>
              <td className="muted">{date(job.created)}</td>
              <td>
                <Status value={job.status} />
              </td>
              <td>
                <button
                  className="icon-button"
                  aria-label={"Review " + job.filename}
                  onClick={() => open(job.id)}
                >
                  <ArrowUpRight size={18} aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty
      title="Your First Source Starts Here"
      description="Import a historical document to begin building a sourced investigation."
    />
  );
}

function ColumnMapping({
  job,
  busy,
  save,
}: {
  job: Job;
  busy: boolean;
  save: (mapping: Record<string, string>) => void;
}) {
  const [mapping, setMapping] = useState(job.mapping);
  useEffect(() => setMapping(job.mapping), [job.id, job.mapping]);
  return (
    <details className="mapping" open>
      <summary>CSV Column Mapping & Preview</summary>
      <p>
        Map source columns before committing. Identifiers are retained as
        strings.
      </p>
      <div className="mapping-grid">
        {job.headers.map((header) => (
          <label key={header}>
            {header}
            <select
              name={"map-" + header}
              value={mapping[header] ?? ""}
              onChange={(e) =>
                setMapping((m) => {
                  const n = { ...m };
                  if (e.target.value) n[header] = e.target.value;
                  else delete n[header];
                  return n;
                })
              }
            >
              <option value="">Ignore Column</option>
              {fields.map((field) => (
                <option key={field} value={field}>
                  {label(field)}
                </option>
              ))}
            </select>
            <small>
              Preview: {String(job.records[0]?.original[header] ?? "Blank")}
            </small>
          </label>
        ))}
      </div>
      <button disabled={busy} onClick={() => save(mapping)}>
        Apply Column Mapping
      </button>
    </details>
  );
}

function RecordReview({
  record,
  sourcePage,
  people,
  onEvidence,
  onEvidenceById,
  busy,
  decide,
}: {
  record: ImportRecord;
  sourcePage?: { jobId: string; width?: number; height?: number };
  people: Person[];
  onEvidence: (fact: Fact) => void;
  onEvidenceById: (id: string) => void;
  busy: boolean;
  decide: (
    r: ImportRecord,
    a: string,
    t: string | null,
    c?: Record<string, string | null>,
  ) => Promise<boolean>;
}) {
  const [target, setTarget] = useState(
      record.recommendation.target ??
        record.recommendation.candidates[0]?.person_id ??
        "",
    ),
    [correcting, setCorrecting] = useState(false),
    [corrected, setCorrected] = useState(record.values);
  const action =
    record.decision?.action ?? record.outcome ?? record.recommendation.action;
  return (
    <article className="review-record">
      <div className="record-header">
        <div>
          <span className="eyebrow">
            {record.page ? `Page ${record.page}` : `CSV Row ${record.row}`} ·{" "}
            {label(record.method)}
          </span>
          <h3>{record.values.name ?? "Unresolved Identifier Mention"}</h3>
        </div>
        <Status
          value={
            record.blank ? "blank" : record.duplicate ? "duplicate" : action
          }
        />
      </div>
      {record.blank || record.duplicate ? (
        <p className="muted">
          {record.blank
            ? "Blank row: no identity or fact will be invented."
            : "Duplicate row: retained for source traceability and skipped at commit."}
        </p>
      ) : (
        <>
          <div className="source-comparison">
            <section>
              <span className="eyebrow">Original Source</span>
              {record.text ? (
                <>
                  <img
                    className="source-page-image"
                    src={`/api/imports/${sourcePage?.jobId}/pages/${record.page}.png`}
                    width={sourcePage?.width ?? 595}
                    height={sourcePage?.height ?? 842}
                    loading="lazy"
                    alt={`Original source document page ${record.page}. Extracted text follows.`}
                  />
                  <details>
                    <summary>Extracted Page Text</summary>
                    <pre>{record.text}</pre>
                  </details>
                </>
              ) : (
                <dl>
                  {Object.entries(record.original).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{value || "Blank"}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
            <section>
              <span className="eyebrow">Extracted & Normalised Facts</span>
              {record.facts?.map((fact) => (
                <button
                  className="extracted-fact"
                  key={fact.id}
                  onClick={() => onEvidence(fact)}
                >
                  <span>{label(fact.field)}</span>
                  <strong>{fact.value}</strong>
                  <small>{fact.normalized}</small>
                  <ArrowUpRight size={14} aria-hidden="true" />
                </button>
              ))}
              <p className="muted">{record.recommendation.reason}</p>
            </section>
          </div>
          {record.recommendation.candidates.length > 0 && (
            <div className="candidate-list">
              <span className="eyebrow">
                Existing Profile Candidates · Weighted Score
              </span>
              {record.recommendation.candidates.map((c) => (
                <div className="candidate" key={c.person_id}>
                  <div>
                    <strong>{c.name}</strong>
                    <span className="mono">{c.person_id}</span>
                    <b>{c.score} points</b>
                  </div>
                  <p className="matching">
                    <Check size={13} aria-hidden="true" />
                    Matching: {c.matching.map(label).join(", ") || "None"}
                  </p>
                  <p className="conflicting">
                    Conflicting: {c.conflicting.map(label).join(", ") || "None"}
                  </p>
                  <p className="muted">
                    Missing: {c.missing.map(label).join(", ") || "None"}
                  </p>
                  <div className="candidate-sources">
                    {Object.entries(c.sources).map(([field, ids]) => (
                      <span key={field}>
                        {ids.map((id, index) => (
                          <button
                            className="source-link"
                            key={id}
                            onClick={() => onEvidenceById(id)}
                          >
                            {label(field)} · source {index + 1} ↗
                          </button>
                        ))}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          {!record.committed && (
            <>
              <div className="record-actions">
                <label>
                  Existing Profile
                  <select
                    name={"target-" + record.id}
                    value={target}
                    onChange={(e) => setTarget(e.target.value)}
                  >
                    <option value="">Select Merge Target</option>
                    {people.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.id}
                      </option>
                    ))}
                  </select>
                </label>
                <div>
                  <button
                    disabled={busy || !target}
                    onClick={() => decide(record, "merge", target)}
                  >
                    Merge
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => decide(record, "separate", null)}
                  >
                    Keep Separate
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => decide(record, "create", null)}
                  >
                    Create New Profile
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => decide(record, "defer", null)}
                  >
                    Defer
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setCorrecting((v) => !v);
                      setCorrected(record.values);
                    }}
                  >
                    Correct Extraction
                  </button>
                </div>
              </div>
              {correcting && (
                <form
                  className="correction-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    decide(record, "correct", null, corrected).then((saved) => {
                      if (saved) setCorrecting(false);
                    });
                  }}
                >
                  <h4>Correct Against the Original Source</h4>
                  <div className="mapping-grid">
                    {fields.map((field) => (
                      <label key={field}>
                        {label(field)}
                        <input
                          name={"correct-" + field}
                          autoComplete="off"
                          value={corrected[field] ?? ""}
                          onChange={(e) =>
                            setCorrected((v) => ({
                              ...v,
                              [field]: e.target.value || null,
                            }))
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <button type="submit" disabled={busy}>
                    Save Corrected Extraction
                  </button>
                </form>
              )}
            </>
          )}
          {record.decision && (
            <p className="notice">
              Decision: {label(record.decision.action)} ·{" "}
              {record.decision.actor} · {record.decision.reason}
            </p>
          )}
        </>
      )}
    </article>
  );
}
