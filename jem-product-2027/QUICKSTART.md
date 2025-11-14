# HR Admin Agent - Quick Start Guide

## What Was Built

A production-ready HR Deep Agent using LangChain's multi-agent supervisor pattern that enables HR administrators to manage employees and leave requests through natural language conversations.

### Key Components

✅ **Neo4j Schema Extension**
- Leave management nodes (LeaveRequest, LeaveBalance)
- Audit logging system
- Migration scripts and seed data

✅ **CRUD Tools** (`src/agent/tools/`)
- `neo4j_crud_tool.py` - Employee create, update, delete operations
- `leave_management_tool.py` - Leave requests, approvals, balance queries
- `authorization.py` - RBAC with 4 role levels and audit logging

✅ **Specialized Subagents** (`src/agent/subagents/`)
- `employee_crud_agent.py` - Handles employee lifecycle management
- `leave_agent.py` - Manages leave workflows
- `query_agent.py` - Wraps existing employee query functionality

✅ **HR Supervisor Agent** (`src/agent/hr_admin_graph.py`)
- Main orchestrator using LangGraph StateGraph
- Human-in-the-loop approval workflow
- Intelligent request classification and routing

✅ **Comprehensive Tests** (`tests/test_hr_admin/`)
- Employee CRUD tests
- Leave management tests
- Authorization and RBAC tests
- Integration tests for full workflows

## Getting Started (5 Minutes)

### 1. Apply Database Schema

Open Neo4j Browser and execute the schema:

```bash
# Copy and run the Cypher from:
cat src/database/migrations/001_leave_management_schema.cypher
```

### 2. Seed Leave Data

Initialize leave balances for existing employees:

```bash
python src/database/migrations/002_seed_leave_data.py
```

### 3. Test the Agent

Run a quick test:

```python
import asyncio
from agent.hr_admin_graph import graph
from langchain_core.messages import HumanMessage

async def test_hr_agent():
    config = {"configurable": {"thread_id": "test_1"}}

    # Query employee information
    response = await graph.ainvoke({
        "messages": [HumanMessage(content="Show me my leave balance")]
    }, config)

    print(response["messages"][-1].content)

asyncio.run(test_hr_agent())
```

### 4. Run Tests

Verify everything works:

```bash
# Run all tests
pytest tests/test_hr_admin/ -v

# Run specific test category
pytest tests/test_hr_admin/test_employee_crud.py -v
```

## Common Use Cases

### 1. Employee Onboarding

```python
await graph.ainvoke({
    "messages": [HumanMessage(content="""
        Create a new employee:
        - Name: Sarah Johnson
        - Mobile: 27823456789
        - Email: sarah.johnson@company.com
        - Employee No: EMP2025001
        - Salary: 85000
        - Reports to: Employee ID 1
    """)]
}, config)
```

**Flow:**
1. Supervisor classifies as "crud" operation
2. Routes to Employee CRUD Agent
3. Requires human approval (create operation)
4. Admin approves
5. Employee created in Neo4j
6. Audit log entry created

### 2. Leave Request Approval

```python
# Manager checks pending requests
await graph.ainvoke({
    "messages": [HumanMessage(content="Show pending leave requests")]
}, config)

# Approve specific request
await graph.ainvoke({
    "messages": [HumanMessage(content="Approve leave request 123")]
}, config)
```

**Flow:**
1. Supervisor classifies as "leave" operation
2. Routes to Leave Management Agent
3. Requires human approval
4. Admin approves
5. Leave balance updated
6. Audit log created

### 3. Organizational Queries

```python
await graph.ainvoke({
    "messages": [HumanMessage(content="Who are the managers in Sales division?")]
}, config)
```

