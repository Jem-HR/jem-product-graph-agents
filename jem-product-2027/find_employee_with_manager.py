"""Find an employee who has a manager (REPORTS_TO relationship)."""

from agent.tools.neo4j_tool import get_neo4j_graph


def find_employee_with_manager():
    """Find an employee with manager and division."""

    print("=" * 70)
    print("FINDING: Employee with Manager/Division")
    print("=" * 70)

    graph = get_neo4j_graph()

    # Find an employee with REPORTS_TO relationship
    query = """
    MATCH (e:Employee)-[:REPORTS_TO]->(manager:Employee)
    WHERE e.mobile_number IS NOT NULL
    RETURN e.mobile_number as mobile,
           e.first_name as first_name,
           e.last_name as last_name,
           e.id as employee_id,
           manager.first_name as manager_first_name,
           manager.last_name as manager_last_name,
           manager.id as manager_id
    LIMIT 5
    """

    print("\n[QUERY] Finding employees with REPORTS_TO relationships...")
    print("-" * 70)
    results = graph.query(query)

    if results:
        print(f"\n✅ Found {len(results)} employee(s) with managers:")
        for row in results:
            print(f"\nEmployee: {row['first_name']} {row['last_name']} (ID: {row['employee_id']})")
            print(f"  Mobile: {row['mobile']}")
            print(f"  Manager: {row['manager_first_name']} {row['manager_last_name']} (ID: {row['manager_id']})")
    else:
        print("\n❌ No employees with REPORTS_TO relationships found")

    # Find an employee with IN_DIVISION relationship
    print("\n[QUERY] Finding employees with IN_DIVISION relationships...")
    print("-" * 70)
    division_query = """
    MATCH (e:Employee)-[:IN_DIVISION]->(div:Division)
    WHERE e.mobile_number IS NOT NULL
    RETURN e.mobile_number as mobile,
           e.first_name as first_name,
           e.last_name as last_name,
           e.id as employee_id,
           div.name as division_name,
           div.id as division_id
    LIMIT 5
    """
    division_results = graph.query(division_query)

    if division_results:
        print(f"\n✅ Found {len(division_results)} employee(s) with divisions:")
        for row in division_results:
            print(f"\nEmployee: {row['first_name']} {row['last_name']} (ID: {row['employee_id']})")
            print(f"  Mobile: {row['mobile']}")
            print(f"  Division: {row['division_name']} (ID: {row['division_id']})")
    else:
        print("\n❌ No employees with IN_DIVISION relationships found")

    print("\n" + "=" * 70)
    print("SEARCH COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    find_employee_with_manager()
