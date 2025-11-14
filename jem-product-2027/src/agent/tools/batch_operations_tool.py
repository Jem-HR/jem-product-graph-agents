"""Batch operations for bulk employee and leave management.

Handles processing large volumes of employee records (up to 5000) from CSV files.
Implements batching, error handling, and progress tracking.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable

from dotenv import load_dotenv
from langchain_core.tools import tool
from neo4j import AsyncGraphDatabase

load_dotenv()


def get_neo4j_driver():
    """Get Neo4j driver connection."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        raise ValueError("Neo4j credentials not found")

    return AsyncGraphDatabase.driver(uri, auth=(username, password))


@tool
async def batch_create_employees(
    records: list[dict[str, Any]],
    employer_id: int,
    admin_id: int,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Create multiple employees in batches.

    Processes records in batches to avoid overwhelming the database.
    Tracks successes and failures separately.

    Args:
        records: List of employee records to create.
        employer_id: Employer ID (for scoping).
        admin_id: Admin performing the operation.
        batch_size: Number of records per batch (default: 100).

    Returns:
        Results with successes, failures, and progress.
    """
    driver = get_neo4j_driver()

    successes = []
    failures = []
    total = len(records)

    try:
        async with driver.session() as session:
            # Get starting ID
            result = await session.run("""
                MATCH (e:Employee)
                RETURN coalesce(max(e.id), 0) + 1 as next_id
            """)
            record = await result.single()
            next_id = record["next_id"]

            # Process in batches
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = records[batch_start:batch_end]

                for idx, emp_record in enumerate(batch):
                    emp_id = next_id + batch_start + idx

                    try:
                        # Check for duplicate mobile number
                        check_result = await session.run("""
                            MATCH (e:Employee {mobile_number: $mobile_number, employer_id: $employer_id})
                            RETURN e.id as id
                        """, mobile_number=emp_record["mobile_number"], employer_id=employer_id)

                        existing = await check_result.single()

                        if existing:
                            failures.append({
                                **emp_record,
                                "error": f"Duplicate mobile number (existing ID: {existing['id']})"
                            })
                            continue

                        # Create employee
                        from uuid import uuid4

                        employee_props = {
                            "id": emp_id,
                            "uuid": str(uuid4()),
                            "first_name": emp_record["first_name"],
                            "last_name": emp_record["last_name"],
                            "mobile_number": emp_record["mobile_number"],
                            "email": emp_record["email"],
                            "status": emp_record.get("status", "active"),
                            "employer_id": employer_id,
                            "employee_no": emp_record["employee_no"],
                            "smartwage_status": emp_record.get("smartwage_status", "inactive"),
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                        }

                        if "salary" in emp_record and emp_record["salary"]:
                            employee_props["salary"] = float(emp_record["salary"])

                        # Create node with employer relationship
                        create_result = await session.run("""
                            CREATE (e:Employee $props)
                            WITH e
                            MATCH (emp:Employer {id: $employer_id})
                            CREATE (e)-[:WORKS_FOR]->(emp)
                            RETURN e.id as id, e.first_name as first_name, e.last_name as last_name
                        """, props=employee_props, employer_id=employer_id)

                        created = await create_result.single()

                        if created:
                            successes.append({
                                **emp_record,
                                "new_id": emp_id,
                                "status": "created"
                            })
                        else:
                            failures.append({
                                **emp_record,
                                "error": "Failed to create employee node"
                            })

                    except Exception as e:
                        failures.append({
                            **emp_record,
                            "error": str(e)
                        })

        return {
            "success": True,
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_count": len(successes),
            "failure_count": len(failures),
            "success_rate": (len(successes) / total * 100) if total > 0 else 0,
            "message": f"Processed {total} records: {len(successes)} succeeded, {len(failures)} failed"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Batch processing error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def batch_update_managers(
    records: list[dict[str, Any]],
    employer_id: int,
    admin_id: int,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Update manager relationships in bulk (change leave approvers).

    Args:
        records: List of {employee_id, new_manager_id} records.
        employer_id: Employer ID (for scoping and validation).
        admin_id: Admin performing the operation.
        batch_size: Number of records per batch.

    Returns:
        Results with successes and failures.
    """
    driver = get_neo4j_driver()

    successes = []
    failures = []
    total = len(records)

    try:
        async with driver.session() as session:
            # Process in batches
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = records[batch_start:batch_end]

                for record in batch:
                    employee_id = int(record["employee_id"])
                    new_manager_id = int(record["new_manager_id"])

                    try:
                        # Verify employee exists in this employer
                        check_result = await session.run("""
                            MATCH (e:Employee {id: $employee_id, employer_id: $employer_id})
                            RETURN e.first_name as first_name, e.last_name as last_name
                        """, employee_id=employee_id, employer_id=employer_id)

                        employee = await check_result.single()

                        if not employee:
                            failures.append({
                                **record,
                                "error": f"Employee {employee_id} not found or wrong employer"
                            })
                            continue

                        # Verify new manager exists in same employer
                        manager_check = await session.run("""
                            MATCH (m:Employee {id: $manager_id, employer_id: $employer_id})
                            RETURN m.first_name as first_name, m.last_name as last_name
                        """, manager_id=new_manager_id, employer_id=employer_id)

                        manager = await manager_check.single()

                        if not manager:
                            failures.append({
                                **record,
                                "error": f"Manager {new_manager_id} not found or wrong employer"
                            })
                            continue

                        # Update relationship
                        # Remove old REPORTS_TO
                        await session.run("""
                            MATCH (e:Employee {id: $employee_id})-[r:REPORTS_TO]->()
                            DELETE r
                        """, employee_id=employee_id)

                        # Create new REPORTS_TO
                        update_result = await session.run("""
                            MATCH (e:Employee {id: $employee_id, employer_id: $employer_id})
                            MATCH (m:Employee {id: $manager_id, employer_id: $employer_id})
                            CREATE (e)-[:REPORTS_TO]->(m)
                            SET e.updated_at = $updated_at
                            RETURN e.first_name as emp_first, e.last_name as emp_last,
                                   m.first_name as mgr_first, m.last_name as mgr_last
                        """,
                            employee_id=employee_id,
                            manager_id=new_manager_id,
                            employer_id=employer_id,
                            updated_at=datetime.now().isoformat()
                        )

                        updated = await update_result.single()

                        if updated:
                            successes.append({
                                **record,
                                "employee_name": f"{updated['emp_first']} {updated['emp_last']}",
                                "new_manager_name": f"{updated['mgr_first']} {updated['mgr_last']}",
                                "status": "updated"
                            })
                        else:
                            failures.append({
                                **record,
                                "error": "Failed to create relationship"
                            })

                    except Exception as e:
                        failures.append({
                            **record,
                            "error": str(e)
                        })

        return {
            "success": True,
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_count": len(successes),
            "failure_count": len(failures),
            "success_rate": (len(successes) / total * 100) if total > 0 else 0,
            "message": f"Updated {len(successes)}/{total} manager relationships"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Batch update error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def batch_initialize_leave_balances(
    employee_ids: list[int],
    year: int,
    employer_id: int,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Initialize leave balances for multiple employees.

    Creates standard South African leave balances:
    - Annual: 21 days
    - Sick: 10 days
    - Family: 3 days

    Args:
        employee_ids: List of employee IDs.
        year: Year for leave balance.
        employer_id: Employer ID for validation.
        batch_size: Batch size for processing.

    Returns:
        Results with counts per leave type.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            created_counts = {"annual": 0, "sick": 0, "family": 0}

            # Process in batches
            for batch_start in range(0, len(employee_ids), batch_size):
                batch_end = min(batch_start + batch_size, len(employee_ids))
                batch_ids = employee_ids[batch_start:batch_end]

                # Annual leave
                result = await session.run("""
                    UNWIND $employee_ids as emp_id
                    MATCH (e:Employee {id: emp_id, employer_id: $employer_id})
                    MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
                        employee_id: emp_id,
                        year: $year,
                        leave_type: 'annual'
                    })
                    SET lb.total_days = 21.0,
                        lb.used_days = 0.0,
                        lb.pending_days = 0.0,
                        lb.remaining_days = 21.0,
                        lb.updated_at = datetime()
                    RETURN count(lb) as count
                """, employee_ids=batch_ids, employer_id=employer_id, year=year)

                record = await result.single()
                created_counts["annual"] += record["count"]

                # Sick leave
                result = await session.run("""
                    UNWIND $employee_ids as emp_id
                    MATCH (e:Employee {id: emp_id, employer_id: $employer_id})
                    MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
                        employee_id: emp_id,
                        year: $year,
                        leave_type: 'sick'
                    })
                    SET lb.total_days = 10.0,
                        lb.used_days = 0.0,
                        lb.pending_days = 0.0,
                        lb.remaining_days = 10.0,
                        lb.updated_at = datetime()
                    RETURN count(lb) as count
                """, employee_ids=batch_ids, employer_id=employer_id, year=year)

                record = await result.single()
                created_counts["sick"] += record["count"]

                # Family leave
                result = await session.run("""
                    UNWIND $employee_ids as emp_id
                    MATCH (e:Employee {id: emp_id, employer_id: $employer_id})
                    MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
                        employee_id: emp_id,
                        year: $year,
                        leave_type: 'family'
                    })
                    SET lb.total_days = 3.0,
                        lb.used_days = 0.0,
                        lb.pending_days = 0.0,
                        lb.remaining_days = 3.0,
                        lb.updated_at = datetime()
                    RETURN count(lb) as count
                """, employee_ids=batch_ids, employer_id=employer_id, year=year)

                record = await result.single()
                created_counts["family"] += record["count"]

        return {
            "success": True,
            "total_employees": len(employee_ids),
            "created_counts": created_counts,
            "message": f"Initialized leave balances for {len(employee_ids)} employees"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Batch initialization error: {str(e)}"
        }
    finally:
        await driver.close()
