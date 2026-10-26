import os
import sys
import click
from dotenv import load_dotenv
from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.seed import seed_database, create_initial_admin

load_dotenv()

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Initializes SQLite database tables safely without destroying existing records."""
    with app.app_context():
        db.create_all()
        admin_user = os.environ.get("ADMIN_USERNAME", "admin")
        admin_pass = os.environ.get("ADMIN_PASSWORD", "AdminPassword123!")
        admin_name = os.environ.get("ADMIN_FULL_NAME", "System Administrator")
        create_initial_admin(admin_user, admin_pass, admin_name)
        click.echo("Database initialized successfully.")


@app.cli.command("seed-db")
@click.option("--reset", is_flag=True, help="Drop all tables and recreate before seeding.")
def seed_db(reset):
    """Loads realistic, deterministic sample data for evaluation and presentation."""
    with app.app_context():
        seed_database(reset_first=reset)


@app.cli.command("create-user")
@click.option("--username", prompt=True, help="Username")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password")
@click.option("--fullname", prompt=True, help="Full Name")
@click.option("--role", type=click.Choice([Role.ADMIN, Role.STAFF]), default=Role.STAFF, help="User Role")
def create_user_cmd(username, password, fullname, role):
    """Creates a new user account via command line."""
    with app.app_context():
        existing = User.query.filter_by(username=username.strip()).first()
        if existing:
            click.echo(f"Error: User '{username}' already exists.", err=True)
            return

        user = User(
            username=username.strip(),
            full_name=fullname.strip(),
            role=role,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Successfully created {role} user: {username}")


if __name__ == "__main__":
    # If subcommands are passed, run Click CLI; otherwise start web server
    cli_commands = {"init-db", "seed-db", "create-user", "routes", "shell"}
    if len(sys.argv) > 1 and (sys.argv[1] in cli_commands or sys.argv[1].startswith("--")):
        app.cli()
    else:
        port = int(os.environ.get("PORT", 5000))
        debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
        app.run(host="127.0.0.1", port=port, debug=debug)

