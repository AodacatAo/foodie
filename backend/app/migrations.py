"""版本化轻量迁移（SQLite 个人量级，不引入 Alembic）。

- `schema_migrations` 表记录已应用版本号，init_db 时按序执行未应用项（事务内）。
- 每个迁移用「防重复」写法（PRAGMA 查列后再 ALTER、回填用 IS NULL 守卫），
  对全新建库（create_all 已含全部列）重放无害。
- 约定：**只增不改**。禁止把"无条件数据改写"（如旧版启动时 UPDATE menu_qty）
  放进迁移——需要回填时用 NULL/默认值守卫，且只执行一次。
"""
from datetime import datetime, timezone

from sqlalchemy.engine import Connection


def _add_column_if_missing(conn: Connection, table: str, column: str, ddl: str) -> None:
    cols = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _m001_video_and_transcript(conn: Connection) -> None:
    """视频笔记：视频文件列 + 语音转写路径列。"""
    _add_column_if_missing(conn, "recipes", "video_path", "VARCHAR(500)")
    _add_column_if_missing(conn, "import_tasks", "transcript_path", "VARCHAR(500)")


def _m002_restaurant_rating_dishes_photos(conn: Connection) -> None:
    """餐厅：我的评分、推荐菜、就餐照片；旧数据 NULL → 空列表。"""
    _add_column_if_missing(conn, "restaurants", "my_rating", "FLOAT")
    _add_column_if_missing(conn, "restaurants", "recommended_dishes", "JSON")
    _add_column_if_missing(conn, "visit_logs", "photos", "JSON")
    conn.exec_driver_sql(
        "UPDATE restaurants SET recommended_dishes = '[]' WHERE recommended_dishes IS NULL"
    )
    conn.exec_driver_sql("UPDATE visit_logs SET photos = '[]' WHERE photos IS NULL")


def _m003_menu_ordering(conn: Connection) -> None:
    """菜单点餐模块：上架/想吃/上架时间/价格/份数/分类。
    menu_qty 已废弃（购物车改为前端本地存储），列保留仅为兼容旧数据。"""
    _add_column_if_missing(conn, "recipes", "on_menu", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "recipes", "menu_want", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "recipes", "menu_at", "DATETIME")
    _add_column_if_missing(conn, "recipes", "menu_price", "FLOAT")
    _add_column_if_missing(conn, "recipes", "menu_qty", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "recipes", "menu_category", "VARCHAR(50)")


def _m004_order_status(conn: Connection) -> None:
    """订单状态机：pending(已下单) → making(制作中) → served(已上菜)。"""
    _add_column_if_missing(conn, "orders", "status", "VARCHAR(20) NOT NULL DEFAULT 'pending'")


# (版本号, 描述, 迁移函数)：版本号只增不改，已应用版本永不变更
MIGRATIONS: list[tuple[int, str, object]] = [
    (1, "视频笔记与语音转写列", _m001_video_and_transcript),
    (2, "餐厅评分/推荐菜/就餐照片列", _m002_restaurant_rating_dishes_photos),
    (3, "菜单点餐模块列", _m003_menu_ordering),
    (4, "订单状态机列", _m004_order_status),
]


def run_migrations(conn: Connection) -> list[int]:
    """在事务内按序执行未应用迁移，返回本次新应用的版本号列表。"""
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY,"
        " description TEXT,"
        " applied_at TEXT"
        ")"
    )
    applied = {
        row[0] for row in conn.exec_driver_sql("SELECT version FROM schema_migrations").fetchall()
    }
    ran: list[int] = []
    for version, desc, fn in MIGRATIONS:
        if version in applied:
            continue
        fn(conn)  # type: ignore[operator]
        conn.exec_driver_sql(
            "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?)",
            (version, desc, datetime.now(timezone.utc).isoformat()),
        )
        ran.append(version)
    return ran
