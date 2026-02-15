#!/usr/bin/env python3
import json
import sqlite3
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "smtg.db"
WEB_PATH = ROOT / "web"

ALLOWED_THEMES = {"light", "dark", "amoled", "calm_blue", "forest_green"}
ALLOWED_RESPONSES = {"start_focus", "snooze", "dismiss"}

INTEGRATIONS = {
    "instagram": {
        "supported": "partial",
        "method": "OS usage stats + foreground app detection",
        "note": "No direct content/feed API is used; behavior is inferred from app usage metadata.",
    },
    "facebook": {
        "supported": "partial",
        "method": "OS usage stats + foreground app detection",
        "note": "Direct timeline-content analytics are not available through this MVP.",
    },
    "youtube_shorts": {
        "supported": "partial",
        "method": "OS usage stats + category/session heuristics",
        "note": "Shorts-specific segmentation is heuristic-based unless native accessibility hooks are approved.",
    },
    "tiktok": {
        "supported": "partial",
        "method": "OS usage stats + session pattern heuristics",
        "note": "No API-level content inspection; app-level time monitoring only.",
    },
}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


def safe_int(value, default, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def build_behavior_analysis(conn):
    total_sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
    scroll_sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE session_type='scroll'").fetchone()["c"]
    productive_sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE productive=1").fetchone()["c"]
    avg_scroll_duration = conn.execute(
        "SELECT COALESCE(AVG(duration_min),0) AS m FROM sessions WHERE session_type='scroll'"
    ).fetchone()["m"]
    late_scroll = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM sessions
        WHERE session_type='scroll'
          AND CAST(strftime('%H', started_at) AS INTEGER) >= 22
        """
    ).fetchone()["c"]
    nudge_total = conn.execute("SELECT COUNT(*) AS c FROM nudges").fetchone()["c"]
    nudge_accept = conn.execute(
        "SELECT COUNT(*) AS c FROM nudges WHERE response='start_focus'"
    ).fetchone()["c"]

    scroll_ratio = 0 if total_sessions == 0 else round((scroll_sessions / total_sessions) * 100, 1)
    productivity_ratio = 0 if total_sessions == 0 else round((productive_sessions / total_sessions) * 100, 1)
    nudge_accept_rate = 0 if nudge_total == 0 else round((nudge_accept / nudge_total) * 100, 1)

    risk_level = "low"
    if scroll_ratio > 55 or avg_scroll_duration > 24:
        risk_level = "high"
    elif scroll_ratio > 35 or avg_scroll_duration > 16:
        risk_level = "medium"

    return {
        "risk_level": risk_level,
        "scroll_ratio_pct": scroll_ratio,
        "productive_ratio_pct": productivity_ratio,
        "avg_scroll_session_min": round(avg_scroll_duration, 1),
        "late_night_scroll_sessions": late_scroll,
        "nudge_accept_rate": nudge_accept_rate,
        "recommendations": [
            "Set a stricter night mode threshold after 10 PM." if late_scroll > 0 else "Keep night mode gentle reminders enabled.",
            "Use 10-15 minute focus blocks after each nudge.",
            "Prioritize study/work modes on weekdays.",
        ],
    }


def init_db():
    conn = db_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS profile (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          name TEXT NOT NULL DEFAULT 'User',
          goal_minutes INTEGER NOT NULL DEFAULT 120,
          timezone TEXT NOT NULL DEFAULT 'UTC',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          study_mode INTEGER NOT NULL DEFAULT 1,
          work_mode INTEGER NOT NULL DEFAULT 1,
          sleep_mode INTEGER NOT NULL DEFAULT 1,
          nudge_enabled INTEGER NOT NULL DEFAULT 1,
          nudge_threshold_min INTEGER NOT NULL DEFAULT 18,
          theme TEXT NOT NULL DEFAULT 'light',
          onboarding_done INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          app_name TEXT NOT NULL,
          session_type TEXT NOT NULL,
          duration_min INTEGER NOT NULL,
          productive INTEGER NOT NULL DEFAULT 0,
          started_at TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS focus_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          planned_min INTEGER NOT NULL,
          completed_min INTEGER NOT NULL,
          accepted_from_nudge INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nudges (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          trigger_reason TEXT NOT NULL,
          response TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subscription (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          plan TEXT NOT NULL DEFAULT 'free',
          trial_ends_at TEXT,
          updated_at TEXT NOT NULL
        );
        """
    )

    cols = [r[1] for r in cur.execute("PRAGMA table_info(settings)").fetchall()]
    if "onboarding_done" not in cols:
        cur.execute("ALTER TABLE settings ADD COLUMN onboarding_done INTEGER NOT NULL DEFAULT 0")

    ts = now_iso()

    if not cur.execute("SELECT id FROM profile WHERE id = 1").fetchone():
        cur.execute(
            "INSERT INTO profile(id, name, goal_minutes, timezone, created_at, updated_at) VALUES(1, 'User', 120, 'UTC', ?, ?)",
            (ts, ts),
        )

    if not cur.execute("SELECT id FROM settings WHERE id = 1").fetchone():
        cur.execute(
            "INSERT INTO settings(id, study_mode, work_mode, sleep_mode, nudge_enabled, nudge_threshold_min, theme, onboarding_done, updated_at) VALUES(1,1,1,1,1,18,'light',0,?)",
            (ts,),
        )

    if not cur.execute("SELECT id FROM subscription WHERE id = 1").fetchone():
        trial = (datetime.utcnow() + timedelta(days=14)).replace(microsecond=0).isoformat() + "Z"
        cur.execute(
            "INSERT INTO subscription(id, plan, trial_ends_at, updated_at) VALUES(1,'free',?,?)",
            (trial, ts),
        )

    if cur.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"] == 0:
        seed = [
            ("Instagram", "scroll", 28, 0),
            ("YouTube", "watch", 20, 0),
            ("Docs", "work", 50, 1),
            ("TikTok", "scroll", 32, 0),
            ("Chrome", "research", 25, 1),
            ("Instagram", "scroll", 18, 0),
        ]
        start = datetime.utcnow() - timedelta(days=6)
        for i, row in enumerate(seed):
            t = (start + timedelta(days=i, hours=3)).replace(microsecond=0).isoformat() + "Z"
            cur.execute(
                "INSERT INTO sessions(app_name, session_type, duration_min, productive, started_at, created_at) VALUES(?,?,?,?,?,?)",
                (row[0], row[1], row[2], row[3], t, ts),
            )

    conn.commit()
    conn.close()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        self._send_json({"error": message}, status)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            data = self.rfile.read(length)
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _send_file(self, path: Path):
        if not path.exists() or path.is_dir():
            self.send_error(404, "Not found")
            return
        content = path.read_bytes()
        ctype_map = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".webmanifest": "application/manifest+json",
        }
        self.send_response(200)
        self.send_header("Content-Type", ctype_map.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path in {"/", "/index.html"}:
            return self._send_file(WEB_PATH / "index.html")
        if path in {"/styles.css", "/script.js", "/manifest.webmanifest", "/sw.js"}:
            return self._send_file(WEB_PATH / path.lstrip("/"))
        if path.startswith("/web/"):
            return self._send_file(ROOT / path.lstrip("/"))

        conn = db_conn()

        if path == "/api/health":
            conn.close()
            return self._send_json({"ok": True, "timestamp": now_iso()})

        if path == "/api/integrations":
            conn.close()
            return self._send_json({"integrations": INTEGRATIONS})

        if path == "/api/behavior/analyze":
            payload = build_behavior_analysis(conn)
            conn.close()
            return self._send_json({"behavior": payload})

        if path == "/api/profile":
            row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
            conn.close()
            return self._send_json({"profile": row_to_dict(row)})

        if path == "/api/settings":
            row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
            conn.close()
            return self._send_json({"settings": row_to_dict(row)})

        if path == "/api/subscription":
            row = conn.execute("SELECT * FROM subscription WHERE id = 1").fetchone()
            conn.close()
            return self._send_json({"subscription": row_to_dict(row)})

        if path == "/api/dashboard":
            p = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
            total = conn.execute(
                "SELECT COALESCE(SUM(duration_min),0) as mins FROM sessions WHERE date(started_at)=date('now')"
            ).fetchone()["mins"]
            focus_done = conn.execute(
                "SELECT COALESCE(SUM(completed_min),0) as mins FROM focus_sessions WHERE date(created_at)=date('now')"
            ).fetchone()["mins"]
            scrolling = conn.execute(
                "SELECT COALESCE(SUM(duration_min),0) as mins FROM sessions WHERE session_type='scroll' AND date(started_at)=date('now')"
            ).fetchone()["mins"]
            streak = conn.execute(
                "SELECT COUNT(*) AS c FROM focus_sessions WHERE created_at >= datetime('now','-6 days')"
            ).fetchone()["c"]
            conn.close()
            score = max(0, min(100, int(100 - (scrolling * 0.8) + (focus_done * 0.6))))
            return self._send_json(
                {
                    "dashboard": {
                        "name": p["name"],
                        "goal_minutes": p["goal_minutes"],
                        "used_minutes": total,
                        "focus_saved_minutes": focus_done,
                        "focus_score": score,
                        "streak_days": min(streak, 7),
                    }
                }
            )

        if path == "/api/insights":
            weekly = conn.execute(
                """
                SELECT strftime('%w', started_at) as d, COALESCE(SUM(duration_min),0) as mins
                FROM sessions
                WHERE started_at >= datetime('now','-6 days')
                GROUP BY d
                """
            ).fetchall()
            top_hour = conn.execute(
                """
                SELECT strftime('%H', started_at) as h, COUNT(*) as c
                FROM sessions
                WHERE session_type='scroll'
                GROUP BY h
                ORDER BY c DESC, h DESC LIMIT 1
                """
            ).fetchone()
            nudge_accept = conn.execute(
                "SELECT COUNT(*) as c FROM nudges WHERE response='start_focus'"
            ).fetchone()["c"]
            nudge_total = conn.execute("SELECT COUNT(*) as c FROM nudges").fetchone()["c"]

            by_day = {str(i): 0 for i in range(7)}
            for r in weekly:
                by_day[r["d"]] = r["mins"]

            ordered = [by_day[str(i)] for i in [1, 2, 3, 4, 5, 6, 0]]
            accept_rate = 0 if nudge_total == 0 else round((nudge_accept / nudge_total) * 100, 1)
            hour = top_hour["h"] if top_hour else "22"
            behavior = build_behavior_analysis(conn)
            conn.close()

            return self._send_json(
                {
                    "insights": {
                        "weekly_minutes": ordered,
                        "time_saved_weekly": [18, 24, 31, 36],
                        "nudge_accept_rate": accept_rate,
                        "ai_sentence": f"Most scrolling happens after {hour}:00.",
                        "behavior_risk": behavior["risk_level"],
                        "scroll_ratio_pct": behavior["scroll_ratio_pct"],
                    }
                }
            )

        if path == "/api/export":
            payload = {
                "profile": row_to_dict(conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()),
                "settings": row_to_dict(conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()),
                "subscription": row_to_dict(conn.execute("SELECT * FROM subscription WHERE id = 1").fetchone()),
                "sessions": [row_to_dict(r) for r in conn.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT 100").fetchall()],
                "focus_sessions": [row_to_dict(r) for r in conn.execute("SELECT * FROM focus_sessions ORDER BY created_at DESC LIMIT 100").fetchall()],
                "nudges": [row_to_dict(r) for r in conn.execute("SELECT * FROM nudges ORDER BY created_at DESC LIMIT 100").fetchall()],
            }
            conn.close()
            return self._send_json(payload)

        conn.close()
        self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read_json()
        if data is None:
            return self._send_error(400, "Invalid JSON body")
        ts = now_iso()

        if path == "/api/sessions":
            required = ["app_name", "session_type", "duration_min"]
            if any(k not in data for k in required):
                return self._send_error(400, "Missing required fields")
            duration = safe_int(data.get("duration_min"), 1, minimum=1, maximum=600)
            conn = db_conn()
            conn.execute(
                "INSERT INTO sessions(app_name, session_type, duration_min, productive, started_at, created_at) VALUES(?,?,?,?,?,?)",
                (
                    str(data["app_name"])[:100],
                    str(data["session_type"])[:50],
                    duration,
                    safe_int(data.get("productive", 0), 0, minimum=0, maximum=1),
                    data.get("started_at", ts),
                    ts,
                ),
            )
            conn.commit()
            conn.close()
            return self._send_json({"ok": True, "message": "Session recorded"}, 201)

        if path == "/api/focus-sessions":
            planned = safe_int(data.get("planned_min", 15), 15, minimum=5, maximum=180)
            completed = safe_int(data.get("completed_min", planned), planned, minimum=1, maximum=planned)
            accepted = safe_int(data.get("accepted_from_nudge", 0), 0, minimum=0, maximum=1)
            conn = db_conn()
            conn.execute(
                "INSERT INTO focus_sessions(planned_min, completed_min, accepted_from_nudge, created_at) VALUES(?,?,?,?)",
                (planned, completed, accepted, ts),
            )
            conn.commit()
            conn.close()
            return self._send_json({"ok": True, "saved_minutes": completed}, 201)

        if path == "/api/nudges":
            reason = str(data.get("trigger_reason", "scroll_threshold"))[:100]
            response = str(data.get("response", "dismiss"))
            if response not in ALLOWED_RESPONSES:
                return self._send_error(400, "Invalid nudge response")
            conn = db_conn()
            conn.execute(
                "INSERT INTO nudges(trigger_reason, response, created_at) VALUES(?,?,?)",
                (reason, response, ts),
            )
            conn.commit()
            conn.close()
            return self._send_json({"ok": True}, 201)

        self.send_error(404, "Not found")

    def do_PUT(self):
        path = urlparse(self.path).path
        data = self._read_json()
        if data is None:
            return self._send_error(400, "Invalid JSON body")
        ts = now_iso()

        if path == "/api/profile":
            conn = db_conn()
            conn.execute(
                "UPDATE profile SET name=?, goal_minutes=?, timezone=?, updated_at=? WHERE id=1",
                (
                    str(data.get("name", "User"))[:60],
                    safe_int(data.get("goal_minutes", 120), 120, minimum=30, maximum=360),
                    str(data.get("timezone", "UTC"))[:60],
                    ts,
                ),
            )
            conn.commit()
            conn.close()
            return self._send_json({"ok": True})

        if path == "/api/settings":
            theme = str(data.get("theme", "light"))
            if theme not in ALLOWED_THEMES:
                return self._send_error(400, "Invalid theme")
            conn = db_conn()
            conn.execute(
                """
                UPDATE settings
                SET study_mode=?, work_mode=?, sleep_mode=?, nudge_enabled=?, nudge_threshold_min=?, theme=?, onboarding_done=?, updated_at=?
                WHERE id=1
                """,
                (
                    safe_int(data.get("study_mode", 1), 1, minimum=0, maximum=1),
                    safe_int(data.get("work_mode", 1), 1, minimum=0, maximum=1),
                    safe_int(data.get("sleep_mode", 1), 1, minimum=0, maximum=1),
                    safe_int(data.get("nudge_enabled", 1), 1, minimum=0, maximum=1),
                    safe_int(data.get("nudge_threshold_min", 18), 18, minimum=5, maximum=60),
                    theme,
                    safe_int(data.get("onboarding_done", 1), 1, minimum=0, maximum=1),
                    ts,
                ),
            )
            conn.commit()
            conn.close()
            return self._send_json({"ok": True})

        if path == "/api/subscription":
            plan = str(data.get("plan", "free"))
            if plan not in {"free", "pro"}:
                return self._send_error(400, "Invalid plan")
            conn = db_conn()
            conn.execute(
                "UPDATE subscription SET plan=?, updated_at=? WHERE id=1",
                (plan, ts),
            )
            conn.commit()
            conn.close()
            return self._send_json({"ok": True, "plan": plan})

        self.send_error(404, "Not found")

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path != "/api/data":
            return self.send_error(404, "Not found")
        conn = db_conn()
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM focus_sessions")
        conn.execute("DELETE FROM nudges")
        conn.commit()
        conn.close()
        self._send_json({"ok": True, "message": "Activity data deleted"})


def run(port=4173):
    init_db()
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"SMTG server running at http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
