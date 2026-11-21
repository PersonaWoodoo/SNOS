import aiosqlite
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'admin',
    permissions TEXT NOT NULL DEFAULT '',
    added_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_id INTEGER,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_db(path: str, owner_id: int):
    Path(path).parent.mkdir(parents=True, exist_ok=True) if Path(path).parent != Path(".") else None
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        # Владелец не хранится как обычный админ: его полномочия определяются OWNER_ID.
        await db.commit()

async def remember_user(path: str, user_id: int, username: str | None, first_name: str | None):
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO users(user_id, username, first_name) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (user_id, username, first_name),
        )
        await db.commit()

async def add_admin(path: str, user_id: int, permissions: list[str], added_by: int):
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO admins(user_id, role, permissions, added_by) VALUES(?, 'admin', ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET permissions=excluded.permissions, added_by=excluded.added_by",
            (user_id, ",".join(sorted(set(permissions))), added_by),
        )
        await db.execute(
            "INSERT INTO audit_log(actor_id, action, target_id, details) VALUES(?,?,?,?)",
            (added_by, "admin_added_or_updated", user_id, ",".join(sorted(set(permissions)))),
        )
        await db.commit()

async def remove_admin(path: str, user_id: int, actor_id: int):
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        await db.execute(
            "INSERT INTO audit_log(actor_id, action, target_id) VALUES(?,?,?)",
            (actor_id, "admin_removed", user_id),
        )
        await db.commit()

async def get_admin(path: str, user_id: int):
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("SELECT permissions FROM admins WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return set(filter(None, row[0].split(","))) if row else set()

async def list_admins(path: str):
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("SELECT user_id, permissions, added_by, created_at FROM admins ORDER BY created_at")
        return await cur.fetchall()

async def log_action(path: str, actor_id: int, action: str, target_id=None, details=None):
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO audit_log(actor_id, action, target_id, details) VALUES(?,?,?,?)",
            (actor_id, action, target_id, details),
        )
        await db.commit()

async def stats(path: str):
    async with aiosqlite.connect(path) as db:
        users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        admins = (await (await db.execute("SELECT COUNT(*) FROM admins")).fetchone())[0]
        return users, admins
