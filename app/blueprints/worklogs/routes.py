from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from ...billing import (
    compute_project_day_revenue,
    compute_worklog_cost,
    is_half_step,
    team_for_member_on,
    to_float,
)
from ...extensions import db
from ...models import Project, ProjectDayBilling, TeamMember, WorkLog, WORK_CATEGORY_CHOICES


worklogs_bp = Blueprint("worklogs", __name__)


def _to_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


def _manager_scope(query):
    return query.filter(
        or_(
            WorkLog.manager_user_id == current_user.id,
            and_(WorkLog.manager_user_id.is_(None), WorkLog.manager_name == current_user.full_name),
        )
    )


def _derive_team_for_row(team_member_id: int, selected_date: date) -> tuple[str, bool]:
    membership = team_for_member_on(team_member_id, selected_date)
    if not membership:
        return "Unassigned", True
    return membership.team.name, False


def _serialize_row(log: WorkLog, selected_date: date) -> dict:
    team_name, team_warning = _derive_team_for_row(log.team_member_id, selected_date)
    return {
        "id": log.id,
        "team_member_id": log.team_member_id,
        "work_category": log.work_category,
        "project_id": log.project_id,
        "hours": float(log.hours or 0),
        "derived_team_name": team_name,
        "team_warning": team_warning,
        "billing_manager_name": log.billing_manager_name,
    }


def _serialize_prefill_row(source: WorkLog, selected_date: date) -> dict:
    draft = WorkLog(
        work_date=selected_date,
        manager_name=current_user.full_name,
        manager_user_id=current_user.id,
        team_member_id=source.team_member_id,
        work_category=source.work_category,
        project_id=source.project_id,
        hours=source.hours,
        billing_manager_name=source.billing_manager_name,
    )
    row = _serialize_row(draft, selected_date)
    row["id"] = None
    return row


def _project_billing_payload(selected_date: date, rows: list[dict]) -> tuple[list[dict], dict[int, Decimal]]:
    project_ids = sorted({int(row["project_id"]) for row in rows if row.get("project_id")})
    if not project_ids:
        return [], {}

    projects = {
        project.id: project
        for project in Project.query.filter(Project.id.in_(project_ids)).order_by(Project.case_code.asc()).all()
    }
    billings = {
        billing.project_id: billing
        for billing in ProjectDayBilling.query.filter(
            ProjectDayBilling.work_date == selected_date,
            ProjectDayBilling.project_id.in_(project_ids),
        ).all()
    }

    worklogs_by_project = defaultdict(list)
    for row in rows:
        if not row.get("project_id"):
            continue
        worklogs_by_project[int(row["project_id"])].append(row)

    payload = []
    revenues = {}
    for project_id in project_ids:
        project = projects.get(project_id)
        if not project:
            continue
        billing = billings.get(project_id)
        result = compute_project_day_revenue(project, billing)
        revenues[project_id] = result.amount
        payload.append(
            {
                "project_id": project.id,
                "case_code": project.case_code,
                "description": project.description,
                "region": project.region,
                "case_type": project.case_type,
                "billable_fte": to_float(Decimal(str(billing.billable_fte))) if billing else None,
                "billing_manager_name": (billing.billing_manager_name if billing else "") or current_user.full_name,
                "override_daily_revenue": to_float(Decimal(str(billing.override_daily_revenue)))
                if billing and billing.override_daily_revenue is not None
                else None,
                "notes": billing.notes if billing else "",
                "computed_daily_revenue": to_float(result.amount),
                "warning": result.warning,
                "total_project_hours": float(sum(float(r.get("hours") or 0) for r in worklogs_by_project[project_id])),
            }
        )

    return payload, revenues


def _apply_allocations(rows: list[dict], project_revenues: dict[int, Decimal], selected_date: date) -> list[dict]:
    by_project = defaultdict(list)
    response_rows = []

    for row in rows:
        row_copy = dict(row)
        row_copy["revenue_share"] = 0.0
        row_copy["row_cost"] = 0.0
        if row_copy.get("project_id") and row_copy.get("work_category") == "Project":
            by_project[int(row_copy["project_id"])].append(row_copy)
        response_rows.append(row_copy)

    for project_id, project_rows in by_project.items():
        total_hours = Decimal(str(sum(float(item.get("hours") or 0) for item in project_rows)))
        revenue = project_revenues.get(project_id, Decimal("0"))
        for item in project_rows:
            item["revenue_share"] = (
                to_float(revenue * (Decimal(str(item.get("hours") or 0)) / total_hours)) if total_hours > 0 else 0.0
            )

    member_ids = {int(row["team_member_id"]) for row in response_rows if row.get("team_member_id")}
    members = {member.id: member for member in TeamMember.query.filter(TeamMember.id.in_(member_ids)).all()}

    for row in response_rows:
        member = members.get(int(row["team_member_id"])) if row.get("team_member_id") else None
        if not member:
            continue
        temp_log = WorkLog(
            work_date=selected_date,
            team_member_id=member.id,
            hours=float(row.get("hours") or 0),
            team_member=member,
        )
        row["row_cost"] = to_float(compute_worklog_cost(temp_log))

    return response_rows


