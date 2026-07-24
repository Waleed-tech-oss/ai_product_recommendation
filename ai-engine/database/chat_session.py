import os
import json
import psycopg

from dotenv import load_dotenv

load_dotenv()

conn = psycopg.connect(
    os.getenv("DATABASE_URL")
)


def get_session(session_id):

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT filters
            FROM chat_sessions
            WHERE session_id = %s
            """,
            (session_id,)
        )

        row = cur.fetchone()

    if row is None:
        return None

    return row[0]


def save_session(session_id, filters, last_query):

    with conn.cursor() as cur:

        cur.execute(
            """
            INSERT INTO chat_sessions
            (
                session_id,
                filters,
                last_query
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            ON CONFLICT(session_id)
            DO UPDATE
            SET
                filters = EXCLUDED.filters,
                last_query = EXCLUDED.last_query,
                updated_at = NOW()
            """,
            (
                session_id,
                json.dumps(filters),
                last_query
            )
        )

        conn.commit()