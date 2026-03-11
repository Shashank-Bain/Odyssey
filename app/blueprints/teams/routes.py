from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...models import Team, TeamMember, TeamMembership, User
from .forms import TeamForm, TeamMembershipForm


teams_bp = Blueprint("teams", __name__, url_prefix="/teams")


def _owner_choices() -> list[tuple[int, str]]:
    choices = [(0, "Unassigned")]
    users = User.query.filter_by(is_active=True).order_by(User.full_name.asc()).all()
    for user in users:
        choices.append((user.id, user.full_name))
    return choices


def _membership_choices() -> list[tuple[int, str]]:
    members = TeamMember.query.order_by(TeamMember.name.asc()).all()
    return [(member.id, f"{member.name} ({member.employee_id})") for member in members]


def _has_overlap(team_member_id: int, start_date: date, end_date: date | None, ignore_id: int | None = None) -> bool:
    query = TeamMembership.query.filter(TeamMembership.team_member_id == team_member_id)
    if ignore_id:
        query = query.filter(TeamMembership.id != ignore_id)

    upper_bound = end_date or date.max

    overlap = query.filter(
        and_(
            TeamMembership.start_date <= upper_bound,
            or_(TeamMembership.end_date.is_(None), TeamMembership.end_date >= start_date),
        )
    ).first()
    return overlap is not None


@teams_bp.route("/")
@login_required
def list_teams():
    status = request.args.get("status", "active")
    query = Team.query
    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "inactive":
        query = query.filter_by(is_active=False)

    teams = query.order_by(Team.name.asc()).all()
    return render_template("teams/list.html", teams=teams, status=status)


@teams_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_team():
    form = TeamForm()
    form.owner_user_id.choices = _owner_choices()
    if form.validate_on_submit():
        team = Team(
            name=form.name.data.strip(),
            owner_user_id=form.owner_user_id.data or None,
            is_active=form.is_active.data,
        )
        db.session.add(team)
        try:
            db.session.commit()
            flash("Team created.", "success")
            return redirect(url_for("teams.list_teams"))
        except IntegrityError:
            db.session.rollback()
            form.name.errors.append("Team name must be unique.")

    return render_template("teams/form.html", form=form, title="Add Team")


@teams_bp.route("/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
def edit_team(team_id: int):
    team = Team.query.get_or_404(team_id)
    form = TeamForm(obj=team)
    form.owner_user_id.choices = _owner_choices()
    if request.method == "GET":
        form.owner_user_id.data = team.owner_user_id or 0

    if form.validate_on_submit():
        team.name = form.name.data.strip()
        team.owner_user_id = form.owner_user_id.data or None
        team.is_active = form.is_active.data
        try:
            db.session.commit()
            flash("Team updated.", "success")
            return redirect(url_for("teams.list_teams"))
        except IntegrityError:
            db.session.rollback()
            form.name.errors.append("Team name must be unique.")

    return render_template("teams/form.html", form=form, title="Edit Team")


@teams_bp.route("/<int:team_id>/delete", methods=["POST"])
@login_required
def delete_team(team_id: int):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    flash("Team deleted.", "success")
    return redirect(url_for("teams.list_teams"))


@teams_bp.route("/<int:team_id>", methods=["GET", "POST"])
@login_required
def team_detail(team_id: int):
    team = Team.query.get_or_404(team_id)
    form = TeamMembershipForm()
    form.team_member_id.choices = _membership_choices()

    if form.validate_on_submit():
        if form.end_date.data and form.end_date.data < form.start_date.data:
            form.end_date.errors.append("End date must be on or after start date.")
        elif _has_overlap(form.team_member_id.data, form.start_date.data, form.end_date.data):
            form.team_member_id.errors.append(
                "This member already has an overlapping team membership. Close the previous period first."
            )
        else:
            membership = TeamMembership(
                team_id=team.id,
                team_member_id=form.team_member_id.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
            )
            db.session.add(membership)
            db.session.commit()
            flash("Membership added.", "success")
            return redirect(url_for("teams.team_detail", team_id=team.id))

    memberships = (
        TeamMembership.query.filter_by(team_id=team.id)
        .join(TeamMember, TeamMembership.team_member_id == TeamMember.id)
        .order_by(TeamMembership.start_date.desc(), TeamMember.name.asc())
        .all()
    )

    return render_template("teams/detail.html", team=team, memberships=memberships, form=form)


@teams_bp.route("/memberships/<int:membership_id>/update", methods=["POST"])
@login_required
def update_membership(membership_id: int):
    membership = TeamMembership.query.get_or_404(membership_id)
    team_id = membership.team_id

    start_date_raw = (request.form.get("start_date") or "").strip()
    end_date_raw = (request.form.get("end_date") or "").strip()

    try:
        start_value = date.fromisoformat(start_date_raw)
    except ValueError:
        flash("Invalid membership start date.", "danger")
        return redirect(url_for("teams.team_detail", team_id=team_id))

    end_value = None
    if end_date_raw:
        try:
            end_value = date.fromisoformat(end_date_raw)
        except ValueError:
            flash("Invalid membership end date.", "danger")
            return redirect(url_for("teams.team_detail", team_id=team_id))

    if end_value and end_value < start_value:
        flash("End date must be on or after start date.", "danger")
        return redirect(url_for("teams.team_detail", team_id=team_id))

    if _has_overlap(membership.team_member_id, start_value, end_value, ignore_id=membership.id):
        flash("Membership overlaps another period for this member.", "danger")
        return redirect(url_for("teams.team_detail", team_id=team_id))

    membership.start_date = start_value
    membership.end_date = end_value
    db.session.commit()
    flash("Membership updated.", "success")
    return redirect(url_for("teams.team_detail", team_id=team_id))


@teams_bp.route("/memberships/<int:membership_id>/delete", methods=["POST"])
@login_required
def delete_membership(membership_id: int):
    membership = TeamMembership.query.get_or_404(membership_id)
    team_id = membership.team_id
    db.session.delete(membership)
    db.session.commit()
    flash("Membership deleted.", "success")
    return redirect(url_for("teams.team_detail", team_id=team_id))
