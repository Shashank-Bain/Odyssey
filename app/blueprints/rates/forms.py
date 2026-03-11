from flask_wtf import FlaskForm
from wtforms import FloatField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

from ...models import CASE_TYPE_CHOICES


class RateCardForm(FlaskForm):
    case_type = SelectField(
        "Case Type",
        choices=[(choice, choice) for choice in CASE_TYPE_CHOICES],
        validators=[DataRequired()],
    )
    region = StringField("Region", validators=[DataRequired(), Length(max=80)])
    hourly_rate = FloatField("Hourly Rate", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Save")
