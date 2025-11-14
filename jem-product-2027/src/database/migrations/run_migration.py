"""Python-based migration runner for Neo4j Cypher files.

Reads and executes .cypher files against Neo4j Aura using credentials from .env.
Handles multi-statement execution and provides detailed feedback.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables
load_dotenv()


async def run_migration(cypher_file_path: str):
    """Execute a Cypher migration file against Neo4j.

    Args:
        cypher_file_path: Path to the .cypher file to execute.
    """
    # Get Neo4j credentials
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("❌ Error: Neo4j credentials not found in .env file")
        print("   Required: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
        sys.exit(1)

    # Read Cypher file
    cypher_path = Path(cypher_file_path)
    if not cypher_path.exists():
        print(f"❌ Error: File not found: {cypher_file_path}")
        sys.exit(1)

    print(f"\n📄 Reading migration file: {cypher_path.name}")
    with open(cypher_path, "r") as f:
        content = f.read()

    # Split into individual statements
    # Remove comments and empty lines
    lines = content.split("\n")
    statements = []
    current_statement = []

    for line in lines:
        # Skip comment-only lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Add line to current statement
        if stripped:
            current_statement.append(line)

        # If line ends with semicolon, it's the end of a statement
        if stripped.endswith(";"):
            stmt = "\n".join(current_statement)
            if stmt.strip():
                statements.append(stmt)
            current_statement = []

    # Add any remaining statement
    if current_statement:
        stmt = "\n".join(current_statement)
        if stmt.strip():
            statements.append(stmt)

    if not statements:
        print("⚠️  No executable statements found in file")
        return

    print(f"📊 Found {len(statements)} statements to execute")
    print(f"\n🔌 Connecting to Neo4j at {uri}...")

    # Connect to Neo4j
    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    try:
        # Verify connection
        await driver.verify_connectivity()
        print("✅ Connected successfully!\n")

        async with driver.session() as session:
            success_count = 0
            error_count = 0

            for i, statement in enumerate(statements, 1):
                # Extract statement type for display
                stmt_preview = statement.strip()[:60].replace("\n", " ")
                if len(statement.strip()) > 60:
                    stmt_preview += "..."

                try:
                    print(f"[{i}/{len(statements)}] Executing: {stmt_preview}")
                    result = await session.run(statement)
                    summary = await result.consume()

                    # Show what was created/updated
                    counters = summary.counters
                    changes = []

                    if counters.constraints_added > 0:
                        changes.append(f"{counters.constraints_added} constraint(s) added")
                    if counters.indexes_added > 0:
                        changes.append(f"{counters.indexes_added} index(es) added")
                    if counters.nodes_created > 0:
                        changes.append(f"{counters.nodes_created} node(s) created")
                    if counters.relationships_created > 0:
                        changes.append(f"{counters.relationships_created} relationship(s) created")
                    if counters.properties_set > 0:
                        changes.append(f"{counters.properties_set} propert(ies) set")

                    if changes:
                        print(f"   ✓ {', '.join(changes)}")
                    else:
                        print(f"   ✓ Executed successfully")

                    success_count += 1

                except Exception as e:
                    print(f"   ❌ Error: {str(e)}")
                    error_count += 1

                print()

            # Summary
            print("=" * 60)
            print(f"\n📊 Migration Summary:")
            print(f"   ✅ Successful: {success_count}")
            if error_count > 0:
                print(f"   ❌ Failed: {error_count}")
            print(f"\n{'✅ Migration completed successfully!' if error_count == 0 else '⚠️  Migration completed with errors'}\n")

    except Exception as e:
        print(f"\n❌ Connection error: {str(e)}")
        sys.exit(1)

    finally:
        await driver.close()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <path_to_cypher_file>")
        print("\nExample:")
        print("  python run_migration.py src/database/migrations/001_leave_management_schema.cypher")
        sys.exit(1)

    cypher_file = sys.argv[1]
    asyncio.run(run_migration(cypher_file))


if __name__ == "__main__":
    main()
