import os
import json
import psycopg

from dotenv import load_dotenv

load_dotenv()

conn = psycopg.connect(
    os.getenv("DATABASE_URL")
)


# ----------------------------------------
# Get Previous Session
# ----------------------------------------
def get_session(session_id):

    try:

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

    except Exception as e:

        print("\n========== GET SESSION ERROR ==========")
        print(e)
        print("=======================================\n")

        return None


# ----------------------------------------
# Save / Update Session
# ----------------------------------------
def save_session(session_id, filters, last_query):

    try:

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

                DO UPDATE SET

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

        return True

    except Exception as e:

        conn.rollback()

        print("\n========== SAVE SESSION ERROR ==========")
        print(e)
        print("========================================\n")

        return False


# ----------------------------------------
# Delete Session
# ----------------------------------------
def delete_session(session_id):

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM chat_sessions
                WHERE session_id = %s
                """,
                (session_id,)
            )

        conn.commit()

        return True

    except Exception as e:

        conn.rollback()

        print("\n========= DELETE SESSION ERROR =========")
        print(e)
        print("========================================\n")

        return False