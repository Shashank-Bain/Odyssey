from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import Project, Team
from .forms import ProjectForm


projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("/")
def list_projects():
    status = request.args.get("status", "active")
    region = request.args.get("region", "")
    case_type = request.args.get("case_type", "")

    query = Project.query.options(joinedload(Project.worklogs))
    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "inactive":
        query = query.filter_by(is_active=False)

    if region:
        query = query.filter(Project.region == region)
    if case_type:
        query = query.filter(Project.case_type == case_type)

    projects = query.order_by(Project.case_code.asc()).all()
    regions = [r[0] for r in db.session.query(Project.region).distinct().order_by(Project.region.asc())]
    case_types = [
        c[0] for c in db.session.query(Project.case_type).distinct().order_by(Project.case_type.asc())
    ]

    return render_template(
        "projects/list.html",
        projects=projects,
        status=status,
        region=region,
        case_type=case_type,
        regions=regions,
        case_types=case_types,
    )


@projects_bp.route("/new", methods=["GET", "POST"])
def create_project():
    form = ProjectForm()
    form.team_id.choices = [(0, "Unassigned")] + [
        (team.id, team.name) for team in Team.query.order_by(Team.name.asc()).all()
    ]
    if form.validate_on_submit():
        if form.is_active.data and form.team_id.data == 0:
            form.team_id.errors.append("Team is required for active projects.")
            return render_template("projects/form.html", form=form, title="Add Project")

        project = Project(
            case_code=form.case_code.data.strip(),
            description=form.description.data.strip(),
            case_type=form.case_type.data,
            stakeholder=form.stakeholder.data.strip(),
            region=form.region.data.strip(),
            nps_contact=form.nps_contact.data.strip(),
            sku=form.sku.data.strip(),
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            notes=(form.notes.data or "").strip() or None,
            team_id=form.team_id.data or None,
            is_active=form.is_active.data,
        )
        db.session.add(project)
        try:
            db.session.commit()
            flash("Project created.", "success")
            return redirect(url_for("projects.list_projects"))
        except IntegrityError:
            db.session.rollback()
            form.case_code.errors.append("Case code must be unique.")

    return render_template("projects/form.html", form=form, title="Add Project")


@projects_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
def edit_project(project_id: int):
    project = Project.query.get_or_404(project_id)
    form = ProjectForm(obj=project)
    form.team_id.choices = [(0, "Unassigned")] + [
        (team.id, team.name) for team in Team.query.order_by(Team.name.asc()).all()
    ]
    if request.method == "GET":
        form.team_id.data = project.team_id or 0

    if form.validate_on_submit():
        if form.is_active.data and form.team_id.data == 0:
            form.team_id.errors.append("Team is required for active projects.")
            return render_template("projects/form.html", form=form, title="Edit Project")

        project.case_code = form.case_code.data.strip()
        project.description = form.description.data.strip()
        project.case_type = form.case_type.data
        project.stakeholder = form.stakeholder.data.strip()
        project.region = form.region.data.strip()
        project.nps_contact = form.nps_contact.data.strip()
        project.sku = form.sku.data.strip()
        project.start_date = form.start_date.data
        project.end_date = form.end_date.data
        project.notes = (form.notes.data or "").strip() or None
        project.team_id = form.team_id.data or None
        project.is_active = form.is_active.data

        try:
            db.session.commit()
            flash("Project updated.", "success")
            return redirect(url_for("projects.list_projects"))
        except IntegrityError:
            db.session.rollback()
            form.case_code.errors.append("Case code must be unique.")

    return render_template("projects/form.html", form=form, title="Edit Project")


@projects_bp.route("/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id: int):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "success")
    return redirect(url_for("projects.list_projects"))
