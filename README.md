# Odyssey

Odyssey is a lightweight Flask app for staffing operations, CoE economics, and governance.

## Tech Stack

- Python 3.11+
- Flask + Blueprints
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-WTF (CSRF)
- Flask-Login
- SQLite by default (`DATABASE_URL` override supported)
- Bootstrap 5 + custom CSS

## Quick Start

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
export SECRET_KEY='change-this-in-production'
# Optional: export DATABASE_URL='sqlite:///odyssey.db'
```

4. Apply migrations:

```bash
flask db upgrade
```

5. Seed master data:

```bash
flask seed
```

6. Run:

```bash
flask run
```

Open `http://127.0.0.1:5000`.

## Login

- Default seeded account: `mgr1@local` / `manager123`
- Reset manager accounts are also available via:

```bash
flask reset-db --all
```

## Master Data (Admin)

Use the top-nav `Master Data` section:

- Team Members: `/members`
- Teams: `/teams`
- Team Memberships: from each Team detail page (`/teams/<id>`)
- Projects: `/projects` (Team required for active projects)
- Cost Rates: `/admin/cost-rates`
- Client Billing Rates: `/admin/client-billing-rates`
- Non-Client Billing Config: `/admin/nonclient-config`
- Legacy Rate Cards (deprecated): `/rates`

## Billing Logic (Current)

Billing is now driven by **Billable FTE per Project per Day** (`ProjectDayBilling`).

1. Daily project revenue
- If `override_daily_revenue` is set, that value is used.
- Else for client-billed projects, lookup `ClientBillingRate` by `(region, cadence='Daily', fte_point)`.
- If exact FTE point does not exist, linear interpolation is used.
- If outside configured FTE range, revenue prorates from max point using `amount_max * (billable_fte / fte_max)`.
- For non-client case types, revenue uses `base_daily_rate_for_4_5 * (billable_fte / 4.5)`.

2. Revenue allocation to worklog rows
- For each project-day, revenue is split by row hours proportion: `row.hours / total_project_hours`.
- If `total_project_hours` is zero, all row shares are zero.

3. Cost per worklog row
- Member levels are normalized (`Manager3 -> Manager`, `ProjectLeader2 -> Project Leader`, etc.).
- Cost is computed from `CostRate.cost_per_day / 8` and multiplied by row hours.

## Team Derivation Logic

Worklog rows no longer require manual team entry.

- Team is derived from `TeamMembership` effective dates:
- active when `start_date <= work_date <= end_date` (or open-ended if no end date)
- If no active membership exists for that date, UI shows `Unassigned` warning.

## Daily Staffing API Contract

- `GET /worklogs/data?date=YYYY-MM-DD`
- returns `worklogs`, derived team info, `projects_used`, `project_day_billing`, and computed previews
- `POST /worklogs/bulk_save`
- accepts `worklogs[]` and `project_day_billing[]`
- validates hours and billable FTE increments (`0.5`)
- saves worklogs + project-day billing in one transaction

## Quick Test Scenario

1. Run `flask db upgrade && flask seed`.
2. Log in and open Daily Staffing.
3. Add a project work row for a member and save once.
4. In `Billing for Selected Date`, set Billable FTE (for example `3.5`) and save.
5. Reload the date and verify:
- derived team appears for each row
- computed revenue appears in billing panel
- row revenue shares and row costs are populated
6. Edit team membership dates under `/teams/<id>` and reload the same work date to verify team derivation changes.
