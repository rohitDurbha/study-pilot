"""The database location comes from DATABASE_URL with a local SQLite default."""

from sqlalchemy import inspect, text

import database


def test_database_url_defaults_to_the_local_sqlite_file():
    assert database.database_url({}) == f"sqlite:///{database.DB_PATH}"
    assert database.database_url({"DATABASE_URL": "   "}) == f"sqlite:///{database.DB_PATH}"


def test_database_url_uses_the_environment_when_set():
    url = "sqlite:////data/studypilot.db"
    assert database.database_url({"DATABASE_URL": f" {url} "}) == url


def test_make_engine_builds_the_schema_at_any_sqlite_path(tmp_path):
    engine = database.make_engine(f"sqlite:///{tmp_path / 'other.db'}")
    database.Base.metadata.create_all(bind=engine)

    assert (tmp_path / "other.db").exists()
    assert "documents" in inspect(engine).get_table_names()


def test_sqlite_connections_can_cross_threads(tmp_path):
    import threading

    engine = database.make_engine(f"sqlite:///{tmp_path / 'threads.db'}")
    errors = []

    def query():
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
        except Exception as exc:  # pragma: no cover - only reached on failure
            errors.append(exc)

    threads = [threading.Thread(target=query) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
