from __future__ import annotations

import os
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


load_dotenv()

_SCHEMA_READY = False


def get_connection():
    return psycopg.connect(
        os.getenv("DATABASE_URL")
    )


def ensure_chat_session_memory_schema() -> None:
    """
    Create or upgrade chat session storage.

    Existing callers can continue using `filters`. New conversational
    product memory is stored in the `conversation_state` JSONB column.
    """
    global _SCHEMA_READY

    if _SCHEMA_READY:
        return

    statements = [
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            filters JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_query TEXT,
            conversation_state JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        ALTER TABLE chat_sessions
        ADD COLUMN IF NOT EXISTS conversation_state
        JSONB NOT NULL DEFAULT '{}'::jsonb
        """,
        """
        ALTER TABLE chat_sessions
        ADD COLUMN IF NOT EXISTS created_at
        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """,
        """
        ALTER TABLE chat_sessions
        ADD COLUMN IF NOT EXISTS updated_at
        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """,
        """
        CREATE INDEX IF NOT EXISTS
        idx_chat_sessions_updated_at
        ON chat_sessions (updated_at)
        """,
    ]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)

            conn.commit()

        _SCHEMA_READY = True

    except Exception as error:
        print(
            "\n========== CHAT SESSION SCHEMA ERROR =========="
        )
        print(error)
        print(
            "===============================================\n"
        )
        raise


def _as_dict(
    value: Any,
) -> dict[str, Any]:
    return (
        dict(value)
        if isinstance(value, dict)
        else {}
    )


def get_session(
    session_id: str,
) -> dict[str, Any] | None:
    """
    Return only shopping filters for backward compatibility.
    """
    ensure_chat_session_memory_schema()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT filters
                    FROM chat_sessions
                    WHERE session_id = %s
                    """,
                    (session_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return _as_dict(row[0])

    except Exception as error:
        print(
            "\n========== GET SESSION ERROR =========="
        )
        print(error)
        print(
            "=======================================\n"
        )
        return None


def get_conversation_state(
    session_id: str,
) -> dict[str, Any]:
    ensure_chat_session_memory_schema()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT conversation_state
                    FROM chat_sessions
                    WHERE session_id = %s
                    """,
                    (session_id,),
                )
                row = cur.fetchone()

        if row is None:
            return {}

        return _as_dict(row[0])

    except Exception as error:
        print(
            "\n========== GET CONVERSATION STATE ERROR =========="
        )
        print(error)
        print(
            "==================================================\n"
        )
        return {}


def save_session(
    session_id: str,
    filters: dict[str, Any] | None,
    last_query: str,
    conversation_state: (
        dict[str, Any]
        | None
    ) = None,
) -> bool:
    """
    Save filters and optionally replace conversational memory.

    When `conversation_state` is omitted, existing product memory is
    preserved instead of being overwritten.
    """
    ensure_chat_session_memory_schema()

    clean_filters = _as_dict(filters)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if conversation_state is None:
                    cur.execute(
                        """
                        INSERT INTO chat_sessions (
                            session_id,
                            filters,
                            last_query
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT (session_id)
                        DO UPDATE SET
                            filters = EXCLUDED.filters,
                            last_query = EXCLUDED.last_query,
                            updated_at = NOW()
                        """,
                        (
                            session_id,
                            Jsonb(clean_filters),
                            last_query,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO chat_sessions (
                            session_id,
                            filters,
                            last_query,
                            conversation_state
                        )
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (session_id)
                        DO UPDATE SET
                            filters = EXCLUDED.filters,
                            last_query = EXCLUDED.last_query,
                            conversation_state =
                                EXCLUDED.conversation_state,
                            updated_at = NOW()
                        """,
                        (
                            session_id,
                            Jsonb(clean_filters),
                            last_query,
                            Jsonb(
                                _as_dict(
                                    conversation_state
                                )
                            ),
                        ),
                    )

            conn.commit()

        return True

    except Exception as error:
        print(
            "\n========== SAVE SESSION ERROR =========="
        )
        print(error)
        print(
            "========================================\n"
        )
        return False


def save_conversation_state(
    session_id: str,
    conversation_state: dict[str, Any],
    *,
    filters: dict[str, Any] | None = None,
    last_query: str | None = None,
) -> bool:
    """
    Update product memory while preserving filters when they are not
    supplied.
    """
    ensure_chat_session_memory_schema()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (
                        session_id,
                        filters,
                        last_query,
                        conversation_state
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (session_id)
                    DO UPDATE SET
                        filters = COALESCE(
                            %s,
                            chat_sessions.filters
                        ),
                        last_query = COALESCE(
                            %s,
                            chat_sessions.last_query
                        ),
                        conversation_state =
                            EXCLUDED.conversation_state,
                        updated_at = NOW()
                    """,
                    (
                        session_id,
                        Jsonb(
                            _as_dict(filters)
                        ),
                        last_query,
                        Jsonb(
                            _as_dict(
                                conversation_state
                            )
                        ),
                        (
                            Jsonb(
                                _as_dict(filters)
                            )
                            if filters is not None
                            else None
                        ),
                        last_query,
                    ),
                )

            conn.commit()

        return True

    except Exception as error:
        print(
            "\n========== SAVE CONVERSATION STATE ERROR =========="
        )
        print(error)
        print(
            "===================================================\n"
        )
        return False


def delete_session(
    session_id: str,
) -> bool:
    ensure_chat_session_memory_schema()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM chat_sessions
                    WHERE session_id = %s
                    """,
                    (session_id,),
                )

            conn.commit()

        return True

    except Exception as error:
        print(
            "\n========= DELETE SESSION ERROR ========="
        )
        print(error)
        print(
            "========================================\n"
        )
        return False
