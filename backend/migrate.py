import click
import os
import mysql.connector
from dotenv import dotenv_values

from src.utils.project_structure import get_project_root

project_root = get_project_root()

bucket_folder = os.path.join(project_root, "bucket")

def clear_database(conn):
    """
    Remove all database objects (events, triggers, views, stored routines, and tables),
    and log each operation.
    """
    cursor = conn.cursor()

    print("Disabling foreign key checks...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

    # Remove scheduled events
    cursor.execute("SHOW EVENTS;")
    events = cursor.fetchall()
    print(f"Found {len(events)} events")
    for (name,) in events:
        cursor.execute(f"DROP EVENT IF EXISTS `{name}`;")
        print(f"Dropped event: {name}")

    # Remove triggers
    cursor.execute("SHOW TRIGGERS;")
    triggers = cursor.fetchall()
    print(f"Found {len(triggers)} triggers")
    for (trigger_name, *_) in triggers:
        cursor.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`;")
        print(f"Dropped trigger: {trigger_name}")

    # Remove database views
    cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW';")
    views = cursor.fetchall()
    print(f"Found {len(views)} views")
    for (view_name, _) in views:
        cursor.execute(f"DROP VIEW IF EXISTS `{view_name}`;")
        print(f"Dropped view: {view_name}")

    # Remove stored procedures
    cursor.execute("SHOW PROCEDURE STATUS WHERE Db = DATABASE();")
    procs = cursor.fetchall()
    print(f"Found {len(procs)} stored procedures")
    for (db, name, *_) in procs:
        cursor.execute(f"DROP PROCEDURE IF EXISTS `{name}`;")
        print(f"Dropped stored procedure: {name}")

    # Remove stored functions
    cursor.execute("SHOW FUNCTION STATUS WHERE Db = DATABASE();")
    funcs = cursor.fetchall()
    print(f"Found {len(funcs)} stored functions")
    for (db, name, *_) in funcs:
        cursor.execute(f"DROP FUNCTION IF EXISTS `{name}`;")
        print(f"Dropped stored function: {name}")

    # Remove tables
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    print(f"Found {len(tables)} tables")
    for (table_name,) in tables:
        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`;")
        print(f"Dropped table: {table_name}")

    print("Re-enabling foreign key checks...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    cursor.close()

def setup_database(conn):
    """
    Initialize required tables: 'bucket' for file metadata and 'documents' for document records.
    """
    cursor = conn.cursor()

    # `objects` table schema:
    # - id: CHAR(36), primary key
    # - name: TEXT, original filename including extension
    # - mime_type: TEXT, MIME type (e.g., application/octet-stream for binary)
    # - size: BIGINT, file size in bytes recorded at upload
    # - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    # - last_modified: TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `objects` (
            `id` CHAR(36) PRIMARY KEY NOT NULL,
            `name` TEXT NOT NULL,
            `mime_type` TEXT NOT NULL,
            `size` BIGINT NOT NULL,
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `last_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
    """)
    print("Created table: objects")

    # `documents` table schema:
    # - id: CHAR(36), primary key
    # - title: TEXT NOT NULL
    # - author: TEXT NOT NULL
    # - description: TEXT, nullable
    # - object_id: CHAR(36), nullable, foreign key to bucket(id)
    # - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    # - last_modified: TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `documents` (
            `id` CHAR(36) PRIMARY KEY NOT NULL,
            `title` TEXT NOT NULL,
            `author` TEXT NOT NULL,
            `description` TEXT,
            `object_id` CHAR(36),
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `last_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (`object_id`) REFERENCES `objects` (`id`)
        ) ENGINE=InnoDB;
    """)
    print("Created table: documents")

    conn.commit()
    cursor.close()

@click.command()
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt and proceed automatically')
def migrate(yes):
    """
    Command-line tool to reset and initialize the MySQL database schema.
    """
    if not yes and not click.confirm(
        "This operation will delete all existing data. Do you wish to continue?", default=False
    ):
        click.echo("Migration aborted.")
        exit(0)

    project_root = get_project_root()
    env_path = os.path.join(project_root, "servers", "mysql", ".env")
    db_config = dotenv_values(env_path)

    conn = mysql.connector.connect(
        host=db_config.get('MYSQL_HOST', 'localhost'),
        port=int(db_config.get('MYSQL_PORT', 3306)),
        user=db_config['MYSQL_USER'],
        password=db_config['MYSQL_PASSWORD'],
        database=db_config['MYSQL_DATABASE'],
    )

    print("Clearing database...")
    clear_database(conn)

    print("Setting up database schema...")
    setup_database(conn)

    print("Clearing old bucket files...")
    bucket_files = os.listdir(bucket_folder)
    for file in bucket_files:
        os.remove(os.path.join(bucket_folder, file))
    print(f"Removed {len(bucket_files)} old bucket files.")



    conn.close()
    click.echo("Migration complete.")

if __name__ == "__main__":
    migrate()
