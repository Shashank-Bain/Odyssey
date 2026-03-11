from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class TeamForm(FlaskForm):
    name = StringField("Team Name", validators=[DataRequired(), Length(max=150)])
    owner_user_id = SelectField("Owner", coerce=int, validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save")


class TeamMembershipForm(FlaskForm):
    team_member_id = SelectField("Team Member", coerce=int, validators=[DataRequired()])
    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date", validators=[Optional()])
    submit = SubmitField("Save Membership")
