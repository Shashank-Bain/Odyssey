from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...models import ClientBillingRate, CostRate, NonClientBillingConfig
from .forms import ClientBillingRateForm, CostRateForm, NonClientBillingConfigForm


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/cost-rates")
@login_required
def list_cost_rates():
    rates = CostRate.query.order_by(CostRate.level_key.asc()).all()
    return render_template("admin/cost_rates_list.html", rates=rates)


@admin_bp.route("/cost-rates/new", methods=["GET", "POST"])
@login_required
def create_cost_rate():
    form = CostRateForm()
    if form.validate_on_submit():
        rate = CostRate(
            level_key=form.level_key.data.strip(),
            cost_per_day=form.cost_per_day.data,
            effective_start_date=form.effective_start_date.data,
            effective_end_date=form.effective_end_date.data,
        )
        db.session.add(rate)
        try:
            db.session.commit()
            flash("Cost rate created.", "success")
            return redirect(url_for("admin.list_cost_rates"))
        except IntegrityError:
            db.session.rollback()
            form.level_key.errors.append("Level key must be unique.")

    return render_template("admin/cost_rates_form.html", form=form, title="Add Cost Rate")


@admin_bp.route("/cost-rates/<int:rate_id>/edit", methods=["GET", "POST"])
@login_required
def edit_cost_rate(rate_id: int):
    rate = CostRate.query.get_or_404(rate_id)
    form = CostRateForm(obj=rate)
    if form.validate_on_submit():
        rate.level_key = form.level_key.data.strip()
        rate.cost_per_day = form.cost_per_day.data
        rate.effective_start_date = form.effective_start_date.data
        rate.effective_end_date = form.effective_end_date.data
        try:
            db.session.commit()
            flash("Cost rate updated.", "success")
            return redirect(url_for("admin.list_cost_rates"))
        except IntegrityError:
            db.session.rollback()
            form.level_key.errors.append("Level key must be unique.")

    return render_template("admin/cost_rates_form.html", form=form, title="Edit Cost Rate")


@admin_bp.route("/cost-rates/<int:rate_id>/delete", methods=["POST"])
@login_required
def delete_cost_rate(rate_id: int):
    rate = CostRate.query.get_or_404(rate_id)
    db.session.delete(rate)
    db.session.commit()
    flash("Cost rate deleted.", "success")
    return redirect(url_for("admin.list_cost_rates"))


@admin_bp.route("/client-billing-rates")
@login_required
def list_client_billing_rates():
    rates = (
        ClientBillingRate.query.order_by(
            ClientBillingRate.region.asc(),
            ClientBillingRate.cadence.asc(),
            ClientBillingRate.fte_point.desc(),
        ).all()
    )
    return render_template("admin/client_billing_rates_list.html", rates=rates)


@admin_bp.route("/client-billing-rates/new", methods=["GET", "POST"])
@login_required
def create_client_billing_rate():
    form = ClientBillingRateForm()
    if form.validate_on_submit():
        rate = ClientBillingRate(
            region=form.region.data,
            cadence=form.cadence.data,
            fte_point=form.fte_point.data,
            amount=form.amount.data,
        )
        db.session.add(rate)
        try:
            db.session.commit()
            flash("Client billing rate created.", "success")
            return redirect(url_for("admin.list_client_billing_rates"))
        except IntegrityError:
            db.session.rollback()
            form.fte_point.errors.append("A row already exists for this region, cadence, and FTE point.")

    return render_template("admin/client_billing_rates_form.html", form=form, title="Add Client Billing Rate")


@admin_bp.route("/client-billing-rates/<int:rate_id>/edit", methods=["GET", "POST"])
@login_required
def edit_client_billing_rate(rate_id: int):
    rate = ClientBillingRate.query.get_or_404(rate_id)
    form = ClientBillingRateForm(obj=rate)
    if form.validate_on_submit():
        rate.region = form.region.data
        rate.cadence = form.cadence.data
        rate.fte_point = form.fte_point.data
        rate.amount = form.amount.data
        try:
            db.session.commit()
            flash("Client billing rate updated.", "success")
            return redirect(url_for("admin.list_client_billing_rates"))
        except IntegrityError:
            db.session.rollback()
            form.fte_point.errors.append("A row already exists for this region, cadence, and FTE point.")

    return render_template("admin/client_billing_rates_form.html", form=form, title="Edit Client Billing Rate")


@admin_bp.route("/client-billing-rates/<int:rate_id>/delete", methods=["POST"])
@login_required
def delete_client_billing_rate(rate_id: int):
    rate = ClientBillingRate.query.get_or_404(rate_id)
    db.session.delete(rate)
    db.session.commit()
    flash("Client billing rate deleted.", "success")
    return redirect(url_for("admin.list_client_billing_rates"))


@admin_bp.route("/nonclient-config", methods=["GET", "POST"])
@login_required
def nonclient_config():
    config = NonClientBillingConfig.query.order_by(NonClientBillingConfig.id.asc()).first()
    if not config:
        config = NonClientBillingConfig(base_daily_rate_for_4_5=1080)
        db.session.add(config)
        db.session.commit()

    form = NonClientBillingConfigForm(obj=config)
    if form.validate_on_submit():
        config.base_daily_rate_for_4_5 = form.base_daily_rate_for_4_5.data
        db.session.commit()
        flash("Non-client billing config updated.", "success")
        return redirect(url_for("admin.nonclient_config"))

    return render_template("admin/nonclient_config.html", form=form)
