"""SQLite local. No network, accounts or third-party dependencies."""
from __future__ import annotations

import secrets
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


class LocalStore:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "viajeamigos.db"
        self._lock = threading.RLock()
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("""CREATE TABLE IF NOT EXISTS trips (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE, lat REAL, lon REAL, updated_at TEXT,
                UNIQUE(trip_id,name), FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS local_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL,
                title TEXT NOT NULL, day TEXT NOT NULL, hour TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS local_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL,
                path TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(trip_id,path), FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL,
                title TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
                FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE)""")

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def setting(self, key, default=""):
        with self._lock, self._connect() as conn:
            result = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return result[0] if result else default

    def set_setting(self, key, value):
        with self._lock, self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)", (key, str(value)))

    def create_trip(self, title):
        title = title.strip()
        if not 3 <= len(title) <= 70:
            raise ValueError("El nombre del viaje debe tener de 3 a 70 caracteres.")
        trip_id = secrets.token_hex(6).upper()
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO trips(id,title,created_at) VALUES (?,?,?)",
                         (trip_id, title, datetime.now().isoformat(timespec="minutes")))
        self.set_setting("active_trip", trip_id)
        self._migrate_old_data_once(trip_id)
        return trip_id

    def _migrate_old_data_once(self, trip_id):
        """Preserve events and photos saved by previous Firebase-optional version."""
        if self.setting("old_data_migrated") == "1":
            return
        with self._lock, self._connect() as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "events" in tables:
                conn.execute("""INSERT INTO local_events(trip_id,title,day,hour,description)
                    SELECT ?,title,day,hour,description FROM events""", (trip_id,))
            if "photos" in tables:
                conn.execute("""INSERT OR IGNORE INTO local_photos(trip_id,path,created_at)
                    SELECT ?,path,created_at FROM photos""", (trip_id,))
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('old_data_migrated','1')")

    def trips(self):
        with self._lock, self._connect() as conn:
            records = conn.execute("SELECT id,title,created_at FROM trips ORDER BY created_at DESC, rowid DESC").fetchall()
        return [{"id": a, "title": b, "created_at": c} for a,b,c in records]

    def trip(self, trip_id):
        with self._lock, self._connect() as conn:
            record = conn.execute("SELECT id,title,created_at FROM trips WHERE id=?", (trip_id,)).fetchone()
        return dict(zip(("id", "title", "created_at"), record)) if record else None

    def active_trip(self):
        active = self.setting("active_trip")
        return self.trip(active)

    def select_trip(self, trip_id):
        if not self.trip(trip_id):
            raise ValueError("Ese viaje no existe.")
        self.set_setting("active_trip", trip_id)

    def delete_trip(self, trip_id):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM trips WHERE id=?", (trip_id,))
        if self.setting("active_trip") == trip_id:
            choices = self.trips()
            self.set_setting("active_trip", choices[0]["id"] if choices else "")

    def _require_trip(self, trip_id):
        if not self.trip(trip_id):
            raise ValueError("Primero creá o seleccioná un viaje.")

    def add_member(self, trip_id, name, lat=None, lon=None):
        self._require_trip(trip_id)
        name = name.strip()
        if not 2 <= len(name) <= 45:
            raise ValueError("El nombre debe tener de 2 a 45 caracteres.")
        if lat is not None or lon is not None:
            lat, lon = self.validate_coords(lat, lon)
        with self._lock, self._connect() as conn:
            try:
                conn.execute("INSERT INTO members(trip_id,name,lat,lon,updated_at) VALUES (?,?,?,?,?)",
                             (trip_id, name, lat, lon, datetime.now().isoformat(timespec="minutes") if lat is not None else None))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Ese integrante ya está agregado al viaje.") from exc

    def members(self, trip_id):
        with self._lock, self._connect() as conn:
            records = conn.execute("SELECT id,name,lat,lon,updated_at FROM members WHERE trip_id=? ORDER BY name COLLATE NOCASE", (trip_id,)).fetchall()
        return [dict(zip(("id", "name", "lat", "lon", "updated_at"), x)) for x in records]

    def set_member_position(self, trip_id, member_id, lat, lon):
        lat, lon = self.validate_coords(lat, lon)
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE members SET lat=?,lon=?,updated_at=? WHERE trip_id=? AND id=?",
                         (lat, lon, datetime.now().isoformat(timespec="minutes"), trip_id, member_id))

    def clear_member_position(self, trip_id, member_id):
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE members SET lat=NULL,lon=NULL,updated_at=NULL WHERE trip_id=? AND id=?", (trip_id, member_id))

    def delete_member(self, trip_id, member_id):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM members WHERE trip_id=? AND id=?", (trip_id, member_id))

    @staticmethod
    def validate_coords(lat, lon):
        try:
            a, b = float(lat), float(lon)
            if not -90 <= a <= 90 or not -180 <= b <= 180:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Coordenadas inválidas: latitud entre -90 y 90; longitud entre -180 y 180.")
        return a, b

    def add_event(self, trip_id, title, day, hour, description=""):
        self._require_trip(trip_id)
        title = title.strip()
        if not 3 <= len(title) <= 100:
            raise ValueError("La actividad debe tener de 3 a 100 caracteres.")
        try:
            if datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d") != day:
                raise ValueError()
            if datetime.strptime(hour, "%H:%M").strftime("%H:%M") != hour:
                raise ValueError()
        except ValueError:
            raise ValueError("Usá fecha AAAA-MM-DD y hora HH:MM.")
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO local_events(trip_id,title,day,hour,description) VALUES (?,?,?,?,?)",
                         (trip_id, title, day, hour, description.strip()[:600]))

    def events(self, trip_id):
        with self._lock, self._connect() as conn:
            records = conn.execute("""SELECT id,title,day,hour,description FROM local_events
                              WHERE trip_id=? ORDER BY day,hour,id""", (trip_id,)).fetchall()
        return [dict(zip(("id", "title", "date", "time", "description"), x)) for x in records]

    def delete_event(self, trip_id, event_id):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM local_events WHERE trip_id=? AND id=?", (trip_id, event_id))

    def add_photo(self, trip_id, path):
        self._require_trip(trip_id)
        path = Path(path)
        if not path.is_file():
            raise ValueError("El archivo de la foto no existe.")
        with self._lock, self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO local_photos(trip_id,path,created_at) VALUES (?,?,?)",
                         (trip_id, str(path), datetime.now().strftime("%d/%m/%Y %H:%M")))

    def photos(self, trip_id):
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT id,path,created_at FROM local_photos WHERE trip_id=? ORDER BY id DESC", (trip_id,)).fetchall()
        return [dict(zip(("id", "path", "created_at"), x)) for x in rows if Path(x[1]).is_file()]

    def delete_photo(self, trip_id, photo_id):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM local_photos WHERE trip_id=? AND id=?", (trip_id, photo_id))
        # Deliberately leave original file untouched; other trips could reference it.

    def add_place(self, trip_id, title, lat, lon):
        self._require_trip(trip_id)
        title = title.strip()
        if not 2 <= len(title) <= 70:
            raise ValueError("El lugar debe tener de 2 a 70 caracteres.")
        lat, lon = self.validate_coords(lat, lon)
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO places(trip_id,title,lat,lon) VALUES (?,?,?,?)", (trip_id, title, lat, lon))

    def places(self, trip_id):
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT id,title,lat,lon FROM places WHERE trip_id=? ORDER BY id", (trip_id,)).fetchall()
        return [dict(zip(("id", "title", "lat", "lon"), x)) for x in rows]

    def delete_place(self, trip_id, place_id):
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM places WHERE trip_id=? AND id=?", (trip_id, place_id))
