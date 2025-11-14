"""Seed leave management data for testing.

This script initializes leave balances for existing employees.
Run this after applying the schema migration.
"""

import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()


async def seed_leave_data():
    """Initialize leave balances for all active employees."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        raise ValueError("Neo4j credentials not found in environment variables")

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    try:
        async with driver.session() as session:
            # Get current year
            current_year = datetime.now().year

            print(f"Initializing leave balances for year {current_year}...")

            # Initialize annual leave balances (21 days per year - South African standard)
            result = await session.run(
                """
                MATCH (e:Employee)
                WHERE e.status = 'active'
                MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
                    employee_id: e.id,
                    year: $year,
                    leave_type: 'annual'
                })
                SET lb.total_days = 21.0,
                    lb.used_days = 0.0,
                    lb.pending_days = 0.0,
                    lb.remaining_days = 21.0,
                    lb.updated_at = datetime()
                RETURN count(lb) as count
                """,
                year=current_year
            )
            record = await result.single()
            print(f"✓ Created/updated {record['count']} annual leave balances")

            # Initialize sick leave balances (30 days per 3-year cycle)
            result = await session.run(
                """
                MATCH (e:Employee)
                WHERE e.status = 'active'
                MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
                    employee_id: e.id,
                    year: $year,
                    leave_type: 'sick'
                })
                SET lb.total_days = 10.0,
                    lb.used_days = 0.0,
                    lb.pending_days = 0.0,
                    lb.remaining_days = 10.0,
                    lb.updated_at = datetime()
                RETURN count(lb) as count
                """,
                year=current_year
            )
            record = await result.single()
            print(f"✓ Created/updated {record['count']} sick leave balances")

            # Initialize family responsibility leave (3 days per year)
            result = await session.run(
                """
                MATCH (e:Employee)
                WHERE e.status = 'active'
                MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
                    employee_id: e.id,
                    year: $year,
                    leave_type: 'family'
                })
                SET lb.total_days = 3.0,
                    lb.used_days = 0.0,
                    lb.pending_days = 0.0,
                    lb.remaining_days = 3.0,
                    lb.updated_at = datetime()
                RETURN count(lb) as count
                """,
                year=current_year
            )
            record = await result.single()
            print(f"✓ Created/updated {record['count']} family responsibility leave balances")

            print("\n✓ Leave data seeding complete!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(seed_leave_data())
