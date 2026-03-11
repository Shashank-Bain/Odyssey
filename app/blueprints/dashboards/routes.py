from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request
from sqlalchemy import and_, func

from ...extensions import db
from ...models import Project, RateCard, TeamMember, User, WorkLog


dashboards_bp = Blueprint("dashboards", __name__, url_prefix="/dashboards")


def _parse_month(month_str: str | None) -> tuple[date, date, str]:
    if month_str:
        try:
            month_start = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
        except ValueError:
            month_start = date.today().replace(day=1)
    else:
        month_start = date.today().replace(day=1)

    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)

    return month_start, next_month, month_start.strftime("%Y-%m")


def _working_days(month_start: date, next_month: date) -> int:
    cursor = month_start
    days = 0
    while cursor < next_month:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


@dashboards_bp.route("/")
def dashboard_home():
    month_start, next_month, month_key = _parse_month(request.args.get("month"))
    working_days = _working_days(month_start, next_month)

    billing_expr = WorkLog.hours * func.coalesce(RateCard.hourly_rate, 0.0)
    by_billing_manager = (
        db.session.query(WorkLog.billing_manager_name, func.sum(billing_expr).label("billing_total"))
        .select_from(WorkLog)
        .join(Project, WorkLog.project_id == Project.id)
        .outerjoin(
            RateCard,
            and_(RateCard.case_type == Project.case_type, RateCard.region == Project.region),
        )
        .filter(WorkLog.work_date >= month_start, WorkLog.work_date < next_month)
        .group_by(WorkLog.billing_manager_name)
        .order_by(func.sum(billing_expr).desc())
        .all()
    )

    manager_identity = func.coalesce(User.full_name, WorkLog.manager_name)
    by_entry_manager = (
        db.session.query(manager_identity.label("manager_name"), func.sum(billing_expr).label("billing_total"))
        .select_from(WorkLog)
        .outerjoin(User, User.id == WorkLog.manager_user_id)
        .join(Project, WorkLog.project_id == Project.id)
        .outerjoin(
            RateCard,
            and_(RateCard.case_type == Project.case_type, RateCard.region == Project.region),
        )
        .filter(WorkLog.work_date >= month_start, WorkLog.work_date < next_month)
        .group_by(manager_identity)
        .order_by(func.sum(billing_expr).desc())
        .all()
    )

    by_team_member = (
        db.session.query(TeamMember.name, func.sum(billing_expr).label("billing_total"))
        .select_from(WorkLog)
        .join(TeamMember, TeamMember.id == WorkLog.team_member_id)
        .join(Project, WorkLog.project_id == Project.id)
        .outerjoin(
            RateCard,
            and_(RateCard.case_type == Project.case_type, RateCard.region == Project.region),
        )
        .filter(WorkLog.work_date >= month_start, WorkLog.work_date < next_month)
        .group_by(TeamMember.name)
        .order_by(func.sum(billing_expr).desc())
        .all()
    )

    by_project = (
        db.session.query(Project.case_code, func.sum(billing_expr).label("billing_total"))
        .select_from(WorkLog)
        .join(Project, WorkLog.project_id == Project.id)
        .outerjoin(
            RateCard,
            and_(RateCard.case_type == Project.case_type, RateCard.region == Project.region),
        )
        .filter(WorkLog.work_date >= month_start, WorkLog.work_date < next_month)
        .group_by(Project.case_code)
        .order_by(func.sum(billing_expr).desc())
        .all()
    )

    by_region_case = (
        db.session.query(
            Project.region,
            Project.case_type,
            func.sum(billing_expr).label("billing_total"),
        )
        .select_from(WorkLog)
        .join(Project, WorkLog.project_id == Project.id)
        .outerjoin(
            RateCard,
            and_(RateCard.case_type == Project.case_type, RateCard.region == Project.region),
        )
        .filter(WorkLog.work_date >= month_start, WorkLog.work_date < next_month)
        .group_by(Project.region, Project.case_type)
        .order_by(func.sum(billing_expr).desc())
        .all()
    )

    logged_hours = dict(
        db.session.query(WorkLog.team_member_id, func.sum(WorkLog.hours))
        .filter(WorkLog.work_date >= month_start, WorkLog.work_date < next_month)
        .group_by(WorkLog.team_member_id)
        .all()
    )

    utilization_rows = []
    for member in TeamMember.query.filter_by(is_active=True).order_by(TeamMember.name.asc()).all():
        hours = float(logged_hours.get(member.id, 0.0) or 0.0)
        capacity = member.default_daily_capacity_hours * working_days if working_days else 0.0
        utilization = (hours / capacity * 100) if capacity else 0.0
        utilization_rows.append(
            {
                "member": member,
                "hours": hours,
                "capacity": capacity,
                "utilization": utilization,
            }
        )

    return render_template(
        "dashboards/index.html",
        month_key=month_key,
        by_entry_manager=by_entry_manager,
        by_billing_manager=by_billing_manager,
        by_team_member=by_team_member,
        by_project=by_project,
        by_region_case=by_region_case,
        utilization_rows=utilization_rows,
        chart_manager_labels=[row[0] for row in by_billing_manager],
        chart_manager_data=[round(float(row[1] or 0), 2) for row in by_billing_manager],
        chart_member_labels=[row[0] for row in by_team_member],
        chart_member_data=[round(float(row[1] or 0), 2) for row in by_team_member],
    )
