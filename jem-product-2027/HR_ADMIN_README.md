# HR Admin Deep Agent

A sophisticated LangChain-based HR management agent with specialized subagents for employee CRUD operations, leave management, and organizational queries.

## Overview

The HR Admin Agent is a **supervisor pattern multi-agent system** that coordinates three specialized subagents:

1. **Employee CRUD Agent** - Handles creating, updating, and deleting employee records
2. **Leave Management Agent** - Manages leave requests, approvals, and balance tracking
3. **Query Agent** - Answers questions about employees and organizational structure

All agents include:
- Role-based access control (RBAC)
- Human-in-the-loop approval for sensitive operations
- Comprehensive audit logging
- Integration with Neo4j graph database

## Architecture

```
HR Supervisor Agent
├── Authenticate Admin (verify credentials and load role)
├── Classify Request (determine operation type using LLM)
├── Route to Specialist (delegate to appropriate subagent)
├── Confirm with Human (interrupt for approval on sensitive ops)
└── Execute Action (perform the operation)
```

## Features

### Role-Based Access Control

Four role levels with different permissions:

- **HR Admin** - Full CRUD access to all operations
- **HR Manager** - Read access, employee updates (no salary), leave approvals
- **HR Viewer** - Read-only access to employee and leave data
- **Employee** - Self-service leave requests and viewing own data

### Human-in-the-Loop Approvals

The following operations require explicit human approval:

- ✅ Create new employee
- ✅ Delete employee (soft or hard delete)
- ✅ Update employee salary
- ✅ Create leave request
- ✅ Approve/reject leave requests

### Audit Logging

All CRUD operations are automatically logged to Neo4j with:
- Admin ID and name
- Operation type
- Target entity and ID
- Changes made
- Timestamp
- Success/failure status

## Installation

1. **Install dependencies:**

```bash
cd jem-product-2027
pip install -e .
```

2. **Set up environment variables:**

```bash
cp .env.example .env
# Edit .env with your Neo4j credentials
```

3. **Apply database schema:**

First, apply the Cypher schema migration:

```bash
# Open Neo4j Browser and run:
# jem-product-2027/src/database/migrations/001_leave_management_schema.cypher
```

Then seed leave data:

```bash
python src/database/migrations/002_seed_leave_data.py
```

## Usage

### Running the HR Admin Agent

```python
from agent.hr_admin_graph import graph
from langchain_core.messages import HumanMessage

# Start a conversation
config = {"configurable": {"thread_id": "hr_session_1"}}

# Admin is authenticated automatically (uses employee ID 1 by default)
# In production, integrate with your authentication system

response = await graph.ainvoke(
    {"messages": [HumanMessage(content="Create a new employee named John Doe")]},
    config
)

print(response["messages"][-1].content)
```

### Employee CRUD Operations

**Create Employee:**
```python
await graph.ainvoke({
    "messages": [HumanMessage(content="""
        Create a new employee:
        - Name: Jane Smith
        - Mobile: 27821234567
        - Email: jane.smith@company.com
        - Employee No: EMP123
        - Salary: 75000
    """)]
}, config)
```

**Update Employee:**
```python
await graph.ainvoke({
    "messages": [HumanMessage(content="""
        Update employee ID 5:
        - New email: jane.updated@company.com
        - New status: on_leave
    """)]
}, config)
```

**Delete Employee:**
```python
await graph.ainvoke({
    "messages": [HumanMessage(content="Deactivate employee ID 5")]
}, config)
```

### Leave Management Operations

**Check Leave Balance:**
```python
await graph.ainvoke({
    "messages": [HumanMessage(content="Show my leave balance")]
}, config)
```

**Create Leave Request:**
```python
await graph.ainvoke({
    "messages": [HumanMessage(content="""
        Create a leave request:
        - Type: annual
        - Start: 2025-02-15
        - End: 2025-02-20
        - Reason: Family vacation
    """)]
}, config)
```

**Approve Leave Request:**
```python
await graph.ainvoke({
    "messages": [HumanMessage(content="Approve leave request ID 42")]
}, config)
```

**View Pending Requests (Managers):**
```python
await graph.ainvoke({
    "messages": [HumanMessage(content="Show me pending leave requests from my team")]
}, config)
```

### Organizational Queries

```python
# Query employee information
await graph.ainvoke({
    "messages": [HumanMessage(content="Who is John's manager?")]
}, config)

# Query organizational structure
await graph.ainvoke({
    "messages": [HumanMessage(content="Show me all employees in the Sales division")]
}, config)

# Query salary information (requires HR Admin role)
await graph.ainvoke({
    "messages": [HumanMessage(content="What is the average salary in the Engineering department?")]
}, config)
```

## Direct Tool Usage

You can also use the subagents directly as tools:

### Employee CRUD Agent

```python
from agent.subagents.employee_crud_agent import employee_crud_agent

result = await employee_crud_agent.ainvoke({
    "operation": "create",
    "admin_id": 1,
    "employee_data": {
        "first_name": "John",
        "last_name": "Doe",
        "mobile_number": "27821234567",
        "email": "john.doe@example.com",
        "employer_id": 1,
        "employee_no": "EMP001",
        "salary": 50000.0
    }
})

print(result)
```

