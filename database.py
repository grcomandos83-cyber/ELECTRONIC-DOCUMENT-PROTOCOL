import sqlite3
import os
import sys
import shutil
from datetime import datetime

def _get_base_data_dir():
    # 1. Portable / Development mode: if protocol.db exists in current directory, use it
    if os.path.exists("protocol.db"):
        return os.getcwd()
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else os.getcwd()
    if os.path.exists(os.path.join(app_dir, "protocol.db")) or not getattr(sys, "frozen", False):
        return app_dir
    # 2. Installed mode: keep user data persistently in %APPDATA%\Protokollo so updates never overwrite it
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    data_dir = os.path.join(appdata, "Protokollo")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

BASE_DIR = _get_base_data_dir()
DB_FILE = os.path.join(BASE_DIR, "protocol.db")
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "attachments")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

# Schema versioning
CURRENT_SCHEMA_VERSION = 2

# Master specification of expected columns for table 'records'
# Format: column_name: column_definition (with sensible DEFAULT values to ensure zero data loss)
EXPECTED_COLUMNS = {
    "protocol_number": "INTEGER NOT NULL DEFAULT 0",
    "year": "INTEGER NOT NULL DEFAULT 0",
    "protocol_date": "TEXT DEFAULT ''",
    "doc_class": "TEXT DEFAULT ''",
    "incoming_date": "TEXT DEFAULT ''",
    "doc_type": "TEXT DEFAULT ''",
    "incoming_origin": "TEXT DEFAULT ''",
    "incoming_desc": "TEXT DEFAULT ''",
    "incoming_file": "TEXT DEFAULT ''",
    "processing_office": "TEXT DEFAULT ''",
    "completed": "INTEGER DEFAULT 0",
    "remarks": "TEXT DEFAULT ''",
    "outgoing_date": "TEXT DEFAULT ''",
    "outgoing_dest": "TEXT DEFAULT ''",
    "outgoing_desc": "TEXT DEFAULT ''",
    "outgoing_file": "TEXT DEFAULT ''",
    "extra_data": "TEXT DEFAULT '{}'",  # JSON field for future expansion / custom fields
}


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def get_table_columns(cursor, table_name="records"):
    """
    Returns a dictionary of existing column metadata for the given table.
    """
    cursor.execute(f"PRAGMA table_info({table_name});")
    rows = cursor.fetchall()
    return {row[1]: {"type": row[2], "notnull": row[3], "dflt_value": row[4], "pk": row[5]} for row in rows}


def create_safety_backup(reason="migration"):
    """
    Creates an automatic safety backup before performing schema changes or migrations.
    """
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        return None
    if not os.path.exists(BACKUPS_DIR):
        os.makedirs(BACKUPS_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"protocol_backup_{reason}_{timestamp}.db"
    backup_path = os.path.join(BACKUPS_DIR, backup_filename)
    try:
        shutil.copy2(DB_FILE, backup_path)
        print(f"Safety backup created at: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Warning: Failed to create safety backup: {e}")
        return None


def sync_table_columns(cursor, table_name="records"):
    """
    Self-healing schema synchronizer:
    Compares existing table columns with EXPECTED_COLUMNS and automatically executes
    ALTER TABLE ADD COLUMN for any missing columns without affecting existing data.
    """
    existing_cols = get_table_columns(cursor, table_name)
    added_columns = []
    for col_name, col_def in EXPECTED_COLUMNS.items():
        if col_name not in existing_cols:
            alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def};"
            cursor.execute(alter_query)
            added_columns.append(col_name)
            print(f"Schema Upgrade: Added column '{col_name}' to table '{table_name}'.")
    return added_columns


