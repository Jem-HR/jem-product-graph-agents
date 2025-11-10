"""Check relationships for specific employee."""

import asyncio
from agent.tools.neo4j_tool import get_neo4j_graph


async def check_employee_relationships():
    """Check what relationships exist for employee 27782440774."""

    print("=" * 70)
    print("CHECKING: Employee Relationships for 27782440774")
    print("=" * 70)

    graph = get_neo4j_graph()

    # Find employee and their relationships
    query = """
    MATCH (e:Employee {mobile_number: '27782440774'})
    OPTIONAL MATCH (e)-[r]->(connected)
    RETURN e.id as employee_id,
           e.first_name as first_name,
           e.last_name as last_name,
           type(r) as relationship_type,
           labels(connected) as connected_labels,
           connected.id as connected_id,
           connected.first_name as connected_first_name,
           connected.last_name as connected_last_name,
           connected.name as connected_name,
           connected.company_name as company_name
    """

    print("\n[QUERY] Finding employee and outgoing relationships...")
    print("-" * 70)
    results = graph.query(query)

    if not results:
        print("❌ No employee found with that mobile number")
        return

    print(f"\n✅ Found {len(results)} relationship(s):")
    for row in results:
        print(f"\nEmployee: {row['first_name']} {row['last_name']} (ID: {row['employee_id']})")
        if row['relationship_type']:
            print(f"  ➜ {row['relationship_type']} ➜ ", end="")
            if row['connected_first_name']:
                print(f"{row['connected_first_name']} {row['connected_last_name']} (ID: {row['connected_id']})")
            elif row['connected_name']:
                print(f"{row['connected_name']} (ID: {row['connected_id']})")
            elif row['company_name']:
                print(f"{row['company_name']} (ID: {row['connected_id']})")
            else:
                print(f"{row['connected_labels']} (ID: {row['connected_id']})")
        else:
            print("  (No outgoing relationships)")

    # Check for REPORTS_TO specifically
    print("\n[QUERY] Checking for REPORTS_TO relationship...")
    print("-" * 70)
    manager_query = """
    MATCH (e:Employee {mobile_number: '27782440774'})-[:REPORTS_TO]->(manager:Employee)
    RETURN manager.id as manager_id,
           manager.first_name as first_name,
           manager.last_name as last_name,
           manager.mobile_number as mobile_number
    """
    manager_result = graph.query(manager_query)

    if manager_result:
        mgr = manager_result[0]
        print(f"✅ Manager: {mgr['first_name']} {mgr['last_name']} (ID: {mgr['manager_id']})")
        print(f"   Mobile: {mgr['mobile_number']}")
    else:
        print("❌ No REPORTS_TO relationship found for this employee")

    # Check for IN_DIVISION
    print("\n[QUERY] Checking for IN_DIVISION relationship...")
    print("-" * 70)
    division_query = """
    MATCH (e:Employee {mobile_number: '27782440774'})-[:IN_DIVISION]->(div:Division)
    RETURN div.id as division_id, div.name as division_name
    """
    division_result = graph.query(division_query)

    if division_result:
        div = division_result[0]
        print(f"✅ Division: {div['division_name']} (ID: {div['division_id']})")
    else:
        print("❌ No IN_DIVISION relationship found for this employee")

    # Check schema that LLM sees
    print("\n[SCHEMA] Checking graph schema...")
    print("-" * 70)
    print(f"Schema:\n{graph.schema}")

    print("\n" + "=" * 70)
    print("RELATIONSHIP CHECK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(check_employee_relationships())
