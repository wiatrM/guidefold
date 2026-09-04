import { useMemo, useState } from "react";
import {
  ArrowRight, Bank, Bell, Buildings, Check, CheckCircle, Clock, Code, Copy,
  Database, DownloadSimple, FileText, GitBranch, ImageSquare, MagnifyingGlass,
  MapTrifold, Pulse, SealCheck, ShieldCheck, SlidersHorizontal, SpinnerGap,
  SquaresFour, Swatches, UsersThree, WarningCircle, X, XCircle,
} from "@phosphor-icons/react";

const ASSET_ROOT = "/assets/industrial-surveyor";
const palette = [
  ["Graphite", "#0F1418"], ["Stone", "#E6E8EA"], ["Survey teal", "#2BA6A0"],
  ["Safety orange", "#FF6A28"], ["Steel", "#677681"], ["Signal red", "#E24A4A"],
];
const proposals = [
  { name: "Customer Onboarding Checklist", owner: "Riverside Team", division: "Product", updated: "Sep 01, 2026", state: "In review", tone: "review" },
  { name: "Access Request Process", owner: "Northfield Team", division: "Operations", updated: "Aug 30, 2026", state: "Active", tone: "success" },
  { name: "Vendor Risk Policy", owner: "Summit Team", division: "Risk", updated: "Aug 29, 2026", state: "Probationary", tone: "warning" },
  { name: "Incident Response Playbook", owner: "Northfield Team", division: "Security", updated: "Aug 28, 2026", state: "Candidate", tone: "neutral" },
];
const gates = [
  { label: "Schema Check", meta: "Sep 02, 2026", state: "Passed", tone: "success", icon: ShieldCheck },
  { label: "Content Quality", meta: "Sep 03, 2026", state: "Passed", tone: "success", icon: CheckCircle },
  { label: "Policy Compliance", meta: "Sep 03, 2026", state: "Passed", tone: "success", icon: SealCheck },
  { label: "Security Review", meta: "Sep 04, 2026", state: "In review", tone: "review", icon: Clock },
  { label: "Executive Approval", meta: "Waiting", state: "Pending", tone: "neutral", icon: WarningCircle },
];
const provenance = [
  ["Created by Riverside Team", "Aug 28, 2026", "success"],
  ["Validated by Northfield Team", "Aug 31, 2026", "success"],
  ["Under review for Product Division", "Sep 03, 2026", "review"],
  ["Adopted by Division", "Pending", "neutral"],
  ["Standardized by Governance", "Pending", "neutral"],
];

function BrandMark({ size = 44, className = "" }) {
  return <img className={`brand-mark ${className}`} src={`${ASSET_ROOT}/guidefold-mark.png`} alt="Guidefold folded survey-map G" width={size} height={size} />;
}

function StateBadge({ tone = "neutral", children }) {
  return <span className={`state-badge ${tone}`}>{children}</span>;
}

function PanelTitle({ icon: Icon, eyebrow, title, action }) {
  return <div className="panel-title"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{Icon && <Icon aria-hidden="true" weight="regular" />} {title}</h2></div>{action}</div>;
}

function BrandRail() {
  const [density, setDensity] = useState("Balanced");
  return <aside className="brand-rail">
    <div className="brand-lockup large"><BrandMark size={104} /><div><div className="wordmark">Guidefold</div><div className="brand-rule" /><span className="brand-edition">Industrial Surveyor</span></div></div>
    <p className="brand-promise">Route governed knowledge from every team to enterprise standard.</p>
    <section className="rail-section"><h3>Logo system</h3><div className="logo-pair"><div className="logo-sample"><BrandMark size={58} /><span>Primary</span></div><div className="logo-sample stencil"><BrandMark size={58} /><span>Stencil</span></div></div></section>
    <section className="rail-section"><h3>Color palette</h3><div className="palette-grid">{palette.map(([name, value]) => <div className="swatch" key={name}><span className="swatch-color" style={{ backgroundColor: value }} /><b>{name}</b><code>{value}</code></div>)}</div></section>
    <section className="rail-section type-specimen"><h3>Typography</h3><div className="type-row"><strong className="display-sample">AA</strong><div><b>Barlow Condensed</b><span>Operational headings</span></div></div><div className="type-row"><strong className="body-sample">Aa</strong><div><b>Inter</b><span>Interface &amp; data</span></div></div></section>
    <section className="rail-section"><h3>Density &amp; spacing</h3><div className="density-control" role="group" aria-label="Interface density">{["Compact", "Balanced", "Comfortable"].map((item) => <button className={density === item ? "active" : ""} onClick={() => setDensity(item)} key={item}>{item}</button>)}</div><div className="spacing-scale" aria-label="Eight pixel spacing scale">{[8, 16, 24, 32, 48, 64].map((space) => <span key={space}><i style={{ width: Math.max(4, space / 2), height: Math.max(4, space / 2) }} />{space}</span>)}</div></section>
    <div className="rail-coordinate">N 40° 44′ 12″ · E 74° 00′ 21″</div>
  </aside>;
}

