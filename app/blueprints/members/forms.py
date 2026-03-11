from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

from ...models import GENDER_CHOICES, LEVEL_CHOICES


class TeamMemberForm(FlaskForm):
    employee_id = StringField("Employee ID", validators=[DataRequired(), Length(max=50)])
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    gender = SelectField(
        "Gender",
        choices=[(choice, choice) for choice in GENDER_CHOICES],
        validators=[DataRequired()],
    )
    level = SelectField(
        "Level",
        choices=[(choice, choice) for choice in LEVEL_CHOICES],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Active", default=True)
    default_daily_capacity_hours = FloatField(
        "Daily Capacity Hours",
        validators=[DataRequired(), NumberRange(min=0.25, max=24)],
        default=8.0,
    )
    submit = SubmitField("Save")
