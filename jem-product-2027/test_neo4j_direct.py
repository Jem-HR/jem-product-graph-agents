"""Direct test of Neo4j connection and schema."""

import asyncio
import os
from dotenv import load_dotenv
from agent.tools.neo4j_tool import get_neo4j_graph, get_employee_by_mobile_neo4j

load_dotenv()


async def test_neo4j_connection():
    """Test Neo4j connection and explore schema."""

    print("=" * 70)
    print("TESTING: Direct Neo4j Connection")
    print("=" * 70)

    # Test 1: Connection
    print("\n[TEST 1] Testing Neo4j connection...")
    print("-" * 70)
    try:
        graph = get_neo4j_graph()
        print("✅ Connected to Neo4j successfully!")
        print(f"   URI: {os.getenv('NEO4J_URI')}")
        print(f"   Username: {os.getenv('NEO4J_USERNAME')}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # Test 2: Check schema
    print("\n[TEST 2] Checking Neo4j schema...")
    print("-" * 70)
    try:
        schema_query = """
        CALL db.schema.visualization()
        """
        schema = graph.query(schema_query)
        print(f"Schema result: {schema}")
    except Exception as e:
        print(f"Schema query failed (this is okay): {e}")

    # Test 3: List node labels
    print("\n[TEST 3] Listing node labels...")
    print("-" * 70)
    try:
        labels_query = """
        CALL db.labels() YIELD label
        RETURN label
        LIMIT 20
        """
        labels = graph.query(labels_query)
        print(f"✅ Found {len(labels)} node labels:")
        for label in labels:
            print(f"   - {label}")
    except Exception as e:
        print(f"❌ Failed to list labels: {e}")

    # Test 4: Count Employee nodes
    print("\n[TEST 4] Counting Employee nodes...")
    print("-" * 70)
    try:
        count_query = """
        MATCH (e:Employee)
        RETURN count(e) as total
        """
        result = graph.query(count_query)
        print(f"✅ Total Employee nodes: {result[0]['total'] if result else 0}")
    except Exception as e:
        print(f"❌ Failed to count employees: {e}")

    # Test 5: Check if specific employee exists
    print("\n[TEST 5] Looking up employee 27782440774...")
    print("-" * 70)
    try:
        employee = await get_employee_by_mobile_neo4j("27782440774")
        if employee:
            print("✅ Employee found:")
            for key, value in employee.items():
                print(f"   {key}: {value}")
        else:
            print("❌ Employee not found")
    except Exception as e:
        print(f"❌ Lookup failed: {e}")

    # Test 6: Check properties of one employee node
    print("\n[TEST 6] Checking Employee node properties...")
    print("-" * 70)
    try:
        props_query = """
        MATCH (e:Employee)
        RETURN e
        LIMIT 1
        """
        result = graph.query(props_query)
        if result:
            print("✅ Sample employee node:")
            print(f"   {result[0]}")
        else:
            print("❌ No employee nodes found")
    except Exception as e:
        print(f"❌ Failed to get properties: {e}")

    # Test 7: Check relationship types
    print("\n[TEST 7] Checking relationship types...")
    print("-" * 70)
    try:
        rel_query = """
        CALL db.relationshipTypes() YIELD relationshipType
        RETURN relationshipType
        LIMIT 20
        """
        relationships = graph.query(rel_query)
        print(f"✅ Found {len(relationships)} relationship types:")
        for rel in relationships:
            print(f"   - {rel}")
    except Exception as e:
        print(f"❌ Failed to list relationships: {e}")

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_neo4j_connection())
