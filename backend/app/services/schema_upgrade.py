from sqlalchemy import inspect, text

# (bảng, cột, kiểu SQL Server, kiểu SQLite): các cột thêm sau khi bảng đã được tạo
NEW_COLUMNS = [
    ("playbook_steps", "reference", "NVARCHAR(100) NULL", "VARCHAR(100)"),
    ("alerts", "ml_priority", "INT NULL", "INTEGER"),
    ("alerts", "ml_zone", "NVARCHAR(20) NULL", "VARCHAR(20)"),
    ("alerts", "ml_result", "NVARCHAR(MAX) NULL", "TEXT"),
]


def ensure_schema(engine):
    """Bổ sung các cột còn thiếu (create_all không sửa bảng có sẵn)."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for table, column, mssql_type, sqlite_type in NEW_COLUMNS:
        if table not in tables:
            continue
        if column in {c["name"] for c in insp.get_columns(table)}:
            continue
        if engine.dialect.name == "mssql":
            ddl = f"ALTER TABLE {table} ADD {column} {mssql_type}"
        else:
            ddl = f"ALTER TABLE {table} ADD COLUMN {column} {sqlite_type}"
        with engine.begin() as conn:
            conn.execute(text(ddl))