function TopBar({ activeView, setActiveView }) {
  const items = [["monitor", "Route monitor", Pulse], ["components", "Component bay", SquaresFour], ["assets", "Asset library", ImageSquare]];
  return <header className="topbar"><div className="mini-brand"><BrandMark size={34} /><span>Guidefold</span></div><nav aria-label="Prototype views">{items.map(([id, label, Icon]) => <button key={id} className={activeView === id ? "active" : ""} onClick={() => setActiveView(id)}><Icon weight="regular" />{label}</button>)}</nav><div className="top-actions"><button className="icon-button" aria-label="Search"><MagnifyingGlass /></button><button className="icon-button notification" aria-label="Notifications"><Bell /><span>3</span></button><button className="avatar" aria-label="Open account menu">AM</button></div></header>;
}

function RouteNode({ type, eyebrow, title, status, date, icon: Icon }) {
  return <div className={`route-node ${type}`}><span className="route-eyebrow">{eyebrow}</span><strong>{title}</strong><div className="node-icon"><Icon weight="regular" /></div><span className="route-dot"><Check weight="bold" /></span><small>{status}<br />{date}</small></div>;
}

function RouteMonitor({ onApprove, status }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => proposals.filter((proposal) => `${proposal.name} ${proposal.owner} ${proposal.division}`.toLowerCase().includes(query.toLowerCase())), [query]);
  return <div className="view monitor-view">
    <div className="page-heading"><div><span className="eyebrow">Promotion control / route 73-A</span><h1>Operational route monitor</h1><p>Team → Division → Company standard</p></div><div className="route-health"><Pulse weight="regular" /><div><span>Route health</span><strong>Healthy</strong><small>All gates normal</small></div></div></div>
    {status === "approved" && <div className="success-banner" role="status"><SealCheck weight="fill" /> Promotion approved. Activation is scheduled for Sep 05, 2026 at 09:00 UTC.</div>}
    <div className="monitor-grid">
      <section className="panel route-panel"><img className="route-art" src={`${ASSET_ROOT}/topographic-route-bg.png`} alt="Dark survey map with topographic contours" /><div className="coordinates"><span>N 40° 44′ 12″</span><span>E 74° 00′ 21″</span></div><div className="route-flow"><RouteNode type="team" eyebrow="Team" title="Riverside Team" status="Validated" date="Sep 02, 2026" icon={UsersThree} /><ArrowRight className="route-arrow" weight="bold" /><RouteNode type="division" eyebrow="Division" title="Product Division" status="Validated" date="Sep 03, 2026" icon={Buildings} /><ArrowRight className="route-arrow" weight="bold" /><RouteNode type="company" eyebrow="Company standard" title="Enterprise Standard" status="Ready" date="Sep 04, 2026" icon={Bank} /></div><div className="route-caption"><MapTrifold /> Promotion path follows validated provenance across three governance layers.</div></section>
      <aside className="panel gate-panel"><PanelTitle icon={ShieldCheck} eyebrow="Automated policy" title="CI / Governance gates" /><div className="gate-list">{gates.map(({ label, meta, state, tone, icon: Icon }) => <div className="gate-row" key={label}><Icon weight="regular" /><div><strong>{label}</strong><small>{meta}</small></div><StateBadge tone={tone}>{state}</StateBadge></div>)}</div><div className="lifecycle"><span>Lifecycle</span><div className="lifecycle-track">{["Candidate", "In review", "Probationary", "Active"].map((item, index) => <div className={index <= (status === "approved" ? 2 : 1) ? "reached" : ""} key={item}><i>{index + 1}</i><small>{item}</small></div>)}</div></div><button className="primary-action" onClick={onApprove} disabled={status === "approved"}>{status === "approved" ? <><CheckCircle weight="fill" /> Approved</> : <><span>Approve promotion</span><ArrowRight weight="bold" /></>}</button></aside>
    </div>
    <div className="detail-grid">
      <section className="panel detail-panel"><PanelTitle icon={FileText} eyebrow="GF-2031" title="Proposal details" /><dl className="definition-list"><div><dt>Knowledge type</dt><dd>Process</dd></div><div><dt>Division</dt><dd>Product</dd></div><div><dt>Proposed by</dt><dd>A. Morgan</dd></div><div><dt>Owner</dt><dd>Riverside Team</dd></div><div><dt>Version</dt><dd>1.3.0</dd></div><div><dt>Last updated</dt><dd>Sep 01, 2026</dd></div></dl><div className="tag-row"><StateBadge>Onboarding</StateBadge><StateBadge>Customer</StateBadge><StateBadge>Checklist</StateBadge></div></section>
      <section className="panel summary-panel"><PanelTitle icon={GitBranch} eyebrow="Selected proposal" title="Customer Onboarding Checklist" /><p>Standardizes customer onboarding steps and ownership across systems, ensuring a consistent, auditable experience from intake to activation.</p><div className="metrics"><div><FileText /><span>Artifacts</span><strong>18</strong></div><div><Database /><span>References</span><strong>24</strong></div><div><ShieldCheck /><span>Checks</span><strong>7</strong></div><div><GitBranch /><span>Policies</span><strong>5</strong></div></div><div className="impact-row"><span>Impact preview</span><b>3 teams</b><b>5 systems</b><b>142 users</b></div></section>
      <section className="panel provenance-panel"><PanelTitle icon={GitBranch} eyebrow="Immutable history" title="Provenance trail" /><ol className="timeline">{provenance.map(([label, date, tone]) => <li className={tone} key={label}><i /><div><strong>{label}</strong><small>{date}</small></div></li>)}</ol></section>
    </div>
    <section className="panel table-panel"><PanelTitle icon={Database} eyebrow="Knowledge inventory" title="Promotion queue" action={<label className="search-field"><MagnifyingGlass /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search proposals" /></label>} /><div className="table-wrap"><table><thead><tr><th>Proposal</th><th>Proposed by</th><th>Division</th><th>Updated</th><th>Status</th></tr></thead><tbody>{filtered.map((proposal) => <tr key={proposal.name}><td>{proposal.name}</td><td>{proposal.owner}</td><td>{proposal.division}</td><td>{proposal.updated}</td><td><StateBadge tone={proposal.tone}>{proposal.state}</StateBadge></td></tr>)}</tbody></table></div></section>
  </div>;
}

