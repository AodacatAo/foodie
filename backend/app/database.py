"""数据库：SQLite(WAL) + SQLAlchemy + FTS5 全文搜索（外部内容表 + 触发器自动同步）。"""
import sqlite3

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# FTS5 中文分词：SQLite >= 3.34 用 trigram（天然支持中文子串匹配），否则 unicode61
_sqlite_ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
FTS_TOKENIZER = "trigram" if _sqlite_ver >= (3, 34, 0) else "unicode61"

_FTS_STATEMENTS = [
    f"""
CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
  title, description, ingredients_text, steps_text, tags_text,
  content='recipes', content_rowid='id', tokenize='{FTS_TOKENIZER}'
)
""",
    """
CREATE TRIGGER IF NOT EXISTS recipes_ai AFTER INSERT ON recipes BEGIN
  INSERT INTO recipes_fts(rowid, title, description, ingredients_text, steps_text, tags_text)
  VALUES (new.id, new.title, new.description, new.ingredients_text, new.steps_text, new.tags_text);
END
""",
    """
CREATE TRIGGER IF NOT EXISTS recipes_ad AFTER DELETE ON recipes BEGIN
  INSERT INTO recipes_fts(recipes_fts, rowid, title, description, ingredients_text, steps_text, tags_text)
  VALUES ('delete', old.id, old.title, old.description, old.ingredients_text, old.steps_text, old.tags_text);
END
""",
    """
CREATE TRIGGER IF NOT EXISTS recipes_au AFTER UPDATE ON recipes BEGIN
  INSERT INTO recipes_fts(recipes_fts, rowid, title, description, ingredients_text, steps_text, tags_text)
  VALUES ('delete', old.id, old.title, old.description, old.ingredients_text, old.steps_text, old.tags_text);
  INSERT INTO recipes_fts(rowid, title, description, ingredients_text, steps_text, tags_text)
  VALUES (new.id, new.title, new.description, new.ingredients_text, new.steps_text, new.tags_text);
END
""",
    # ---- 模块二：餐厅 FTS ----
    f"""
CREATE VIRTUAL TABLE IF NOT EXISTS restaurants_fts USING fts5(
  name, cuisine, address, tags_text,
  content='restaurants', content_rowid='id', tokenize='{FTS_TOKENIZER}'
)
""",
    """
CREATE TRIGGER IF NOT EXISTS restaurants_ai AFTER INSERT ON restaurants BEGIN
  INSERT INTO restaurants_fts(rowid, name, cuisine, address, tags_text)
  VALUES (new.id, new.name, new.cuisine, new.address, new.tags_text);
END
""",
    """
CREATE TRIGGER IF NOT EXISTS restaurants_ad AFTER DELETE ON restaurants BEGIN
  INSERT INTO restaurants_fts(restaurants_fts, rowid, name, cuisine, address, tags_text)
  VALUES ('delete', old.id, old.name, old.cuisine, old.address, old.tags_text);
END
""",
    """
CREATE TRIGGER IF NOT EXISTS restaurants_au AFTER UPDATE ON restaurants BEGIN
  INSERT INTO restaurants_fts(restaurants_fts, rowid, name, cuisine, address, tags_text)
  VALUES ('delete', old.id, old.name, old.cuisine, old.address, old.tags_text);
  INSERT INTO restaurants_fts(rowid, name, cuisine, address, tags_text)
  VALUES (new.id, new.name, new.cuisine, new.address, new.tags_text);
END
""",
]


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for stmt in _FTS_STATEMENTS:
            conn.exec_driver_sql(stmt)
        # 轻量迁移：为已有库补充新增列
        _add_column_if_missing(conn, "recipes", "video_path", "VARCHAR(500)")
        _add_column_if_missing(conn, "import_tasks", "transcript_path", "VARCHAR(500)")
        _add_column_if_missing(conn, "restaurants", "my_rating", "FLOAT")
        _add_column_if_missing(conn, "restaurants", "recommended_dishes", "JSON")
        _add_column_if_missing(conn, "visit_logs", "photos", "JSON")
        # 旧数据回填：NULL → 空列表
        conn.exec_driver_sql(
            "UPDATE restaurants SET recommended_dishes = '[]' WHERE recommended_dishes IS NULL"
        )
        conn.exec_driver_sql("UPDATE visit_logs SET photos = '[]' WHERE photos IS NULL")

def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    cols = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def rebuild_fts() -> None:
    """FTS 索引重建（维护用）。"""
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO recipes_fts(recipes_fts) VALUES('rebuild')")
