import os
from datetime import date

import click
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from .extensions import csrf, db, login_manager, migrate
from .models import (
    LEVEL_CHOICES,
    ClientBillingRate,
    CostRate,
    NonClientBillingConfig,
    Project,
    ProjectDayBilling,
    RateCard,
    Team,
    TeamMember,
    TeamMembership,
    User,
    WorkLog,
    normalize_level_key,
)


RESET_MANAGER_PEOPLE = [
    {"name": "Sonal Chawla", "level": "SeniorDirector"},
    {"name": "Shashank Yadav", "level": "SeniorManager1"},
    {"name": "Rajat Pratap Singh", "level": "SeniorManager1"},
    {"name": "Samyak Ponangi", "level": "Manager3"},
    {"name": "Subodhika Vohra", "level": "Manager3"},
    {"name": "Kriti Chopra", "level": "Manager3"},
]

SEED_TEAM_DEFINITIONS = [
    ("SustainX & Commitments", "Shashank Yadav"),
    ("Global Sustainability - Carbon", "Shashank Yadav"),
    ("Global Sustainability - Reporting", "Kriti Chopra"),
    ("Sustainability Carbon & ESG Diagnostics", "Subodhika Vohra"),
    ("Sustainability New Frontiers", "Subodhika Vohra"),
    ("Sustainability Social Impact", "Subodhika Vohra"),
    ("NZN/Decarb", "Rajat Pratap Singh"),
    ("Sustainability Policy", "Samyak Ponangi"),
    ("ESG Diagnostics", "Samyak Ponangi"),
]

SEED_COST_RATES = [
    ("Analyst 1", 220),
    ("Analyst 2", 250),
    ("Associate 1", 350),
    ("Associate 2", 400),
    ("Associate 3", 400),
    ("Project Leader", 550),
    ("Manager", 800),
    ("Senior Manager", 1000),
    ("Director", 1600),
    ("Senior Director", 2300),
    ("VP", 2600),
]