function ComponentBay() {
  const [enabled, setEnabled] = useState(true);
  const [copied, setCopied] = useState(false);
  const copyTokens = async () => { await navigator.clipboard?.writeText("--survey-teal: #2BA6A0; --safety-orange: #FF6A28;"); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
  return <div className="view component-view">
    <div className="page-heading"><div><span className="eyebrow">Reusable interface inventory</span><h1>Component bay</h1><p>Operational primitives for dense, regulated workflows.</p></div><button className="secondary-button" onClick={copyTokens}>{copied ? <Check /> : <Copy />}{copied ? "Copied" : "Copy core tokens"}</button></div>
    <div className="component-grid">
      <section className="panel component-panel"><PanelTitle icon={SlidersHorizontal} eyebrow="Actions" title="Buttons" /><div className="component-stack"><button className="primary-action compact">Approve <ArrowRight /></button><button className="secondary-button">Request changes</button><button className="danger-button">Reject</button><button className="text-button">View evidence</button></div></section>
      <section className="panel component-panel"><PanelTitle icon={Code} eyebrow="Inputs" title="Form controls" /><label className="field-label">Proposal name<input className="text-input" defaultValue="Customer Onboarding Checklist" /></label><label className="field-label">Division<select className="text-input" defaultValue="Product"><option>Product</option><option>Security</option><option>Operations</option></select></label><button className={`toggle-row ${enabled ? "on" : ""}`} onClick={() => setEnabled(!enabled)}><span className="toggle"><i /></span><span><strong>Include references</strong><small>Attach validated evidence</small></span></button></section>
      <section className="panel component-panel"><PanelTitle icon={Pulse} eyebrow="Semantics" title="System states" /><div className="state-list"><StateBadge tone="success">Passed</StateBadge><StateBadge tone="review">In review</StateBadge><StateBadge tone="warning">Probationary</StateBadge><StateBadge tone="neutral">Pending</StateBadge><StateBadge tone="danger">Failed</StateBadge></div><div className="inline-alert success"><CheckCircle /> Policy checks passed.</div><div className="inline-alert warning"><WarningCircle /> Human review required.</div><div className="inline-alert danger"><XCircle /> Route blocked by schema.</div></section>
      <section className="panel component-panel wide"><PanelTitle icon={Database} eyebrow="Structured data" title="Compact table" /><div className="table-wrap"><table><thead><tr><th>Control</th><th>Owner</th><th>Evidence</th><th>Status</th></tr></thead><tbody><tr><td>PII handling</td><td>Security</td><td>6 artifacts</td><td><StateBadge tone="success">Passed</StateBadge></td></tr><tr><td>Model evaluation</td><td>AI Platform</td><td>14 runs</td><td><StateBadge tone="review">In review</StateBadge></td></tr><tr><td>Retention policy</td><td>Legal</td><td>3 controls</td><td><StateBadge tone="success">Passed</StateBadge></td></tr></tbody></table></div></section>
      <section className="panel component-panel"><PanelTitle icon={Swatches} eyebrow="Foundation" title="Semantic colors" /><div className="token-list">{palette.map(([name, value]) => <div key={name}><span className="token-chip" style={{ backgroundColor: value }} /><b>{name}</b><code>{value}</code></div>)}</div></section>
    </div>
  </div>;
}

function AssetLibrary() {
  const assets = [
    { name: "Folded survey-map G", file: "guidefold-mark.png", description: "Primary identity asset for navigation, product chrome and app icon.", className: "logo-asset" },
    { name: "Topographic route field", file: "topographic-route-bg.png", description: "Wide art layer beneath the operational promotion route.", className: "wide-asset" },
    { name: "Survey grid pattern", file: "survey-grid-pattern.png", description: "Low-contrast repeatable texture for page and panel surfaces.", className: "pattern-asset" },
  ];
  return <div className="view asset-view"><div className="page-heading"><div><span className="eyebrow">Project-ready raster pack</span><h1>Asset library</h1><p>Independent assets generated from the selected Industrial Surveyor direction.</p></div></div><div className="asset-grid">{assets.map((asset) => <article className="panel asset-card" key={asset.file}><div className={`asset-preview ${asset.className}`}><img src={`${ASSET_ROOT}/${asset.file}`} alt={asset.name} /></div><div className="asset-meta"><div><span className="eyebrow">PNG asset</span><h2>{asset.name}</h2><p>{asset.description}</p></div><a className="secondary-button" href={`${ASSET_ROOT}/${asset.file}`} download><DownloadSimple />Download</a></div></article>)}</div><section className="panel asset-notes"><PanelTitle icon={MapTrifold} eyebrow="Usage rule" title="One map, two information layers" /><p>The map texture carries place and provenance. HTML carries every interactive label, metric and state so the interface remains responsive, accessible and easy to localize.</p></section></div>;
}

function ApprovalDialog({ open, onClose, onConfirm, approving }) {
  if (!open) return null;
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="approval-dialog" role="dialog" aria-modal="true" aria-labelledby="approval-title" onMouseDown={(event) => event.stopPropagation()}><button className="icon-button close-button" onClick={onClose} aria-label="Close"><X /></button><span className="dialog-icon"><ShieldCheck weight="regular" /></span><span className="eyebrow">Final governance action</span><h2 id="approval-title">Approve promotion to Product Division?</h2><p>This moves <strong>Customer Onboarding Checklist v1.3.0</strong> into a 30-day probationary stage and notifies 3 teams.</p><div className="dialog-summary"><span>Required quorum</span><strong>4 / 5 approvals</strong><span>Activation</span><strong>Sep 05, 2026 · 09:00 UTC</strong></div><div className="dialog-actions"><button className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-action compact" onClick={onConfirm} disabled={approving}>{approving ? <><SpinnerGap className="spin" />Promoting…</> : <><ShieldCheck />Confirm approval</>}</button></div></section></div>;
}

export function App() {
  const [activeView, setActiveView] = useState("monitor");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [approvalStatus, setApprovalStatus] = useState("idle");
  const confirmApproval = () => { setApprovalStatus("approving"); window.setTimeout(() => { setApprovalStatus("approved"); setDialogOpen(false); }, 900); };
  return <div className="prototype-shell"><BrandRail /><main className="workspace"><TopBar activeView={activeView} setActiveView={setActiveView} />{activeView === "monitor" && <RouteMonitor onApprove={() => setDialogOpen(true)} status={approvalStatus} />}{activeView === "components" && <ComponentBay />}{activeView === "assets" && <AssetLibrary />}</main><ApprovalDialog open={dialogOpen} onClose={() => approvalStatus !== "approving" && setDialogOpen(false)} onConfirm={confirmApproval} approving={approvalStatus === "approving"} /></div>;
}
