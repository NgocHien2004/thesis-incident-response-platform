from sqlalchemy import inspect, text


def ensure_schema(engine):
    """Bổ sung các cột thêm sau khi bảng đã được tạo (create_all không sửa bảng có sẵn)."""
    insp = inspect(engine)
    if "playbook_steps" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("playbook_steps")}
    if "reference" not in cols:
        if engine.dialect.name == "mssql":
            ddl = "ALTER TABLE playbook_steps ADD reference NVARCHAR(100) NULL"
        else:
            ddl = "ALTER TABLE playbook_steps ADD COLUMN reference VARCHAR(100)"
        with engine.begin() as conn:
            conn.execute(text(ddl))
