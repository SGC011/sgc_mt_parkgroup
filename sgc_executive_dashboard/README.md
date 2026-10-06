# Executive Command Center

A single, unified, C-level command center covering every business domain
live on an Odoo 19 database — real estate, construction, deals, HR/payroll,
finance/compliance, CRM/sales, learning and more. Built on a provider-registry
architecture: each domain is a self-contained KPI provider that declares the
Odoo module it needs. The aggregator walks the registry at runtime, and any
domain not installed renders as a dormant "opportunity tile" instead of
erroring — so the module degrades gracefully on any Odoo 19 database, not
just one preconfigured install.

## Short description

Unified C-level command center: cross-app KPIs, trend charts, drill-through
and an Application Universe view — degrades gracefully to whatever apps are
actually installed.

## Features

### Shell UX
- Hero KPI band with a Month-to-date / Quarter-to-date / Year-to-date /
  Rolling-12-months period selector and a company selector.
- KPI card grid grouped by provider/domain section.
- Chart.js trend, bar, doughnut and polar-area cards fed by Odoo ORM
  aggregates.
- Drill-through: click a KPI card to open the underlying list/pivot view,
  pre-filtered to that KPI's domain.
- Application Universe: every Odoo application, installed or not; dormant
  apps render as opportunity tiles with a one-click "Activate" action
  (administrators only).

### KPI providers (v1 — each active only if its backing module is installed)
- **Real Estate / Offplan Rental** — units under management, occupancy %,
  offplan sales value (MTD/YTD), active leases, upcoming lease expiries
  (30d); occupancy trend line, sales-by-project bar.
- **Construction Management** — active projects, on-time milestone %,
  budget burn vs. plan, overdue milestones; budget-burn line, milestone
  status stacked bar.
- **Deals Management** — open deal value, stage conversion %, deals closing
  this period, average deal cycle time; pipeline-by-stage funnel.
- **Commission** — commission liability (accrued/unpaid), top 5 earning
  agents, payout run status; commission-by-agent bar.
- **CRM & Sales** — pipeline value, win rate, quotations sent, confirmed
  revenue; revenue trend line, pipeline funnel.
- **Purchase** — open POs, spend (MTD/YTD), average PO cycle time; spend
  trend line.
- **Finance** — net revenue, net profit, cash position, overdue
  receivables, open AML flags, e-invoice compliance rate; P&L trend line,
  AR ageing bar.
- **HR & UAE Payroll** — headcount, current-period payroll run status, WPS
  compliance %, attendance rate, open leave requests, open requisitions;
  headcount trend line.
- **Compliance / KYC** — KYC records complete %, documents expiring (30d),
  pending reviews; expiry countdown list.
- **Projects (general)** — task completion %, overdue tasks, active
  projects; burndown line.
- **Learning & Assessment** — course completion %, certifications issued
  (MTD), average assessment score; completion trend line.
- **Video Conferencing** — meetings held (MTD), total participant-minutes,
  adoption rate (active users / headcount); usage trend line.

### Security
- `Executive Viewer` group — read access to the dashboard.
- `Executive Officer` / system-admin group — additionally can activate a
  dormant application from the Application Universe tile.
- Company-scoped: every provider query filters through the current user's
  allowed companies; no cross-tenant data exposure.

## Installation

1. Copy the module to your Odoo 19 `addons/` path.
2. Update the app list and install `sgc_executive_dashboard`.
3. No hard dependencies on any business module — `base` and `web` only; each
   provider is gated on its own module being installed.

## Usage

Navigate to the **Executive** app (top app bar). Use the period selector and
company selector in the toolbar, browse the **Performance** tab for KPIs and
charts, click any KPI card to drill through to its filtered list/pivot view,
and switch to the **Application Universe** tab to see live vs. dormant apps.

## Configuration

- Assign the `Executive Viewer` security group (Settings → Users) to grant
  dashboard read access.
- No separate settings screen: which providers appear is determined
  automatically by which Odoo modules are installed on the database.

## Technical details

- Odoo version: 19.0.
- Dependencies: `base`, `web` (providers detect their own modules at
  runtime — see feature list above).
- External libraries: Chart.js, loaded from Odoo's bundled
  `web/static/lib/Chart/Chart.js` (no new vendored chart library).
- License: OPL-1.

## Support

Author / Maintainer: SGC TECH AI
Website: https://sgctech.ai
Support: info@sgctech.ai
