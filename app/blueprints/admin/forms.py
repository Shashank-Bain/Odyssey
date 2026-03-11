from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


REGION_CHOICES = ["AMER", "EMEA", "APAC", "Global"]
CADENCE_CHOICES = ["Daily", "Weekly"]


class CostRateForm(FlaskForm):
    level_key = StringField("Level Key", validators=[DataRequired(), Length(max=80)])
    cost_per_day = DecimalField("Cost Per Day", validators=[DataRequired(), NumberRange(min=0)], places=2)
    effective_start_date = DateField("Effective Start Date", validators=[Optional()])
    effective_end_date = DateField("Effective End Date", validators=[Optional()])
    submit = SubmitField("Save")


class ClientBillingRateForm(FlaskForm):
    region = SelectField(
        "Region",
        choices=[(choice, choice) for choice in REGION_CHOICES],
        validators=[DataRequired()],
    )
    cadence = SelectField(
        "Cadence",
        choices=[(choice, choice) for choice in CADENCE_CHOICES],
        validators=[DataRequired()],
    )
    fte_point = DecimalField("FTE Point", validators=[DataRequired(), NumberRange(min=0)], places=2)
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)], places=2)
    submit = SubmitField("Save")


class NonClientBillingConfigForm(FlaskForm):
    base_daily_rate_for_4_5 = DecimalField(
        "Base Daily Rate for 4.5 FTE",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
    )
    submit = SubmitField("Save")