def run_migrations(conn):
    """
    Executes version-controlled schema migrations and ensures self-healing column synchronization.
    """
    cursor = conn.cursor()

    # Enable foreign keys and query user_version
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA user_version;")
    row = cursor.fetchone()
    db_version = row[0] if row else 0

    # 1. Base table creation if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocol_number INTEGER NOT NULL,
            year INTEGER NOT NULL,
            protocol_date TEXT,
            doc_class TEXT,
            incoming_date TEXT,
            doc_type TEXT,
            incoming_origin TEXT,
            incoming_desc TEXT,
            incoming_file TEXT,
            processing_office TEXT,
            completed INTEGER DEFAULT 0,
            remarks TEXT,
            outgoing_date TEXT,
            outgoing_dest TEXT,
            outgoing_desc TEXT,
            outgoing_file TEXT
        );
    """)

    # 2. If upgrading or migrating, take a safety backup
    if db_version < CURRENT_SCHEMA_VERSION and os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
        create_safety_backup(f"v{db_version}_to_v{CURRENT_SCHEMA_VERSION}")

    # 3. Dynamic schema auto-sync (adds any missing columns like extra_data)
    sync_table_columns(cursor, "records")

    # 4. Indexes for performance and quick lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_protocol_num_year ON records(protocol_number, year);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_year ON records(year);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_doc_class ON records(doc_class);")

    # 5. Update user_version pragma
    if db_version < CURRENT_SCHEMA_VERSION:
        cursor.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")
        print(f"Database schema version updated from {db_version} to {CURRENT_SCHEMA_VERSION}.")

    conn.commit()


def init_db():
    """Initializes the database, directories, and executes migrations."""
    # Ensure attachments and backups directories exist
    for directory in (ATTACHMENTS_DIR, BACKUPS_DIR):
        if not os.path.exists(directory):
            os.makedirs(directory)

    conn = get_db_connection()
    try:
        run_migrations(conn)
    finally:
        conn.close()


def get_db_version():
    """Returns the current schema version stored in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version;")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def get_next_protocol_number(year):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(protocol_number) FROM records WHERE year = ?", (year,)
    )
    row = cursor.fetchone()
    conn.close()
    if row[0] is not None:
        return row[0] + 1
    return 1


def insert_record(data):
    """
    Inserts a new record dynamically.
    Auto-assigns the next protocol number for the record's year if not provided or 0.
    Dynamically maps fields to available columns in the database, ignoring non-existent columns.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    year = data.get('year') or datetime.now().year
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = datetime.now().year

    protocol_num = data.get('protocol_number')
    if not protocol_num or protocol_num == 0 or str(protocol_num) == '0':
        protocol_num = get_next_protocol_number(year)
    else:
        try:
            protocol_num = int(protocol_num)
        except (ValueError, TypeError):
            protocol_num = get_next_protocol_number(year)

    available_cols = get_table_columns(cursor, "records")

    payload = dict(data)
    payload['year'] = year
    payload['protocol_number'] = protocol_num

    # Filter payload to only include columns that actually exist in the DB (excluding primary key 'id')
    valid_cols = [col for col in payload.keys() if col in available_cols and col != 'id']

    col_names = ", ".join(valid_cols)
    placeholders = ", ".join(["?"] * len(valid_cols))
    values = [payload[col] for col in valid_cols]

    sql = f"INSERT INTO records ({col_names}) VALUES ({placeholders})"
    cursor.execute(sql, values)
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id, protocol_num


def update_record(record_id, data):
    """
    Updates an existing record dynamically based on available table columns.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    available_cols = get_table_columns(cursor, "records")
    payload = dict(data)

    # Filter payload to only existing columns, excluding primary key 'id'
    valid_cols = [col for col in payload.keys() if col in available_cols and col != 'id']
    if not valid_cols:
        conn.close()
        return

    set_clauses = ", ".join([f"{col} = ?" for col in valid_cols])
    values = [payload[col] for col in valid_cols]
    values.append(record_id)

    sql = f"UPDATE records SET {set_clauses} WHERE id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()


