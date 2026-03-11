from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, or_

from .extensions import db
from .models import (
    ClientBillingRate,
    CostRate,
    NonClientBillingConfig,
    Project,
    ProjectDayBilling,
    TeamMembership,
    TeamMember,
    WorkLog,
    is_client_billed_case_type,
    normalize_level_key,
)


DEFAULT_NONCLIENT_BASE = Decimal("1080")
HALF_STEP = Decimal("0.5")


@dataclass
class RevenueResult:
    amount: Decimal
    warning: str | None = None


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def is_half_step(value) -> bool:
    try:
        dec = _to_decimal(value)
    except Exception:
        return False
    return (dec % HALF_STEP) == 0


def get_nonclient_base_rate() -> Decimal:
    row = NonClientBillingConfig.query.order_by(NonClientBillingConfig.id.asc()).first()
    if not row or row.base_daily_rate_for_4_5 is None:
        return DEFAULT_NONCLIENT_BASE
    return _to_decimal(row.base_daily_rate_for_4_5)


def interpolate_client_daily_rate(region: str, billable_fte: Decimal) -> RevenueResult:
    points = (
        ClientBillingRate.query.filter_by(region=region, cadence="Daily")
        .order_by(ClientBillingRate.fte_point.asc())
        .all()
    )
    if not points:
        return RevenueResult(amount=Decimal("0"), warning=f"No Daily rates configured for region {region}.")

    exact = next((r for r in points if _to_decimal(r.fte_point) == billable_fte), None)
    if exact:
        return RevenueResult(amount=_to_decimal(exact.amount))

    # Outside configured range: prorate from the highest configured rate.
    min_fte = _to_decimal(points[0].fte_point)
    max_fte = _to_decimal(points[-1].fte_point)
    if billable_fte < min_fte or billable_fte > max_fte:
        max_amount = _to_decimal(points[-1].amount)
        if max_fte == 0:
            return RevenueResult(amount=Decimal("0"), warning="Invalid max FTE configuration.")
        return RevenueResult(amount=max_amount * (billable_fte / max_fte))

    lower = None
    upper = None
    for idx in range(len(points) - 1):
        left = points[idx]
        right = points[idx + 1]
        left_fte = _to_decimal(left.fte_point)
        right_fte = _to_decimal(right.fte_point)
        if left_fte <= billable_fte <= right_fte:
            lower = left
            upper = right
            break

    if not lower or not upper:
        return RevenueResult(amount=Decimal("0"), warning="Unable to interpolate billing rate.")

    lower_fte = _to_decimal(lower.fte_point)
    upper_fte = _to_decimal(upper.fte_point)
    lower_amount = _to_decimal(lower.amount)
    upper_amount = _to_decimal(upper.amount)

    if upper_fte == lower_fte:
        return RevenueResult(amount=lower_amount)

    slope = (upper_amount - lower_amount) / (upper_fte - lower_fte)
    interpolated = lower_amount + slope * (billable_fte - lower_fte)
    return RevenueResult(amount=interpolated)


def compute_project_day_revenue(project: Project, project_day_billing: ProjectDayBilling | None) -> RevenueResult:
    if not project_day_billing:
        return RevenueResult(amount=Decimal("0"), warning="Billable FTE not set for this project-day.")

    if project_day_billing.override_daily_revenue is not None:
        return RevenueResult(amount=_to_decimal(project_day_billing.override_daily_revenue))

    billable_fte = _to_decimal(project_day_billing.billable_fte)

    if is_client_billed_case_type(project.case_type):
        return interpolate_client_daily_rate(project.region, billable_fte)

    base_rate = get_nonclient_base_rate()
    return RevenueResult(amount=base_rate * (billable_fte / Decimal("4.5")))


def get_effective_cost_rate(level_key: str, target_date: date) -> CostRate | None:
    normalized = normalize_level_key(level_key)
    return (
        CostRate.query.filter(CostRate.level_key == normalized)
        .filter(
            and_(
                or_(CostRate.effective_start_date.is_(None), CostRate.effective_start_date <= target_date),
                or_(CostRate.effective_end_date.is_(None), CostRate.effective_end_date >= target_date),
            )
        )
        .order_by(CostRate.effective_start_date.desc().nullslast(), CostRate.id.desc())
        .first()
    )


def compute_worklog_cost(worklog: WorkLog) -> Decimal:
    if not worklog.team_member:
        return Decimal("0")
    level_key = normalize_level_key(worklog.team_member.level)
    rate = get_effective_cost_rate(level_key, worklog.work_date)
    if not rate:
        return Decimal("0")
    cost_per_hour = _to_decimal(rate.cost_per_day) / Decimal("8")
    return _to_decimal(worklog.hours) * cost_per_hour


def team_for_member_on(member_id: int, target_date: date) -> TeamMembership | None:
    return (
        TeamMembership.query.filter_by(team_member_id=member_id)
        .filter(
            TeamMembership.start_date <= target_date,
            or_(TeamMembership.end_date.is_(None), TeamMembership.end_date >= target_date),
        )
        .order_by(TeamMembership.start_date.desc(), TeamMembership.id.desc())
        .first()
    )


def allocate_project_day_revenue(worklogs: list[WorkLog], total_revenue: Decimal) -> dict[int, Decimal]:
    total_hours = sum(_to_decimal(row.hours) for row in worklogs)
    if total_hours <= 0:
        return {row.id: Decimal("0") for row in worklogs if row.id is not None}

    allocations = {}
    for row in worklogs:
        if row.id is None:
            continue
        share = total_revenue * (_to_decimal(row.hours) / total_hours)
        allocations[row.id] = share
    return allocations


def to_float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)
