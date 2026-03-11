from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from ...models import CASE_TYPE_CHOICES


class ProjectForm(FlaskForm):
    case_code = StringField("Case Code", validators=[DataRequired(), Length(max=50)])
    description = StringField("Description", validators=[DataRequired(), Length(max=250)])
    case_type = SelectField(
        "Case Type",
        choices=[(choice, choice) for choice in CASE_TYPE_CHOICES],
        validators=[DataRequired()],
    )
    stakeholder = StringField("Stakeholder", validators=[DataRequired(), Length(max=120)])
    region = StringField("Region", validators=[DataRequired(), Length(max=80)])
    nps_contact = StringField("NPS Contact", validators=[DataRequired(), Length(max=120)])
    sku = StringField("SKU", validators=[DataRequired(), Length(max=80)])
    start_date = DateField("Start Date", validators=[Optional()])
    end_date = DateField("End Date", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save")