**Flow:**
1. Supervisor classifies as "query" operation
2. Routes to Query Agent
3. Executes Neo4j natural language query
4. Returns formatted results (no approval needed)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    HR Supervisor Agent                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │
│  │Authenticate│─▶│  Classify  │─▶│  Route to Specialist│   │
│  │   Admin    │  │  Request   │  │                     │    │
│  └────────────┘  └────────────┘  └──────────┬─────────┘    │
│                                              │              │
│                          ┌───────────────────┼──────────┐   │
│                          │                   │          │   │
│                   ┌──────▼──────┐   ┌────────▼─────┐   │   │
│                   │   Query     │   │   CRUD       │   │   │
│                   │   Agent     │   │   Agent      │   │   │
│                   └─────────────┘   └──────┬───────┘   │   │
│                                             │           │   │
│                                    ┌────────▼───────┐   │   │
│                                    │ Leave Agent    │───┤   │
│                                    └────────────────┘   │   │
│                                             │           │   │
│                          ┌──────────────────▼──────┐    │   │
│                          │  Confirm with Human     │    │   │
│                          │  (Human-in-the-Loop)    │    │   │
│                          └──────────┬──────────────┘    │   │
│                                     │                   │   │
│                          ┌──────────▼──────────────┐    │   │
│                          │   Execute Action        │    │   │
│                          └─────────────────────────┘    │   │
└─────────────────────────────────────────────────────────┘

                                   │
                    ┌──────────────▼────────────────┐
                    │        Neo4j Database         │
                    │  ┌────────────────────────┐   │
                    │  │  Employee Nodes        │   │
                    │  │  LeaveRequest Nodes    │   │
                    │  │  LeaveBalance Nodes    │   │
                    │  │  AuditLog Nodes        │   │
                    │  └────────────────────────┘   │
                    └───────────────────────────────┘
```

## Role-Based Access Control

| Role        | Create Employee | Update Salary | Delete Employee | Approve Leave | View Data |
|-------------|----------------|---------------|-----------------|---------------|-----------|
| HR Admin    | ✅             | ✅            | ✅              | ✅            | ✅        |
| HR Manager  | ❌             | ❌            | ❌              | ✅            | ✅        |
| HR Viewer   | ❌             | ❌            | ❌              | ❌            | ✅        |
| Employee    | ❌             | ❌            | ❌              | ❌            | Own data only |

## Human-in-the-Loop Operations

These operations require explicit admin approval:

1. ✅ **Create Employee** - Prevents unauthorized account creation
2. ✅ **Delete Employee** - Prevents accidental data loss
3. ✅ **Update Salary** - Requires management approval for compensation changes
4. ✅ **Create Leave Request** - Manager review for time-off requests
5. ✅ **Approve/Reject Leave** - Final authorization by appropriate manager

## Next Steps

1. **Integrate with Authentication**: Connect to your SSO/auth system
2. **Add Notifications**: Implement email/Slack alerts for approvals
3. **Deploy to Production**: Use LangGraph Studio for deployment
4. **Monitor and Optimize**: Set up logging and performance monitoring
5. **Extend Functionality**: Add more HR workflows (onboarding, reviews, etc.)

## File Structure

```
jem-product-2027/
├── src/
│   ├── agent/
│   │   ├── hr_admin_graph.py          # Main supervisor agent
│   │   ├── graph.py                   # Original employee greeting agent
│   │   ├── tools/
│   │   │   ├── neo4j_crud_tool.py     # Employee CRUD operations
│   │   │   ├── leave_management_tool.py # Leave operations
│   │   │   ├── authorization.py        # RBAC and audit logging
│   │   │   └── neo4j_tool.py          # Original query tools
│   │   └── subagents/
│   │       ├── employee_crud_agent.py  # CRUD subagent
│   │       ├── leave_agent.py          # Leave subagent
│   │       └── query_agent.py          # Query subagent
│   └── database/
│       └── migrations/
│           ├── 001_leave_management_schema.cypher
│           └── 002_seed_leave_data.py
├── tests/
│   └── test_hr_admin/
│       ├── test_employee_crud.py
│       ├── test_leave_management.py
│       ├── test_authorization.py
│       └── test_integration.py
├── HR_ADMIN_README.md                  # Detailed documentation
└── QUICKSTART.md                       # This file
```

## Key Technologies

- **LangChain**: Agent framework and tool calling
- **LangGraph**: State management and workflow orchestration
- **Claude (Haiku)**: LLM for classification and query generation
- **Neo4j**: Graph database for employee and leave data
- **Python AsyncIO**: Asynchronous database operations

## Support and Documentation

- **Full Documentation**: See `HR_ADMIN_README.md`
- **Test Examples**: Check `tests/test_hr_admin/` for usage patterns
- **LangChain Docs**: https://python.langchain.com/docs/
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/

---

**🎉 You're all set!** The HR Admin Agent is ready to help manage your employees and leave requests through natural language conversations.