@worklogs_bp.route("/")
@login_required
def daily_staffing():
    selected_date = _to_date(request.args.get("date", date.today().isoformat()))
    members = TeamMember.query.filter_by(is_active=True).order_by(TeamMember.name.asc()).all()
    projects = Project.query.filter_by(is_active=True).order_by(Project.case_code.asc()).all()

    member_options = [{"id": m.id, "label": f"{m.name} ({m.employee_id})"} for m in members]
    project_options = [
        {
            "id": p.id,
            "case_code": p.case_code,
            "description": p.description,
            "case_type": p.case_type,
            "region": p.region,
            "label": f"{p.case_code} - {p.description}",
        }
        for p in projects
    ]

    return render_template(
        "worklogs/index.html",
        selected_date=selected_date,
        member_options=member_options,
        project_options=project_options,
        work_categories=WORK_CATEGORY_CHOICES,
    )


@worklogs_bp.route("/worklogs/data")
@login_required
def worklogs_data():
    selected_date = _to_date(request.args.get("date", date.today().isoformat()))
    force_prefill = request.args.get("force_prefill") == "1"

    existing_rows = _manager_scope(
        WorkLog.query.options(joinedload(WorkLog.project)).filter(WorkLog.work_date == selected_date)
    ).order_by(WorkLog.created_at.asc()).all()

    rows = []
    prefilled_from = None

    if existing_rows and not force_prefill:
        rows = [_serialize_row(log, selected_date) for log in existing_rows]
    else:
        prior_date = (
            _manager_scope(WorkLog.query)
            .filter(WorkLog.work_date < selected_date)
            .order_by(WorkLog.work_date.desc())
            .with_entities(WorkLog.work_date)
            .first()
        )
        if prior_date:
            src_date = prior_date[0]
            src_rows = _manager_scope(
                WorkLog.query.options(joinedload(WorkLog.project)).filter(WorkLog.work_date == src_date)
            ).order_by(WorkLog.created_at.asc()).all()
            rows = [_serialize_prefill_row(log, selected_date) for log in src_rows]
            prefilled_from = src_date.isoformat()

    project_day_billing, project_revenues = _project_billing_payload(selected_date, rows)
    rows_with_alloc = _apply_allocations(rows, project_revenues, selected_date)

    projects_used = [
        {
            "project_id": item["project_id"],
            "case_code": item["case_code"],
            "description": item["description"],
            "case_type": item["case_type"],
            "region": item["region"],
        }
        for item in project_day_billing
    ]

    return jsonify(
        {
            "work_date": selected_date.isoformat(),
            "worklogs": rows_with_alloc,
            "prefilled_from": prefilled_from,
            "projects_used": projects_used,
            "project_day_billing": project_day_billing,
        }
    )