SEED_CLIENT_BILLING_RATES = [
    ("AMER", "Weekly", 4.5, 19000),
    ("AMER", "Weekly", 3.5, 14800),
    ("AMER", "Weekly", 2.5, 10500),
    ("AMER", "Weekly", 1.0, 4200),
    ("AMER", "Daily", 4.5, 3800),
    ("AMER", "Daily", 3.5, 2960),
    ("AMER", "Daily", 2.5, 2100),
    ("AMER", "Daily", 1.0, 840),
    ("EMEA", "Weekly", 4.5, 17500),
    ("EMEA", "Weekly", 3.5, 13600),
    ("EMEA", "Weekly", 2.5, 9700),
    ("EMEA", "Weekly", 1.0, 3900),
    ("EMEA", "Daily", 4.5, 3500),
    ("EMEA", "Daily", 3.5, 2720),
    ("EMEA", "Daily", 2.5, 1940),
    ("EMEA", "Daily", 1.0, 780),
    ("APAC", "Weekly", 4.5, 16500),
    ("APAC", "Weekly", 3.5, 12800),
    ("APAC", "Weekly", 2.5, 9200),
    ("APAC", "Weekly", 1.0, 3700),
    ("APAC", "Daily", 4.5, 3300),
    ("APAC", "Daily", 3.5, 2560),
    ("APAC", "Daily", 2.5, 1840),
    ("APAC", "Daily", 1.0, 740),
]


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///odyssey.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from .blueprints.auth.routes import auth_bp
    from .blueprints.dashboards.routes import dashboards_bp
    from .blueprints.members.routes import members_bp
    from .blueprints.admin.routes import admin_bp
    from .blueprints.projects.routes import projects_bp
    from .blueprints.rates.routes import rates_bp
    from .blueprints.teams.routes import teams_bp
    from .blueprints.worklogs.routes import worklogs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(worklogs_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(rates_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dashboards_bp)

    register_cli(app)

    with app.app_context():
        db.create_all()

    @app.template_filter("currency")
    def currency_filter(value: float) -> str:
        return f"${value:,.2f}"

    return app


def register_cli(app: Flask) -> None:
    def _build_email(full_name: str) -> str:
        parts = [part.strip().lower() for part in full_name.split() if part.strip()]
        if len(parts) < 2:
            local = parts[0] if parts else "manager"
        else:
            local = f"{parts[0]}.{parts[-1]}"
        return f"{local}@local"

    def _next_employee_ids(count: int) -> list[str]:
        used_ids = {
            row[0]
            for row in db.session.query(TeamMember.employee_id)
            .filter(TeamMember.employee_id.like("BCN%"))
            .all()
        }
        generated: list[str] = []
        idx = 1
        while len(generated) < count:
            candidate = f"BCN{idx:03d}"
            if candidate not in used_ids:
                generated.append(candidate)
                used_ids.add(candidate)
            idx += 1
        return generated

    def _seed_reset_managers() -> list[User]:
        employee_ids = _next_employee_ids(len(RESET_MANAGER_PEOPLE))
        created_users: list[User] = []
        for idx, person in enumerate(RESET_MANAGER_PEOPLE):
            if person["level"] not in LEVEL_CHOICES:
                raise click.ClickException(
                    f"Configured level '{person['level']}' is not in LEVEL_CHOICES."
                )

            member = TeamMember(
                employee_id=employee_ids[idx],
                name=person["name"],
                gender="PreferNot",
                level=person["level"],
                is_active=True,
                default_daily_capacity_hours=8.0,
            )
            user = User(
                email=_build_email(person["name"]),
                full_name=person["name"],
                password_hash=generate_password_hash("manager123"),
                role="Manager",
                is_active=True,
            )
            db.session.add(member)
            db.session.add(user)
            created_users.append(user)
        return created_users

    def _seed_master_data() -> None:
        users_by_name = {user.full_name: user for user in User.query.all()}

        team_map = {}
        for team_name, owner_name in SEED_TEAM_DEFINITIONS:
            team = Team.query.filter_by(name=team_name).first()
            if not team:
                team = Team(name=team_name)
                db.session.add(team)
            owner = users_by_name.get(owner_name)
            team.owner_user_id = owner.id if owner else None
            team.is_active = True
            team_map[team_name] = team

        db.session.flush()

        cost_rate_map = {rate.level_key: rate for rate in CostRate.query.all()}
        for level_key, cost_per_day in SEED_COST_RATES:
            normalized = normalize_level_key(level_key)
            rate = cost_rate_map.get(normalized)
            if not rate:
                rate = CostRate(level_key=normalized)
                db.session.add(rate)
            rate.cost_per_day = cost_per_day
            rate.effective_start_date = None
            rate.effective_end_date = None

        existing_client_rates = {
            (row.region, row.cadence, float(row.fte_point)): row for row in ClientBillingRate.query.all()
        }
        for region, cadence, fte_point, amount in SEED_CLIENT_BILLING_RATES:
            key = (region, cadence, float(fte_point))
            rate = existing_client_rates.get(key)
            if not rate:
                rate = ClientBillingRate(region=region, cadence=cadence, fte_point=fte_point)
                db.session.add(rate)
            rate.amount = amount

        config = NonClientBillingConfig.query.order_by(NonClientBillingConfig.id.asc()).first()
        if not config:
            config = NonClientBillingConfig(base_daily_rate_for_4_5=1080)
            db.session.add(config)
        else:
            config.base_daily_rate_for_4_5 = 1080

        projects = [
            {
                "case_code": "CASE-1001",
                "description": "Retail cost optimization sprint",
                "case_type": "Client billed",
                "stakeholder": "Retail BU",
                "region": "AMER",
                "nps_contact": "Sam Wilson",
                "sku": "SKU-RET-01",
                "start_date": date(2026, 1, 10),
                "team_name": "SustainX & Commitments",
            },
            {
                "case_code": "CASE-2002",
                "description": "Carbon disclosure readiness",
                "case_type": "CD",
                "stakeholder": "Sustainability Office",
                "region": "EMEA",
                "nps_contact": "Leah Smith",
                "sku": "SKU-CD-22",
                "start_date": date(2026, 2, 1),
                "team_name": "Global Sustainability - Reporting",
            },
            {
                "case_code": "CASE-3003",
                "description": "Hydrogen investment diligence",
                "case_type": "Investment",
                "stakeholder": "Corp Strategy",
                "region": "APAC",
                "nps_contact": "Raj Nair",
                "sku": "SKU-INV-07",
                "start_date": date(2026, 2, 14),
                "team_name": "NZN/Decarb",
            },
            {
                "case_code": "CASE-4004",
                "description": "Internal process redesign",
                "case_type": "Others",
                "stakeholder": "Operations",
                "region": "Global",
                "nps_contact": "Elena Cruz",
                "sku": "SKU-OPS-11",
                "start_date": date(2026, 1, 20),
                "team_name": "ESG Diagnostics",
            },
        ]

        for project_data in projects:
            project = Project.query.filter_by(case_code=project_data["case_code"]).first()
            if not project:
                project = Project(case_code=project_data["case_code"])
                db.session.add(project)

            project.description = project_data["description"]
            project.case_type = project_data["case_type"]
            project.stakeholder = project_data["stakeholder"]
            project.region = project_data["region"]
            project.nps_contact = project_data["nps_contact"]
            project.sku = project_data["sku"]
            project.start_date = project_data["start_date"]
            project.is_active = True
            project.team_id = team_map[project_data["team_name"]].id

        # Keep legacy rate cards available to avoid breaking old dashboard logic.
        legacy_rates = [
            ("ClientCase", "North America", 220.0),
            ("CD", "EMEA", 180.0),
            ("Investment", "APAC", 250.0),
            ("Others", "LATAM", 140.0),
        ]
        existing_legacy = {(row.case_type, row.region): row for row in RateCard.query.all()}
        for case_type, region, hourly_rate in legacy_rates:
            rate = existing_legacy.get((case_type, region))
            if not rate:
                rate = RateCard(case_type=case_type, region=region)
                db.session.add(rate)
            rate.hourly_rate = hourly_rate

    @app.cli.command("reset-db")
    @click.option("--all", "reset_scope", flag_value="all", default=True, help="Drop all tables, recreate, and seed demo data.")
    @click.option(
        "--managers-only",
        "reset_scope",
        flag_value="managers-only",
        help="Only reset User and TeamMember records and recreate manager accounts.",
    )
    def reset_db(reset_scope: str) -> None:
        created_users: list[User] = []

        try:
            if reset_scope == "all":
                db.session.query(ProjectDayBilling).delete()
                db.session.query(WorkLog).delete()
                db.session.query(TeamMembership).delete()
                db.session.query(Project).delete()
                db.session.query(Team).delete()
                db.session.query(ClientBillingRate).delete()
                db.session.query(CostRate).delete()
                db.session.query(NonClientBillingConfig).delete()
                db.session.query(RateCard).delete()
                db.session.query(User).delete()
                db.session.query(TeamMember).delete()
                db.session.commit()

                db.drop_all()
                db.create_all()
                created_users = _seed_reset_managers()
                _seed_master_data()
            else:
                # Clear manager foreign key references before deleting users.
                db.session.query(WorkLog).update({WorkLog.manager_user_id: None}, synchronize_session=False)
                db.session.query(ProjectDayBilling).update(
                    {ProjectDayBilling.billing_manager_user_id: None}, synchronize_session=False
                )
                db.session.query(Team).update({Team.owner_user_id: None}, synchronize_session=False)
                db.session.query(TeamMembership).delete()
                db.session.query(User).delete()
                db.session.query(TeamMember).delete()
                created_users = _seed_reset_managers()

            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise click.ClickException(f"Database reset failed: {exc}") from exc

        click.echo(f"Reset complete ({reset_scope}). Created manager users:")
        for user in created_users:
            click.echo(f"- {user.full_name}: {user.email}")

    @app.cli.command("seed")
    def seed_data() -> None:
        manager = User.query.filter_by(email="mgr1@local").first()
        if not manager:
            manager = User(
                email="mgr1@local",
                full_name="Manager One",
                password_hash=generate_password_hash("manager123"),
                role="Manager",
                is_active=True,
            )
            db.session.add(manager)
        else:
            # Keep seeded credentials deterministic across environments.
            manager.full_name = "Manager One"
            manager.password_hash = generate_password_hash("manager123")
            manager.role = "Manager"
            manager.is_active = True

        members = [
            TeamMember(
                employee_id="EMP001",
                name="Aarav Shah",
                gender="Male",
                level="Analyst1",
                is_active=True,
                default_daily_capacity_hours=8.0,
            ),
            TeamMember(
                employee_id="EMP002",
                name="Maya Rao",
                gender="Female",
                level="Associate2",
                is_active=True,
                default_daily_capacity_hours=8.0,
            ),
            TeamMember(
                employee_id="EMP003",
                name="Rohan Iyer",
                gender="Male",
                level="ProjectLeader1",
                is_active=True,
                default_daily_capacity_hours=8.0,
            ),
            TeamMember(
                employee_id="EMP004",
                name="Nina Kapoor",
                gender="Female",
                level="Manager1",
                is_active=True,
                default_daily_capacity_hours=8.0,
            ),
            TeamMember(
                employee_id="EMP005",
                name="Zara Khan",
                gender="Other",
                level="SeniorManager2",
                is_active=True,
                default_daily_capacity_hours=8.0,
            ),
            TeamMember(
                employee_id="EMP006",
                name="Ishaan Mehta",
                gender="PreferNot",
                level="Director",
                is_active=True,
                default_daily_capacity_hours=8.0,
            ),
        ]

        existing_members = {m.employee_id: m for m in TeamMember.query.all()}
        for seed_member in members:
            member = existing_members.get(seed_member.employee_id)
            if not member:
                db.session.add(seed_member)
                member = seed_member
            else:
                member.name = seed_member.name
                member.gender = seed_member.gender
                member.level = seed_member.level
                member.is_active = seed_member.is_active
                member.default_daily_capacity_hours = seed_member.default_daily_capacity_hours

        _seed_master_data()
        db.session.flush()

        # Attach each seed member to the first team by default if no membership exists.
        first_team = Team.query.order_by(Team.name.asc()).first()
        if first_team:
            for member in TeamMember.query.all():
                has_membership = TeamMembership.query.filter_by(team_member_id=member.id).first()
                if not has_membership:
                    db.session.add(
                        TeamMembership(
                            team_member_id=member.id,
                            team_id=first_team.id,
                            start_date=date(2026, 1, 1),
                            end_date=None,
                        )
                    )

        db.session.commit()

        click.echo("Seed complete: manager user plus teams, memberships, projects, and economics master data added.")
