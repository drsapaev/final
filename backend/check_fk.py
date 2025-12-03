from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///./clinic.db")

with engine.connect() as conn:
    fk = conn.execute(text("PRAGMA foreign_keys;")).scalar()
    print("foreign_keys =", fk)

    tables = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table';"
    )).fetchall()

    for t in tables:
        name = t[0]
        fks = conn.execute(text(f"PRAGMA foreign_key_list({name});")).fetchall()
        if fks:
            print(f"\nTable: {name}")
            for fk in fks:
                print(fk)