def delete_record(record_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def get_all_records(year_filter=None, search_field=None, search_query=None):
    """
    Fetches records, applying optional filters.
    Returns list of dicts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM records WHERE 1=1"
    params = []

    if year_filter and year_filter != "Όλα" and str(year_filter).isdigit():
        query += " AND year = ?"
        params.append(int(year_filter))

    if search_field and search_query:
        query_map = {
            "Προέρχεται": "incoming_origin",
            "Αποστέλλεται": "outgoing_dest",
            "Γραφείο Διεκπεραίωσης": "processing_office",
            "ΠΕΡΙΓΡ. ΕΙΣΕΡΧ.": "incoming_desc",
            "ΠΕΡΙΓΡ. ΕΞΕΡΧ.": "outgoing_desc"
        }
        db_column = query_map.get(search_field)
        if db_column:
            query += f" AND {db_column} LIKE ?"
            params.append(f"%{search_query}%")

    query += " ORDER BY year DESC, protocol_number ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_years():
    """Returns a sorted list of unique years in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT year FROM records ORDER BY year DESC")
    rows = cursor.fetchall()
    conn.close()
    years = [row[0] for row in rows]
    current_year = datetime.now().year
    if current_year not in years:
        years.insert(0, current_year)
    return sorted(list(set(years)), reverse=True)


def copy_to_attachments(source_path):
    """Copies a file to the attachments directory and returns its relative path."""
    if not source_path or not os.path.exists(source_path):
        return ""

    if not os.path.exists(ATTACHMENTS_DIR):
        os.makedirs(ATTACHMENTS_DIR)

    filename = os.path.basename(source_path)
    unique_prefix = datetime.now().strftime("%Y%m%d%H%M%S_")
    dest_filename = unique_prefix + filename
    dest_path = os.path.join(ATTACHMENTS_DIR, dest_filename)

    shutil.copy2(source_path, dest_path)
    return dest_path


def create_backup(dest_path):
    """Backs up the database file to a destination path."""
    if os.path.exists(DB_FILE):
        shutil.copy2(DB_FILE, dest_path)
        return True
    return False


def restore_backup(src_path):
    """Restores the database from a backup path."""
    if os.path.exists(src_path):
        temp_backup = DB_FILE + ".tmp"
        if os.path.exists(DB_FILE):
            shutil.copy2(DB_FILE, temp_backup)
        try:
            shutil.copy2(src_path, DB_FILE)
            if os.path.exists(temp_backup):
                os.remove(temp_backup)
            # Run migrations on restored database in case it's from an older schema version
            init_db()
            return True
        except Exception as e:
            if os.path.exists(temp_backup):
                shutil.copy2(temp_backup, DB_FILE)
                os.remove(temp_backup)
            raise e
    return False


def reset_database():
    """
    Creates an automatic safety backup, then completely clears all records
    and resets auto-increment sequence counters to factory state.
    """
    create_safety_backup("pre_user_reset")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records;")
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='records';")
    except Exception:
        pass
    conn.commit()
    conn.close()
    init_db()
    return True


def ui_to_db_date(date_str):
    if not date_str or not date_str.strip():
        return ""
    try:
        dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Μη έγκυρη ημερομηνία: {date_str}. Παρακαλώ χρησιμοποιήστε τη μορφή ΗΗ/ΜΜ/ΕΕΕΕ.")


def db_to_ui_date(date_str):
    if not date_str or not date_str.strip():
        return ""
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return date_str


def search_advanced(target_type=None, date_field="protocol_date", start_date=None, end_date=None,
                    year_filter=None, entity_filter=None, doc_type_filter=None, desc_filter=None):
    """
    Advanced multi-criteria search for incoming/outgoing protocols.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM records WHERE 1=1"
    params = []

    if target_type == "ΕΙΣΕΡΧΟΜΕΝΑ":
        query += " AND doc_class IN ('ΕΙΣΕΡΧΟΜΕΝΑ', 'ΕΙΣΕΡΧΟΜΕΝΟ', 'ΜΕ ΑΠΑΝΤΗΣΗ', 'ΕΙΣΕΡΧΟΜΕΝΟ & ΕΞΕΡΧΟΜΕΝΟ')"
    elif target_type == "ΕΞΕΡΧΟΜΕΝΑ":
        query += " AND doc_class IN ('ΕΞΕΡΧΟΜΕΝΑ', 'ΕΞΕΡΧΟΜΕΝΟ', 'ΜΕ ΑΠΑΝΤΗΣΗ', 'ΕΙΣΕΡΧΟΜΕΝΟ & ΕΞΕΡΧΟΜΕΝΟ')"

    if start_date:
        query += f" AND {date_field} >= ?"
        params.append(start_date)
    if end_date:
        query += f" AND {date_field} <= ?"
        params.append(end_date)

    if year_filter and str(year_filter).isdigit() and str(year_filter) != "Όλα":
        query += " AND year = ?"
        params.append(int(year_filter))

    if entity_filter and entity_filter.strip():
        if target_type == "ΕΞΕΡΧΟΜΕΝΑ":
            query += " AND outgoing_dest LIKE ?"
            params.append(f"%{entity_filter.strip()}%")
        else:
            query += " AND incoming_origin LIKE ?"
            params.append(f"%{entity_filter.strip()}%")

    if doc_type_filter and doc_type_filter.strip():
        query += " AND doc_type LIKE ?"
        params.append(f"%{doc_type_filter.strip()}%")

    if desc_filter and desc_filter.strip():
        if target_type == "ΕΞΕΡΧΟΜΕΝΑ":
            query += " AND outgoing_desc LIKE ?"
            params.append(f"%{desc_filter.strip()}%")
        else:
            query += " AND incoming_desc LIKE ?"
            params.append(f"%{desc_filter.strip()}%")

    query += " ORDER BY year DESC, protocol_number ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
