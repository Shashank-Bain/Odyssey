from datetime import datetime
from decimal import Decimal

from flask_login import UserMixin

from .extensions import db


GENDER_CHOICES = ["Male", "Female", "Other", "PreferNot"]
LEVEL_CHOICES = [
    "Analyst1",
    "Analyst2",
    "Associate1",
    "Associate2",
    "Associate3",
    "ProjectLeader1",
    "ProjectLeader2",
    "ProjectLeader3",
    "Manager1",
    "Manager2",
    "Manager3",
    "SeniorManager1",
    "SeniorManager2",
    "SeniorManager3",
    "Director",
    "SeniorDirector",
]
CASE_TYPE_CHOICES = [
    "Client billed",
    "ClientCase",
    "IP (Z5LB/J2RC)",
    "Other CD/IP Codes",
    "Investment",
    "CD",
    "Others",
]
WORK_CATEGORY_CHOICES = ["Project", "SickLeave", "Leave", "Training", "Internal", "Holiday", "Bench"]

CLIENT_BILLED_CASE_TYPES = {"Client billed", "ClientCase"}

LEVEL_NORMALIZATION_MAP = {
    "Analyst1": "Analyst 1",
    "Analyst2": "Analyst 2",
    "Associate1": "Associate 1",
    "Associate2": "Associate 2",
    "Associate3": "Associate 3",
    "ProjectLeader1": "Project Leader",
    "ProjectLeader2": "Project Leader",
    "ProjectLeader3": "Project Leader",
    "Manager1": "Manager",
    "Manager2": "Manager",
    "Manager3": "Manager",
    "SeniorManager1": "Senior Manager",
    "SeniorManager2": "Senior Manager",
    "SeniorManager3": "Senior Manager",
    "Director": "Director",
    "SeniorDirector": "Senior Director",
    "SeniorDirector1": "Senior Director",
    "VP": "VP",
}


def normalize_level_key(level: str | None) -> str:
    if not level:
        return ""
    return LEVEL_NORMALIZATION_MAP.get(level.strip(), level.strip())


def is_client_billed_case_type(case_type: str | None) -> bool:
    return (case_type or "").strip() in CLIENT_BILLED_CASE_TYPES


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="Manager")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    worklogs = db.relationship("WorkLog", back_populates="manager_user")

    def __repr__(self):
        return f"<User {self.email}>"


class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    level = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    default_daily_capacity_hours = db.Column(db.Float, default=8.0, nullable=False)

    worklogs = db.relationship("WorkLog", back_populates="team_member", cascade="all, delete-orphan")
    memberships = db.relationship(
        "TeamMembership",
        back_populates="team_member",
        cascade="all, delete-orphan",
        order_by="TeamMembership.start_date.desc()",
    )

    def team_on(self, target_date):
        for membership in self.memberships:
            if membership.active_on(target_date):
                return membership.team
        return None

    @property
    def normalized_level_key(self) -> str:
        return normalize_level_key(self.level)

    def __repr__(self):
        return f"<TeamMember {self.employee_id} - {self.name}>"


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(250), nullable=False)
    case_type = db.Column(db.String(30), nullable=False)
    stakeholder = db.Column(db.String(120), nullable=False)
    region = db.Column(db.String(80), nullable=False, index=True)
    nps_contact = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(80), nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)

    worklogs = db.relationship("WorkLog", back_populates="project", cascade="all, delete-orphan")
    team = db.relationship("Team", back_populates="projects")
    day_billings = db.relationship(
        "ProjectDayBilling",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    assignments = db.relationship(
        "ProjectAssignment", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project {self.case_code}>"


class RateCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_type = db.Column(db.String(30), nullable=False)
    region = db.Column(db.String(80), nullable=False)
    hourly_rate = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint("case_type", "region", name="uq_rate_case_region"),)

    def __repr__(self):
        return f"<RateCard {self.case_type}/{self.region}: {self.hourly_rate}>"


class WorkLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    manager_name = db.Column(db.String(120), nullable=False, index=True)
    manager_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    team_member_id = db.Column(db.Integer, db.ForeignKey("team_member.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)

    work_category = db.Column(db.String(20), nullable=False, default="Project")
    hours = db.Column(db.Float, nullable=False)
    team_name = db.Column(db.String(120), nullable=True)
    billing_manager_name = db.Column(db.String(120), nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    team_member = db.relationship("TeamMember", back_populates="worklogs")
    project = db.relationship("Project", back_populates="worklogs")
    manager_user = db.relationship("User", back_populates="worklogs")

    def __repr__(self):
        return f"<WorkLog {self.work_date} {self.team_member_id} {self.project_id} {self.hours}>"


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    owner_user = db.relationship("User")
    memberships = db.relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")
    projects = db.relationship("Project", back_populates="team")


class TeamMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_member_id = db.Column(db.Integer, db.ForeignKey("team_member.id"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)

    team_member = db.relationship("TeamMember", back_populates="memberships")
    team = db.relationship("Team", back_populates="memberships")

    def active_on(self, target_date) -> bool:
        if target_date < self.start_date:
            return False
        if self.end_date and target_date > self.end_date:
            return False
        return True


class ProjectDayBilling(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    billable_fte = db.Column(db.Numeric(10, 2), nullable=False)
    billing_manager_name = db.Column(db.String(120), nullable=True)
    billing_manager_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    override_daily_revenue = db.Column(db.Numeric(12, 2), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    project = db.relationship("Project", back_populates="day_billings")
    billing_manager_user = db.relationship("User")

    __table_args__ = (db.UniqueConstraint("project_id", "work_date", name="uq_project_day_billing"),)


class CostRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level_key = db.Column(db.String(80), nullable=False, unique=True, index=True)
    cost_per_day = db.Column(db.Numeric(12, 2), nullable=False)
    effective_start_date = db.Column(db.Date, nullable=True)
    effective_end_date = db.Column(db.Date, nullable=True)

    @property
    def cost_per_hour(self) -> Decimal:
        return Decimal(self.cost_per_day or 0) / Decimal("8")


class ClientBillingRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(30), nullable=False, index=True)
    cadence = db.Column(db.String(20), nullable=False, index=True)
    fte_point = db.Column(db.Numeric(10, 2), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("region", "cadence", "fte_point", name="uq_client_billing_rate"),
    )


class NonClientBillingConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    base_daily_rate_for_4_5 = db.Column(db.Numeric(12, 2), nullable=False, default=1080)


class ProjectAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    team_member_id = db.Column(db.Integer, db.ForeignKey("team_member.id"), nullable=False)
    planned_start = db.Column(db.Date, nullable=False)
    planned_end = db.Column(db.Date, nullable=False)
    planned_hours_per_day = db.Column(db.Float, nullable=False, default=8.0)

    project = db.relationship("Project", back_populates="assignments")
    team_member = db.relationship("TeamMember")
