from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


PROJECT_CASE_TYPE_CHOICES = [
    ("Client billed", "Client Billed"),
    ("Investment", "Investment"),
    ("CD", "CD"),
    ("IP (Z5LB/J2RC)", "IP (Z5LB/J2RC)"),
    ("Others", "Other"),
]


class ProjectForm(FlaskForm):
    case_code = StringField("Case Code", validators=[DataRequired(), Length(max=50)])
    description = StringField("Project Name", validators=[DataRequired(), Length(max=250)])
    case_type = SelectField(
        "Case Type",
        choices=PROJECT_CASE_TYPE_CHOICES,
        validators=[DataRequired()],
    )
    stakeholder = StringField("Stakeholder", validators=[DataRequired(), Length(max=120)])
    region = SelectField("Region", choices=[], validators=[DataRequired()])
    nps_contact = StringField("NPS Contact", validators=[DataRequired(), Length(max=120)])
    sku = SelectField("SKU", choices=[], validators=[DataRequired()])
    start_date = DateField("Start Date", validators=[Optional()])
    end_date = DateField("End Date", validators=[Optional()])
    notes = TextAreaField("Notes / Description", validators=[Optional(), Length(max=2000)])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save")
