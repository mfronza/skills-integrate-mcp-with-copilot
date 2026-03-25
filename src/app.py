"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

DB_DIR = current_dir / "data"
DB_PATH = DB_DIR / "school.db"

# Seed data used to initialize a fresh database.
DEFAULT_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with row access by column name."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create schema and seed data when database is empty."""
    DB_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK (max_participants > 0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                FOREIGN KEY (activity_id) REFERENCES activities (id) ON DELETE CASCADE,
                UNIQUE (activity_id, email)
            )
            """
        )

        existing_count = conn.execute(
            "SELECT COUNT(*) AS total FROM activities"
        ).fetchone()["total"]

        if existing_count == 0:
            for name, details in DEFAULT_ACTIVITIES.items():
                cursor = conn.execute(
                    """
                    INSERT INTO activities (name, description, schedule, max_participants)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        details["description"],
                        details["schedule"],
                        details["max_participants"],
                    ),
                )
                activity_id = cursor.lastrowid
                for email in details["participants"]:
                    conn.execute(
                        """
                        INSERT INTO participants (activity_id, email)
                        VALUES (?, ?)
                        """,
                        (activity_id, email),
                    )


init_db()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with get_connection() as conn:
        activity_rows = conn.execute(
            """
            SELECT id, name, description, schedule, max_participants
            FROM activities
            ORDER BY name ASC
            """
        ).fetchall()
        participant_rows = conn.execute(
            """
            SELECT activity_id, email
            FROM participants
            ORDER BY email ASC
            """
        ).fetchall()

    participants_by_activity: dict[int, list[str]] = {}
    for row in participant_rows:
        participants_by_activity.setdefault(row["activity_id"], []).append(row["email"])

    activities: dict[str, dict] = {}
    for row in activity_rows:
        activities[row["name"]] = {
            "description": row["description"],
            "schedule": row["schedule"],
            "max_participants": row["max_participants"],
            "participants": participants_by_activity.get(row["id"], []),
        }

    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    with get_connection() as conn:
        activity = conn.execute(
            """
            SELECT id, max_participants
            FROM activities
            WHERE name = ?
            """,
            (activity_name,),
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant_count = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM participants
            WHERE activity_id = ?
            """,
            (activity["id"],),
        ).fetchone()["total"]

        if participant_count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is full")

        already_signed_up = conn.execute(
            """
            SELECT 1
            FROM participants
            WHERE activity_id = ? AND email = ?
            """,
            (activity["id"], email),
        ).fetchone()
        if already_signed_up is not None:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up"
            )

        conn.execute(
            """
            INSERT INTO participants (activity_id, email)
            VALUES (?, ?)
            """,
            (activity["id"], email),
        )

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    with get_connection() as conn:
        activity = conn.execute(
            """
            SELECT id
            FROM activities
            WHERE name = ?
            """,
            (activity_name,),
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        existing = conn.execute(
            """
            SELECT 1
            FROM participants
            WHERE activity_id = ? AND email = ?
            """,
            (activity["id"], email),
        ).fetchone()
        if existing is None:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        conn.execute(
            """
            DELETE FROM participants
            WHERE activity_id = ? AND email = ?
            """,
            (activity["id"], email),
        )

    return {"message": f"Unregistered {email} from {activity_name}"}