### Leave Management Agent

```python
from agent.subagents.leave_agent import leave_management_agent

result = await leave_management_agent.ainvoke({
    "operation": "create",
    "admin_id": 1,
    "leave_data": {
        "employee_id": 1,
        "leave_type": "annual",
        "start_date": "2025-03-15",
        "end_date": "2025-03-20",
        "reason": "Vacation"
    }
})

print(result)
```

### Query Agent

```python
from agent.subagents.query_agent import query_employee_info

result = await query_employee_info.ainvoke({
    "question": "Who reports to employee ID 1?",
    "admin_id": 1
})

print(result)
```

## Testing

Run the comprehensive test suite:

```bash
# Run all HR admin tests
pytest tests/test_hr_admin/

# Run specific test files
pytest tests/test_hr_admin/test_employee_crud.py
pytest tests/test_hr_admin/test_leave_management.py
pytest tests/test_hr_admin/test_authorization.py
pytest tests/test_hr_admin/test_integration.py

# Run with coverage
pytest --cov=agent.subagents --cov=agent.tools tests/test_hr_admin/
```

## Neo4j Schema

### Employee CRUD

**Nodes:**
- `Employee` - Employee records with properties (id, first_name, last_name, mobile_number, email, salary, status, etc.)
- `Employer` - Company information
- `Division` - Organizational divisions
- `Branch` - Physical locations

**Relationships:**
- `(Employee)-[:REPORTS_TO]->(Employee)` - Manager hierarchy
- `(Employee)-[:WORKS_FOR]->(Employer)` - Employment
- `(Employee)-[:IN_DIVISION]->(Division)` - Team membership
- `(Employee)-[:ASSIGNED_TO_BRANCH]->(Branch)` - Location

### Leave Management

**Nodes:**
- `LeaveRequest` - Leave requests with dates, type, status, reason
- `LeaveBalance` - Annual leave balances by type and year

**Relationships:**
- `(Employee)-[:SUBMITTED_LEAVE]->(LeaveRequest)` - Employee submitted request
- `(Employee)-[:APPROVED_LEAVE]->(LeaveRequest)` - Manager approved request
- `(Employee)-[:HAS_BALANCE]->(LeaveBalance)` - Employee's leave balance

### Audit Logging

**Nodes:**
- `AuditLog` - Audit trail of all administrative operations

**Relationships:**
- `(Employee)-[:PERFORMED]->(AuditLog)` - Admin performed action

## Security Considerations

1. **Authentication**: Integrate with your organization's SSO/authentication system
2. **Authorization**: Role assignments should be managed through a secure admin interface
3. **Audit Logging**: All operations are logged for compliance and security
4. **Data Validation**: All inputs are validated before database operations
5. **Human Approval**: Sensitive operations require explicit human confirmation

## Extending the Agent

### Adding New Operations

1. **Create a new tool** in `src/agent/tools/`:

```python
from langchain_core.tools import tool

@tool
async def new_operation(param1: str, param2: int) -> dict:
    """Description of the operation."""
    # Implementation
    pass
```

2. **Add to appropriate subagent** in `src/agent/subagents/`:

```python
from agent.tools.new_tool import new_operation

# Use in subagent logic
result = await new_operation.ainvoke({...})
```

3. **Update permissions** in `src/agent/tools/authorization.py`:

```python
class Permission(str, Enum):
    NEW_OPERATION = "new_operation"

ROLE_PERMISSIONS[AdminRole.HR_ADMIN].add(Permission.NEW_OPERATION)
```

### Adding New Roles

Edit `src/agent/tools/authorization.py`:

```python
class AdminRole(str, Enum):
    NEW_ROLE = "new_role"

ROLE_PERMISSIONS[AdminRole.NEW_ROLE] = {
    Permission.VIEW_EMPLOYEE,
    # Add permissions
}
```

## Troubleshooting

### Common Issues

**Issue: "Neo4j credentials not found"**
- Solution: Ensure `.env` file has `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`

**Issue: "Employee not found"**
- Solution: Check employee exists in database, verify ID is correct

**Issue: "Permission denied"**
- Solution: Verify admin has correct role and permissions for the operation

**Issue: "Insufficient leave balance"**
- Solution: Run seed script to initialize leave balances, or manually create balances

### Debug Mode

Enable detailed logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

## Performance Optimization

- **Connection pooling**: Neo4j driver uses connection pooling by default
- **Caching**: Consider adding caching for frequently queried employee data
- **Batch operations**: For bulk updates, create dedicated batch tools
- **Indexes**: Schema includes indexes on frequently queried fields

## Future Enhancements

- [ ] Integration with HRIS systems
- [ ] Email notifications for leave approvals/rejections
- [ ] Slack/Teams integration for approval workflows
- [ ] Advanced reporting and analytics
- [ ] Employee onboarding workflows
- [ ] Performance review management
- [ ] Document management integration

## License

See LICENSE file in repository root.

## Support

For issues and questions, please open an issue on the GitHub repository.
