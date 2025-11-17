"""Neo4j backup and restore utilities for testing.

Provides functions to:
- Export entire graph database to Cypher statements
- Restore database from backup
- Create snapshots for testing
- Rollback after tests
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

# Backup directory
BACKUP_DIR = Path("data/neo4j_backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


async def backup_neo4j_database(
    backup_name: str | None = None,
    employer_id: int | None = None
) -> str:
    """Create a backup of the Neo4j database.

    Exports all nodes and relationships to Cypher CREATE statements.
    Can optionally scope to a specific employer for multi-tenant backups.

    Args:
        backup_name: Name for the backup file (default: timestamp).
        employer_id: If provided, only backup data for this employer.

    Returns:
        Path to the backup file.
    """
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        raise ValueError("Neo4j credentials not found in .env")

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    # Generate backup filename
    if not backup_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"

    if employer_id:
        backup_name += f"_employer_{employer_id}"

    backup_file = BACKUP_DIR / f"{backup_name}.cypher"

    try:
        async with driver.session() as session:
            # Build scoping clause
            employer_filter = f"WHERE e.employer_id = {employer_id}" if employer_id else ""

            print(f"🔍 Backing up Neo4j database...")
            if employer_id:
                print(f"   Scope: Employer ID {employer_id} only")

            with open(backup_file, "w") as f:
                f.write("// Neo4j Database Backup\n")
                f.write(f"// Created: {datetime.now().isoformat()}\n")
                if employer_id:
                    f.write(f"// Scope: Employer ID {employer_id}\n")
                f.write("//\n\n")

                # Backup Employees
                print("   📦 Backing up Employee nodes...")
                query = f"""
                MATCH (e:Employee)
                {employer_filter}
                RETURN e
                """
                result = await session.run(query)
                employees = await result.data()

                f.write(f"// Employee Nodes ({len(employees)} records)\n")
                for record in employees:
                    emp = record['e']
                    props = ", ".join([f"{k}: {repr(v)}" for k, v in emp.items()])
                    f.write(f"CREATE (e{emp['id']}:Employee {{{props}}});\n")

                f.write("\n")

                # Backup REPORTS_TO relationships
                print("   📦 Backing up REPORTS_TO relationships...")
                query = f"""
                MATCH (e:Employee)-[r:REPORTS_TO]->(m:Employee)
                {employer_filter.replace('e.', 'e.')}
                RETURN e.id as emp_id, m.id as mgr_id
                """
                result = await session.run(query)
                relations = await result.data()

                f.write(f"// REPORTS_TO Relationships ({len(relations)} records)\n")
                for rel in relations:
                    f.write(f"MATCH (e:Employee {{id: {rel['emp_id']}}}), (m:Employee {{id: {rel['mgr_id']}}}) CREATE (e)-[:REPORTS_TO]->(m);\n")

                f.write("\n")

                # Backup LeaveBalance nodes
                print("   📦 Backing up LeaveBalance nodes...")
                query = f"""
                MATCH (e:Employee)-[:HAS_BALANCE]->(lb:LeaveBalance)
                {employer_filter}
                RETURN lb, e.id as emp_id
                """
                result = await session.run(query)
                balances = await result.data()

                f.write(f"// LeaveBalance Nodes ({len(balances)} records)\n")
                for record in balances:
                    lb = record['lb']
                    emp_id = record['emp_id']
                    props = ", ".join([f"{k}: {repr(v)}" for k, v in lb.items()])
                    f.write(f"MATCH (e:Employee {{id: {emp_id}}}) CREATE (e)-[:HAS_BALANCE]->(:LeaveBalance {{{props}}});\n")

                f.write("\n")

                # Backup LeaveRequest nodes
                print("   📦 Backing up LeaveRequest nodes...")
                query = f"""
                MATCH (e:Employee)-[:SUBMITTED_LEAVE]->(lr:LeaveRequest)
                {employer_filter}
                RETURN lr, e.id as emp_id
                """
                result = await session.run(query)
                leave_requests = await result.data()

                f.write(f"// LeaveRequest Nodes ({len(leave_requests)} records)\n")
                for record in leave_requests:
                    lr = record['lr']
                    emp_id = record['emp_id']
                    props = ", ".join([f"{k}: {repr(v)}" for k, v in lr.items()])
                    f.write(f"MATCH (e:Employee {{id: {emp_id}}}) CREATE (e)-[:SUBMITTED_LEAVE]->(:LeaveRequest {{{props}}});\n")

                f.write("\n")
                f.write("// Backup complete\n")

            print(f"\n✅ Backup complete: {backup_file}")
            print(f"   Total size: {backup_file.stat().st_size / 1024:.1f} KB")

            return str(backup_file)

    finally:
        await driver.close()


async def restore_neo4j_database(
    backup_file: str,
    clear_existing: bool = True
) -> bool:
    """Restore Neo4j database from a backup file.

    Args:
        backup_file: Path to the backup Cypher file.
        clear_existing: If True, delete existing data before restore (default: True).

    Returns:
        True if successful, False otherwise.
    """
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        raise ValueError("Neo4j credentials not found in .env")

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    try:
        async with driver.session() as session:
            if clear_existing:
                print("⚠️  Clearing existing data...")
                # WARNING: This deletes ALL data!
                await session.run("MATCH (n) DETACH DELETE n")
                print("   ✅ Database cleared")

            print(f"📥 Restoring from: {backup_file}")

            # Read and execute backup file
            with open(backup_file, "r") as f:
                statements = []
                current_statement = []

                for line in f:
                    # Skip comments and empty lines
                    stripped = line.strip()
                    if stripped.startswith("//") or not stripped:
                        continue

                    current_statement.append(line)

                    # Statement ends with semicolon
                    if stripped.endswith(";"):
                        stmt = "".join(current_statement)
                        statements.append(stmt)
                        current_statement = []

            print(f"   Found {len(statements)} statements to execute")

            # Execute statements
            for i, statement in enumerate(statements, 1):
                if i % 100 == 0:
                    print(f"   Progress: {i}/{len(statements)} statements...")

                try:
                    await session.run(statement)
                except Exception as e:
                    print(f"   ⚠️  Error on statement {i}: {e}")
                    # Continue with other statements

            print(f"\n✅ Restore complete: {len(statements)} statements executed")

            return True

    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False

    finally:
        await driver.close()


async def create_test_snapshot(employer_id: int = 189) -> str:
    """Create a test snapshot before running tests.

    Args:
        employer_id: Employer ID to backup (default: 189).

    Returns:
        Path to snapshot file.
    """
    snapshot_name = f"test_snapshot_employer_{employer_id}"
    backup_path = await backup_neo4j_database(snapshot_name, employer_id)

    print(f"\n💾 Test snapshot created: {backup_path}")
    print(f"   Use this to restore after testing")

    return backup_path


async def rollback_to_snapshot(snapshot_file: str) -> bool:
    """Rollback database to a previous snapshot.

    Args:
        snapshot_file: Path to snapshot file.

    Returns:
        True if successful.
    """
    print(f"\n🔄 Rolling back to snapshot: {snapshot_file}")

    result = await restore_neo4j_database(snapshot_file, clear_existing=True)

    if result:
        print("✅ Rollback successful!")
    else:
        print("❌ Rollback failed!")

    return result


async def list_backups() -> list[str]:
    """List all available backup files.

    Returns:
        List of backup file paths.
    """
    backups = sorted(BACKUP_DIR.glob("*.cypher"), key=lambda p: p.stat().st_mtime, reverse=True)

    print("\n📦 Available Backups:")
    print("="*60)

    for i, backup in enumerate(backups, 1):
        size = backup.stat().st_size / 1024
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"{i}. {backup.name}")
        print(f"   Size: {size:.1f} KB")
        print(f"   Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    return [str(b) for b in backups]


# CLI interface
async def main():
    """Main CLI interface for backup/restore operations."""
    import sys

    if len(sys.argv) < 2:
        print("Neo4j Backup & Restore Utility")
        print("="*60)
        print("\nUsage:")
        print("  python src/database/backup_restore.py backup [employer_id]")
        print("  python src/database/backup_restore.py restore <backup_file>")
        print("  python src/database/backup_restore.py snapshot [employer_id]")
        print("  python src/database/backup_restore.py rollback <snapshot_file>")
        print("  python src/database/backup_restore.py list")
        print("\nExamples:")
        print("  python src/database/backup_restore.py backup 189")
        print("  python src/database/backup_restore.py snapshot 189")
        print("  python src/database/backup_restore.py rollback data/neo4j_backups/test_snapshot_employer_189.cypher")
        print("  python src/database/backup_restore.py list")
        sys.exit(1)

    command = sys.argv[1]

    if command == "backup":
        employer_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
        await backup_neo4j_database(employer_id=employer_id)

    elif command == "restore":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide backup file path")
            sys.exit(1)
        backup_file = sys.argv[2]
        await restore_neo4j_database(backup_file)

    elif command == "snapshot":
        employer_id = int(sys.argv[2]) if len(sys.argv) > 2 else 189
        await create_test_snapshot(employer_id)

    elif command == "rollback":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide snapshot file path")
            sys.exit(1)
        snapshot_file = sys.argv[2]
        await rollback_to_snapshot(snapshot_file)

    elif command == "list":
        await list_backups()

    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
