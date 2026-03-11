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

## Deploy To Azure Web App (From Git)

This repo is ready to deploy to **Azure App Service (Linux, Python)** directly from GitHub.

### 1. Push code to GitHub

Make sure your latest changes (including `requirements.txt`) are committed and pushed.

### 2. Create the Web App

In Azure Portal:

1. Create a **Web App**
2. Publish: `Code`
3. Runtime stack: `Python 3.11` (or newer supported version)
4. Operating System: `Linux`

### 3. Configure startup command

In Web App -> **Configuration** -> **General settings** -> **Startup Command**, set:

```bash
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

### 4. Configure environment variables

In Web App -> **Configuration** -> **Application settings**, add:

- `SECRET_KEY` = (strong random value)

If using a managed database (PostgreSQL):

- `DATABASE_URL` = (your Azure PostgreSQL connection string)

If using Azure Blob as file-backed database (no DB server):

- `ODYSSEY_BLOB_CONNECTION_STRING` = (storage account connection string)
- `ODYSSEY_BLOB_CONTAINER` = (container name, example: `odyssey-data`)
- `ODYSSEY_BLOB_NAME` = `odyssey.db` (or another blob file name)

Optional for blob mode:

- `ODYSSEY_LOCAL_DB_PATH` = `/home/odyssey-data/odyssey.db`
- `ODYSSEY_BLOB_SYNC_INTERVAL_SECONDS` = `5`

Optional but recommended:

- `SCM_DO_BUILD_DURING_DEPLOYMENT` = `true`

### 5. Connect GitHub for continuous deployment

In Web App -> **Deployment Center**:

1. Source: `GitHub`
2. Authorize and select your repository + branch
3. Save

Azure will create a GitHub Actions workflow and auto-deploy on every push to that branch.

### 6. Run database migration on Azure

After first deployment, open **SSH** from the Web App (or use Kudu console) and run:

```bash
flask db upgrade
```

If you want seed data in the hosted environment:

```bash
flask seed
```

If you are in Blob-backed SQLite mode, force an upload after migration/seed:

```bash
flask sync-db-blob
```

### 7. Verify deployment

- Open `https://<your-app-name>.azurewebsites.net`
- Check **Log stream** in Azure Portal if startup fails
- Confirm login and dashboard routes load

## Notes

- Blob-backed SQLite is supported in this app when `ODYSSEY_BLOB_CONNECTION_STRING` and `ODYSSEY_BLOB_CONTAINER` are set.
- In blob mode, app startup downloads `odyssey.db` from blob (if present) and uploads updates after requests that modify data.
- The app also uploads in CLI flows (`flask seed`, `flask reset-db`) and supports manual upload via `flask sync-db-blob`.
- Blob-backed SQLite is best for low-concurrency/single-instance usage. If you scale out to multiple app instances, use PostgreSQL.
- This repo still contains `vercel.json`; Azure App Service ignores it.
