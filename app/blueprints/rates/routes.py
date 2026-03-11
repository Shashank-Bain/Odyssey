from flask import Blueprint, flash, redirect, render_template, url_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, func

from ...extensions import db
from ...models import Project, RateCard, WorkLog
from .forms import RateCardForm


rates_bp = Blueprint("rates", __name__, url_prefix="/rates")


@rates_bp.route("/")
def list_rates():
    rates = RateCard.query.order_by(RateCard.case_type.asc(), RateCard.region.asc()).all()

    missing_rate_rows = (
        db.session.query(Project.case_type, Project.region, func.count(WorkLog.id).label("logs_count"))
        .join(WorkLog, WorkLog.project_id == Project.id)
        .outerjoin(
            RateCard,
            and_(RateCard.case_type == Project.case_type, RateCard.region == Project.region),
        )
        .filter(RateCard.id.is_(None))
        .group_by(Project.case_type, Project.region)
        .order_by(Project.case_type.asc(), Project.region.asc())
        .all()
    )

    return render_template("rates/list.html", rates=rates, missing_rate_rows=missing_rate_rows)


@rates_bp.route("/new", methods=["GET", "POST"])
def create_rate():
    form = RateCardForm()
    if form.validate_on_submit():
        rate = RateCard(
            case_type=form.case_type.data,
            region=form.region.data.strip(),
            hourly_rate=form.hourly_rate.data,
        )
        db.session.add(rate)
        try:
            db.session.commit()
            flash("Rate card created.", "success")
            return redirect(url_for("rates.list_rates"))
        except IntegrityError:
            db.session.rollback()
            form.region.errors.append("A rate for this case type and region already exists.")

    return render_template("rates/form.html", form=form, title="Add Rate")


@rates_bp.route("/<int:rate_id>/edit", methods=["GET", "POST"])
def edit_rate(rate_id: int):
    rate = RateCard.query.get_or_404(rate_id)
    form = RateCardForm(obj=rate)
    if form.validate_on_submit():
        rate.case_type = form.case_type.data
        rate.region = form.region.data.strip()
        rate.hourly_rate = form.hourly_rate.data

        try:
            db.session.commit()
            flash("Rate card updated.", "success")
            return redirect(url_for("rates.list_rates"))
        except IntegrityError:
            db.session.rollback()
            form.region.errors.append("A rate for this case type and region already exists.")

    return render_template("rates/form.html", form=form, title="Edit Rate")


@rates_bp.route("/<int:rate_id>/delete", methods=["POST"])
def delete_rate(rate_id: int):
    rate = RateCard.query.get_or_404(rate_id)
    db.session.delete(rate)
    db.session.commit()
    flash("Rate card deleted.", "success")
    return redirect(url_for("rates.list_rates"))
