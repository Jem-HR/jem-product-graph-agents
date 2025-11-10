"""Async database connection and query tools using environment variables."""

import os
from typing import Any

import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def get_employee_by_mobile(mobile_number: str) -> dict[str, Any] | None:
    """Query employee by mobile number from the staging database (async).

    Args:
        mobile_number: The mobile number to search for.

    Returns:
        dict | None: Employee record if found, None otherwise.
                     Returns a dictionary with employee fields from app_employee table.

    Raises:
        RuntimeError: If database connection or query fails.
    """
    try:
        # Get credentials from environment
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = int(os.getenv("DB_PORT", "5432"))
        db_name = os.getenv("DB_NAME", "staging")
        db_user = os.getenv("DB_USERNAME")
        db_password = os.getenv("DB_PASSWORD")

        if not db_user or not db_password:
            raise RuntimeError(
                "Database credentials not found in environment variables. "
                "Please set DB_USERNAME and DB_PASSWORD in .env file."
            )

        # Connect to PostgreSQL asynchronously
        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
        )

        try:
            # Query employee table - only active (non-deleted) employees
            query = """
                SELECT
                    id,
                    uuid,
                    first_name,
                    last_name,
                    mobile_number,
                    email,
                    status,
                    employer_id,
                    employee_no,
                    smartwage_status,
                    date_created,
                    date_updated
                FROM app_employee
                WHERE mobile_number = $1
                  AND (deleted IS NULL OR deleted = FALSE)
                LIMIT 1;
            """

            result = await conn.fetchrow(query, mobile_number)

            # Convert asyncpg Record to dict
            if result:
                return dict(result)
            return None

        finally:
            await conn.close()

    except asyncpg.PostgresError as e:
        raise RuntimeError(f"Database error while querying employee: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error querying employee: {e}") from e


async def test_db_connection() -> bool:
    """Test database connection using environment credentials (async).

    Returns:
        bool: True if connection successful, False otherwise.
    """
    try:
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = int(os.getenv("DB_PORT", "5432"))
        db_name = os.getenv("DB_NAME", "staging")
        db_user = os.getenv("DB_USERNAME")
        db_password = os.getenv("DB_PASSWORD")

        if not db_user or not db_password:
            return False

        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
        )
        await conn.close()
        return True
    except Exception:
        return False
