from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from ...extensions import db
from ...models import TeamMember
from .forms import TeamMemberForm


members_bp = Blueprint("members", __name__, url_prefix="/members")


@members_bp.route("/")
def list_members():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "active")

    query = TeamMember.query
    if q:
        like_value = f"%{q}%"
        query = query.filter(
            or_(TeamMember.name.ilike(like_value), TeamMember.employee_id.ilike(like_value))
        )

    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "inactive":
        query = query.filter_by(is_active=False)

    members = query.order_by(TeamMember.name.asc()).all()
    return render_template("members/list.html", members=members, q=q, status=status)


@members_bp.route("/new", methods=["GET", "POST"])
def create_member():
    form = TeamMemberForm()
    if form.validate_on_submit():
        member = TeamMember(
            employee_id=form.employee_id.data.strip(),
            name=form.name.data.strip(),
            gender=form.gender.data,
            level=form.level.data,
            is_active=form.is_active.data,
            default_daily_capacity_hours=form.default_daily_capacity_hours.data,
        )
        db.session.add(member)
        try:
            db.session.commit()
            flash("Team member created.", "success")
            return redirect(url_for("members.list_members"))
        except IntegrityError:
            db.session.rollback()
            form.employee_id.errors.append("Employee ID must be unique.")

    return render_template("members/form.html", form=form, title="Add Team Member")


@members_bp.route("/<int:member_id>/edit", methods=["GET", "POST"])
def edit_member(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    form = TeamMemberForm(obj=member)
    if form.validate_on_submit():
        member.employee_id = form.employee_id.data.strip()
        member.name = form.name.data.strip()
        member.gender = form.gender.data
        member.level = form.level.data
        member.is_active = form.is_active.data
        member.default_daily_capacity_hours = form.default_daily_capacity_hours.data

        try:
            db.session.commit()
            flash("Team member updated.", "success")
            return redirect(url_for("members.list_members"))
        except IntegrityError:
            db.session.rollback()
            form.employee_id.errors.append("Employee ID must be unique.")

    return render_template("members/form.html", form=form, title="Edit Team Member")


@members_bp.route("/<int:member_id>/delete", methods=["POST"])
def delete_member(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    flash("Team member deleted.", "success")
    return redirect(url_for("members.list_members"))
