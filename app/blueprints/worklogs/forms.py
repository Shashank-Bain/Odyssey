from flask_wtf import FlaskForm
from wtforms import DateField, FloatField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, NumberRange, ValidationError


def validate_quarter_hour(form, field):
    value = field.data or 0
    rounded = round(value * 4)
    if abs((rounded / 4) - value) > 1e-8:
        raise ValidationError("Hours must be in quarter-hour increments (e.g. 1.25, 1.5).")


class WorkLogEntryForm(FlaskForm):
    work_date = DateField("Date", validators=[DataRequired()])
    manager_name = StringField("Manager Name", validators=[DataRequired()])
    team_member_id = SelectField("Team Member", coerce=int, validators=[DataRequired()])
    project_id = SelectField("Project", coerce=int, validators=[DataRequired()])
    hours = FloatField(
        "Hours",
        validators=[DataRequired(), NumberRange(min=0.25, max=24), validate_quarter_hour],
    )
    billing_manager_name = StringField("Billing Manager", validators=[DataRequired()])
    submit = SubmitField("Add Row")