@worklogs_bp.route("/worklogs/bulk_save", methods=["POST"])
@login_required
def bulk_save_worklogs():
    payload = request.get_json(silent=True) or {}
    selected_date = _to_date(payload.get("work_date", date.today().isoformat()))
    incoming_rows = payload.get("worklogs", [])
    incoming_project_day_billing = payload.get("project_day_billing", [])

    if not isinstance(incoming_rows, list) or not isinstance(incoming_project_day_billing, list):
        return jsonify({"ok": False, "message": "Invalid payload."}), 400

    existing_rows = _manager_scope(WorkLog.query.filter(WorkLog.work_date == selected_date)).order_by(WorkLog.id.asc()).all()
    existing_map = {row.id: row for row in existing_rows}

    incoming_ids = set()
    validated_rows = []
    project_hours = defaultdict(float)

    for idx, row in enumerate(incoming_rows, start=1):
        try:
            row_id = int(row.get("id")) if row.get("id") else None
        except (TypeError, ValueError):
            row_id = None

        try:
            hours = float(row.get("hours", 0))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "message": f"Row {idx}: invalid hours."}), 400

        if hours <= 0 or hours > 24:
            return jsonify({"ok": False, "message": f"Row {idx}: hours must be > 0 and <= 24."}), 400

        try:
            team_member_id = int(row.get("team_member_id"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "message": f"Row {idx}: invalid team member."}), 400

        team_member = db.session.get(TeamMember, team_member_id)
        if not team_member:
            return jsonify({"ok": False, "message": f"Row {idx}: team member not found."}), 400

        work_category = (row.get("work_category") or "Project").strip()
        if work_category not in WORK_CATEGORY_CHOICES:
            return jsonify({"ok": False, "message": f"Row {idx}: invalid work type."}), 400

        project_id = row.get("project_id")
        if work_category == "Project":
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "message": f"Row {idx}: project is required for project work."}), 400
            if not db.session.get(Project, project_id):
                return jsonify({"ok": False, "message": f"Row {idx}: project not found."}), 400
            project_hours[project_id] += hours
        else:
            project_id = None

        billing_manager_name = (row.get("billing_manager_name") or "").strip() or current_user.full_name
        derived_team_name, _ = _derive_team_for_row(team_member_id, selected_date)

        validated_rows.append(
            {
                "id": row_id,
                "team_member_id": team_member_id,
                "work_category": work_category,
                "project_id": project_id,
                "hours": hours,
                "team_name": derived_team_name if derived_team_name != "Unassigned" else None,
                "billing_manager_name": billing_manager_name,
            }
        )
        if row_id:
            incoming_ids.add(row_id)

    billing_by_project = {}
    for idx, item in enumerate(incoming_project_day_billing, start=1):
        try:
            project_id = int(item.get("project_id"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "message": f"Billing row {idx}: invalid project."}), 400

        fte_raw = item.get("billable_fte")
        if fte_raw in (None, ""):
            billing_by_project[project_id] = None
            continue

        if not is_half_step(fte_raw):
            return jsonify({"ok": False, "message": f"Billing row {idx}: billable FTE must be in increments of 0.5."}), 400

        billable_fte = Decimal(str(fte_raw))
        if billable_fte <= 0:
            return jsonify({"ok": False, "message": f"Billing row {idx}: billable FTE must be greater than 0."}), 400

        override_value = item.get("override_daily_revenue")
        override = Decimal(str(override_value)) if override_value not in (None, "") else None

        billing_by_project[project_id] = {
            "billable_fte": billable_fte,
            "billing_manager_name": (item.get("billing_manager_name") or "").strip() or current_user.full_name,
            "override_daily_revenue": override,
            "notes": (item.get("notes") or "").strip() or None,
        }

    for project_id, hours in project_hours.items():
        if hours > 0 and not billing_by_project.get(project_id):
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": f"Billable FTE is required for project {project_id} on {selected_date.isoformat()}.",
                    }
                ),
                400,
            )

    try:
        for existing in existing_rows:
            if existing.id not in incoming_ids:
                db.session.delete(existing)

        for row in validated_rows:
            model = existing_map.get(row["id"]) if row["id"] else None
            if model is None:
                model = WorkLog(work_date=selected_date)
                db.session.add(model)

            model.manager_user_id = current_user.id
            model.manager_name = current_user.full_name
            model.work_date = selected_date
            model.team_member_id = row["team_member_id"]
            model.work_category = row["work_category"]
            model.project_id = row["project_id"]
            model.hours = row["hours"]
            model.team_name = row["team_name"]
            model.billing_manager_name = row["billing_manager_name"]

        project_ids_for_date = set(project_hours.keys())
        existing_billing = {
            row.project_id: row
            for row in ProjectDayBilling.query.filter(
                ProjectDayBilling.work_date == selected_date,
                ProjectDayBilling.project_id.in_(list(project_ids_for_date) or [0]),
            ).all()
        }

        for project_id in project_ids_for_date:
            payload_row = billing_by_project.get(project_id)
            model = existing_billing.get(project_id)

            if not payload_row:
                if model:
                    db.session.delete(model)
                continue

            if not model:
                model = ProjectDayBilling(project_id=project_id, work_date=selected_date)
                db.session.add(model)

            model.billable_fte = payload_row["billable_fte"]
            model.billing_manager_name = payload_row["billing_manager_name"]
            model.billing_manager_user_id = current_user.id
            model.override_daily_revenue = payload_row["override_daily_revenue"]
            model.notes = payload_row["notes"]

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "message": f"Save failed: {exc}"}), 500

    return jsonify({"ok": True, "message": "Timesheet and billing saved."})
