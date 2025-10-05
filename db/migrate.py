from alembic import command, config
import os

# This script assumes alembic.ini is in the project root and migration scripts are in db/migrations

def run_migrations():
    alembic_cfg = config.Config(os.path.join(os.path.dirname(__file__), '../alembic.ini'))
    command.upgrade(alembic_cfg, 'head')

if __name__ == "__main__":
    run_migrations()
    print("Database migrations applied.")
