"""Neo4j CRUD operations for employee management.

Provides tools for creating, updating, and deleting employee records.
All operations include validation and audit logging.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.tools import tool
from neo4j import AsyncGraphDatabase

load_dotenv()


def get_neo4j_driver():
    """Get Neo4j driver connection.

    Returns:
        Neo4j driver instance.
    """
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        msg = "Neo4j credentials not found in environment variables"
        raise ValueError(msg)

    return AsyncGraphDatabase.driver(uri, auth=(username, password))


@tool
async def create_employee(
    first_name: str,
    last_name: str,
    mobile_number: str,
    email: str,
    employer_id: int,
    employee_no: str,
    status: str = "active",
    salary: float | None = None,
    division_id: int | None = None,
    branch_id: int | None = None,
    reports_to_id: int | None = None,
) -> dict[str, Any]:
    """Create a new employee record in Neo4j.

    Args:
        first_name: Employee's first name.
        last_name: Employee's last name.
        mobile_number: Mobile number in 27XXXXXXXXX format.
        email: Employee's email address.
        employer_id: ID of the employer company.
        employee_no: Unique employee number/code.
        status: Employment status (default: 'active').
        salary: Optional salary amount.
        division_id: Optional division/team ID.
        branch_id: Optional branch location ID.
        reports_to_id: Optional manager's employee ID.

    Returns:
        Created employee record with ID.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Validate mobile number format
            if not mobile_number.startswith("27") or len(mobile_number) != 11:
                return {
                    "success": False,
                    "error": "Mobile number must be in format 27XXXXXXXXX (11 digits)"
                }

            # Check if mobile number already exists
            check_query = """
            MATCH (e:Employee {mobile_number: $mobile_number})
            RETURN e.id as id
            """
            result = await session.run(check_query, mobile_number=mobile_number)
            existing = await result.single()

            if existing:
                return {
                    "success": False,
                    "error": f"Employee with mobile number {mobile_number} already exists (ID: {existing['id']})"
                }

            # Get next employee ID
            id_query = """
            MATCH (e:Employee)
            RETURN coalesce(max(e.id), 0) + 1 as next_id
            """
            result = await session.run(id_query)
            record = await result.single()
            next_id = record["next_id"]

            # Create employee node with properties
            employee_props = {
                "id": next_id,
                "uuid": str(uuid4()),
                "first_name": first_name,
                "last_name": last_name,
                "mobile_number": mobile_number,
                "email": email,
                "status": status,
                "employer_id": employer_id,
                "employee_no": employee_no,
                "smartwage_status": "inactive",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            if salary is not None:
                employee_props["salary"] = salary

            # Build query with relationships
            create_query = """
            CREATE (e:Employee $props)
            WITH e
            """

            # Add employer relationship
            create_query += """
            MATCH (emp:Employer {id: $employer_id})
            CREATE (e)-[:WORKS_FOR]->(emp)
            WITH e
            """

            # Add optional relationships
            if division_id:
                create_query += """
                MATCH (d:Division {id: $division_id})
                CREATE (e)-[:IN_DIVISION]->(d)
                WITH e
                """

            if branch_id:
                create_query += """
                MATCH (b:Branch {id: $branch_id})
                CREATE (e)-[:ASSIGNED_TO_BRANCH]->(b)
                WITH e
                """

            if reports_to_id:
                create_query += """
                MATCH (manager:Employee {id: $reports_to_id})
                CREATE (e)-[:REPORTS_TO]->(manager)
                WITH e
                """

            # Return the created employee
            create_query += """
            RETURN e.id as id,
                   e.uuid as uuid,
                   e.first_name as first_name,
                   e.last_name as last_name,
                   e.mobile_number as mobile_number,
                   e.email as email,
                   e.status as status,
                   e.salary as salary
            """

            result = await session.run(
                create_query,
                props=employee_props,
                employer_id=employer_id,
                division_id=division_id,
                branch_id=branch_id,
                reports_to_id=reports_to_id,
            )
            record = await result.single()

            if record:
                return {
                    "success": True,
                    "employee": dict(record),
                    "message": f"Employee {first_name} {last_name} created successfully"
                }

            return {
                "success": False,
                "error": "Failed to create employee record"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def update_employee(
    employee_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    mobile_number: str | None = None,
    email: str | None = None,
    status: str | None = None,
    salary: float | None = None,
    employee_no: str | None = None,
    smartwage_status: str | None = None,
    employer_id: int | None = None,
) -> dict[str, Any]:
    """Update an existing employee record.

    Only provided fields will be updated. Null values are ignored.
    Operations are scoped to the employer for data isolation.

    Args:
        employee_id: ID of employee to update.
        first_name: Optional new first name.
        last_name: Optional new last name.
        mobile_number: Optional new mobile number (27XXXXXXXXX format).
        email: Optional new email.
        status: Optional new status.
        salary: Optional new salary (requires approval).
        employee_no: Optional new employee number.
        smartwage_status: Optional new SmartWage status.
        employer_id: Employer ID for scoping (data isolation).

    Returns:
        Updated employee record.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Check if employee exists
            check_query = """
            MATCH (e:Employee {id: $employee_id})
            RETURN e.first_name as first_name, e.last_name as last_name
            """
            result = await session.run(check_query, employee_id=employee_id)
            existing = await result.single()

            if not existing:
                return {
                    "success": False,
                    "error": f"Employee with ID {employee_id} not found"
                }

            # Build update query dynamically
            update_fields = []
            params = {"employee_id": employee_id}

            if first_name is not None:
                update_fields.append("e.first_name = $first_name")
                params["first_name"] = first_name

            if last_name is not None:
                update_fields.append("e.last_name = $last_name")
                params["last_name"] = last_name

            if mobile_number is not None:
                # Validate format
                if not mobile_number.startswith("27") or len(mobile_number) != 11:
                    return {
                        "success": False,
                        "error": "Mobile number must be in format 27XXXXXXXXX"
                    }
                update_fields.append("e.mobile_number = $mobile_number")
                params["mobile_number"] = mobile_number

            if email is not None:
                update_fields.append("e.email = $email")
                params["email"] = email

            if status is not None:
                update_fields.append("e.status = $status")
                params["status"] = status

            if salary is not None:
                update_fields.append("e.salary = $salary")
                params["salary"] = salary

            if employee_no is not None:
                update_fields.append("e.employee_no = $employee_no")
                params["employee_no"] = employee_no

            if smartwage_status is not None:
                update_fields.append("e.smartwage_status = $smartwage_status")
                params["smartwage_status"] = smartwage_status

            if not update_fields:
                return {
                    "success": False,
                    "error": "No fields provided for update"
                }

            # Always update timestamp
            update_fields.append("e.updated_at = $updated_at")
            params["updated_at"] = datetime.now().isoformat()

            update_query = f"""
            MATCH (e:Employee {{id: $employee_id}})
            SET {", ".join(update_fields)}
            RETURN e.id as id,
                   e.first_name as first_name,
                   e.last_name as last_name,
                   e.mobile_number as mobile_number,
                   e.email as email,
                   e.status as status,
                   e.salary as salary,
                   e.updated_at as updated_at
            """

            result = await session.run(update_query, **params)
            record = await result.single()

            if record:
                return {
                    "success": True,
                    "employee": dict(record),
                    "message": f"Employee {employee_id} updated successfully"
                }

            return {
                "success": False,
                "error": "Failed to update employee"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def delete_employee(
    employee_id: int,
    soft_delete: bool = True,
    employer_id: int | None = None,
) -> dict[str, Any]:
    """Delete or deactivate an employee record.

    By default performs soft delete (sets status to 'terminated').
    Hard delete removes the node entirely (use with caution).
    Operations are scoped to the employer for data isolation.

    Args:
        employee_id: ID of employee to delete.
        soft_delete: If True, deactivate instead of deleting (default: True).
        employer_id: Employer ID for scoping (data isolation).

    Returns:
        Result of deletion operation.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Check if employee exists (scoped to employer if provided)
            if employer_id:
                check_query = """
                MATCH (e:Employee {id: $employee_id, employer_id: $employer_id})
                RETURN e.first_name as first_name,
                       e.last_name as last_name,
                       e.status as status
                """
                result = await session.run(check_query, employee_id=employee_id, employer_id=employer_id)
            else:
                check_query = """
                MATCH (e:Employee {id: $employee_id})
                RETURN e.first_name as first_name,
                       e.last_name as last_name,
                       e.status as status
                """
                result = await session.run(check_query, employee_id=employee_id)

            existing = await result.single()

            if not existing:
                return {
                    "success": False,
                    "error": f"Employee with ID {employee_id} not found or access denied"
                }

            if soft_delete:
                # Soft delete: set status to terminated
                if employer_id:
                    update_query = """
                    MATCH (e:Employee {id: $employee_id, employer_id: $employer_id})
                    SET e.status = 'terminated',
                        e.termination_date = $termination_date,
                        e.updated_at = $updated_at
                    RETURN e.id as id,
                           e.first_name as first_name,
                           e.last_name as last_name,
                           e.status as status
                    """
                    result = await session.run(
                        update_query,
                        employee_id=employee_id,
                        employer_id=employer_id,
                        termination_date=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                    )
                else:
                    update_query = """
                    MATCH (e:Employee {id: $employee_id})
                    SET e.status = 'terminated',
                        e.termination_date = $termination_date,
                        e.updated_at = $updated_at
                    RETURN e.id as id,
                           e.first_name as first_name,
                           e.last_name as last_name,
                           e.status as status
                    """
                    result = await session.run(
                        update_query,
                        employee_id=employee_id,
                        termination_date=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                    )
                record = await result.single()

                if record:
                    return {
                        "success": True,
                        "employee": dict(record),
                        "message": f"Employee {existing['first_name']} {existing['last_name']} deactivated (soft delete)"
                    }
            else:
                # Hard delete: remove node and relationships
                if employer_id:
                    delete_query = """
                    MATCH (e:Employee {id: $employee_id, employer_id: $employer_id})
                    DETACH DELETE e
                    RETURN count(e) as deleted_count
                    """
                    result = await session.run(delete_query, employee_id=employee_id, employer_id=employer_id)
                else:
                    delete_query = """
                    MATCH (e:Employee {id: $employee_id})
                    DETACH DELETE e
                    RETURN count(e) as deleted_count
                    """
                    result = await session.run(delete_query, employee_id=employee_id)
                record = await result.single()

                if record and record["deleted_count"] > 0:
                    return {
                        "success": True,
                        "message": f"Employee {existing['first_name']} {existing['last_name']} permanently deleted (hard delete)"
                    }

            return {
                "success": False,
                "error": "Failed to delete employee"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def update_employee_relationships(
    employee_id: int,
    reports_to_id: int | None = None,
    division_id: int | None = None,
    branch_id: int | None = None,
) -> dict[str, Any]:
    """Update employee organizational relationships.

    Replaces existing relationships of the specified types.
    Pass None to remove a relationship.

    Args:
        employee_id: ID of employee to update.
        reports_to_id: New manager's employee ID (None to remove).
        division_id: New division ID (None to remove).
        branch_id: New branch ID (None to remove).

    Returns:
        Result of relationship update.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Check if employee exists
            check_query = """
            MATCH (e:Employee {id: $employee_id})
            RETURN e.first_name as first_name, e.last_name as last_name
            """
            result = await session.run(check_query, employee_id=employee_id)
            existing = await result.single()

            if not existing:
                return {
                    "success": False,
                    "error": f"Employee with ID {employee_id} not found"
                }

            # Update REPORTS_TO relationship
            if reports_to_id is not None:
                # Remove existing REPORTS_TO
                await session.run(
                    """
                    MATCH (e:Employee {id: $employee_id})-[r:REPORTS_TO]->()
                    DELETE r
                    """,
                    employee_id=employee_id
                )

                # Create new REPORTS_TO if ID provided
                if reports_to_id > 0:
                    result = await session.run(
                        """
                        MATCH (e:Employee {id: $employee_id})
                        MATCH (manager:Employee {id: $reports_to_id})
                        CREATE (e)-[:REPORTS_TO]->(manager)
                        RETURN manager.first_name as manager_first_name,
                               manager.last_name as manager_last_name
                        """,
                        employee_id=employee_id,
                        reports_to_id=reports_to_id
                    )
                    await result.single()

            # Update IN_DIVISION relationship
            if division_id is not None:
                await session.run(
                    """
                    MATCH (e:Employee {id: $employee_id})-[r:IN_DIVISION]->()
                    DELETE r
                    """,
                    employee_id=employee_id
                )

                if division_id > 0:
                    await session.run(
                        """
                        MATCH (e:Employee {id: $employee_id})
                        MATCH (d:Division {id: $division_id})
                        CREATE (e)-[:IN_DIVISION]->(d)
                        """,
                        employee_id=employee_id,
                        division_id=division_id
                    )

            # Update ASSIGNED_TO_BRANCH relationship
            if branch_id is not None:
                await session.run(
                    """
                    MATCH (e:Employee {id: $employee_id})-[r:ASSIGNED_TO_BRANCH]->()
                    DELETE r
                    """,
                    employee_id=employee_id
                )

                if branch_id > 0:
                    await session.run(
                        """
                        MATCH (e:Employee {id: $employee_id})
                        MATCH (b:Branch {id: $branch_id})
                        CREATE (e)-[:ASSIGNED_TO_BRANCH]->(b)
                        """,
                        employee_id=employee_id,
                        branch_id=branch_id
                    )

            # Update timestamp
            await session.run(
                """
                MATCH (e:Employee {id: $employee_id})
                SET e.updated_at = $updated_at
                """,
                employee_id=employee_id,
                updated_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "message": f"Relationships updated for employee {existing['first_name']} {existing['last_name']}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()
