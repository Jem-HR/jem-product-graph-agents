# JEM Product Graph Agents

Production-ready HR management agents built with LangGraph, featuring employee CRUD operations, leave management, and intelligent bulk CSV processing.

## Overview

This project contains two LangGraph agents:

### 1. **Employee Greeting Agent** (`agent`)
Simple employee authentication and query agent that:
- Authenticates employees via mobile number
- Provides personalized greetings
- Answers questions about organizational structure using Neo4j

### 2. **HR Admin Deep Agent** (`hr_admin`) ⭐ NEW
Sophisticated multi-agent system for HR administrators with:
- **Employee CRUD** - Create, update, delete employee records
- **Leave Management** - Requests, approvals, balance tracking
- **Bulk CSV Processing** - Import/update up to 5000 employees
- **Smart CSV Processing** - Handles messy data with automatic cleaning
- **Enhanced Classification** - Confidence scoring and context awareness
- **Multi-tenant Security** - Employer-scoped data isolation
- **Human-in-the-Loop** - Approval workflows for sensitive operations

## Quick Start

### Prerequisites

- Python 3.11+
- Neo4j Aura database (or local Neo4j instance)
- Anthropic API key

### Installation

```bash
# Clone repository
git clone git@github.com:Jem-HR/jem-product-graph-agents.git
cd jem-product-graph-agents/jem-product-2027

# Install dependencies
pip install -e . "langgraph-cli[inmem]"

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Database Setup

```bash
# Apply Neo4j schema for leave management
python src/database/migrations/run_migration.py src/database/migrations/001_leave_management_schema.cypher

# Seed leave balance data
python src/database/migrations/002_seed_leave_data.py
```

### Run LangGraph Studio

```bash
langgraph dev
```

Access at: **https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024**

Select either:
- **`agent`** - Employee greeting agent
- **`hr_admin`** - HR Admin agent (recommended)

## HR Admin Agent Features

### 🎯 Core Capabilities

**Employee Management:**
- Create new employees with validation
- Update employee information (email, salary, status, etc.)
- Soft/hard delete employee records
- Update manager relationships (change leave approvers)
- Query organizational structure

**Leave Management:**
- Check leave balances (annual, sick, family)
- Create leave requests with balance validation
- Approve/reject leave requests
- View pending approvals
- Leave history and reporting

**Bulk Operations:**
- Import employees from CSV (up to 5000 records)
- Update manager relationships in bulk
- Automatic data cleaning for messy CSVs
- Fuzzy column matching (90+ name variations)
- Comprehensive error reporting

### 🔒 Security & Compliance

- **Role-Based Access Control** - 4 permission levels (Admin, Manager, Viewer, Employee)
- **Multi-Tenant Isolation** - All queries scoped to employer
- **Audit Logging** - Every operation tracked in Neo4j
- **Human Approval** - Sensitive operations require explicit confirmation
- **Data Validation** - Mobile numbers, emails, duplicates

### 🧠 Intelligent Classification

- **Confidence Scoring** - Know when system is uncertain
- **Chain-of-Thought Reasoning** - Transparent decision-making
- **Context Awareness** - Remembers conversation, resolves pronouns
- **Multi-Intent Detection** - Handles compound requests
- **Graceful Degradation** - Asks for clarification when unsure

## Architecture

```
HR Supervisor Agent
├── Authentication (Employee ID 101487 as HR Admin)
├── Enhanced Classifier (confidence scoring, context awareness)
├── Query Agent → Neo4j organizational queries
├── Employee CRUD Agent → Create/update/delete employees
├── Leave Management Agent → Leave requests and approvals
├── Bulk Processing Agent → Standard CSV imports (clean data)
└── Smart CSV Agent → Variable-format CSV with data cleaning
```

## Usage Examples

### Interactive Operations

```python
# Via LangGraph Studio or API
"Show my leave balance"
"Who are the managers in my company?"
"Create a leave request from 2025-12-20 to 2025-12-27"
"Approve leave request 123"
"Update employee 22483's email to new@email.com"
```

### Bulk CSV Operations

```python
# Standard clean CSV
"Import employees from data/new_hires_2025.csv"

# Messy CSV with automatic cleaning
"Process messy CSV from external HR system - data needs cleaning"
```

**CSV Formats Supported:**

**Import Employees:**
```csv
first_name,last_name,mobile_number,email,employee_no,salary
John,Doe,27821234567,john@company.com,EMP001,55000
```

**Update Leave Approvers:**
```csv
employee_id,new_manager_id
22483,22489
101919,22465
```

**Messy Data (handled automatically):**
```csv
First Name,Surname,Cell Number,E-mail Address,Staff #,Monthly Pay
John,DOE,+27 82 123 4567,john@company.com,EMP001,"R 55,000"
```

## Documentation

- **[HR_ADMIN_README.md](./HR_ADMIN_README.md)** - Complete HR Admin agent documentation
- **[QUICKSTART.md](./QUICKSTART.md)** - 5-minute setup guide
- **[BULK_OPERATIONS_GUIDE.md](./BULK_OPERATIONS_GUIDE.md)** - CSV processing guide
- **[HOW_AGENT_DECIDES.md](./HOW_AGENT_DECIDES.md)** - Classification system explained
- **[ENHANCED_CLASSIFICATION_SUMMARY.md](./ENHANCED_CLASSIFICATION_SUMMARY.md)** - Advanced features

## Testing

```bash
# Run all tests
pytest tests/test_hr_admin/ -v

# Specific test suites
pytest tests/test_hr_admin/test_employee_crud.py -v
pytest tests/test_hr_admin/test_leave_management.py -v
pytest tests/test_hr_admin/test_authorization.py -v
pytest tests/test_hr_admin/test_bulk_operations.py -v
pytest tests/test_hr_admin/test_classification.py -v
```

## Configuration

### Environment Variables

Required in `.env`:

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Neo4j Aura
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...

# LangSmith (optional)
LANGSMITH_API_KEY=lsv2...
LANGSMITH_PROJECT=hr-admin-agent
```

### Authentication

**Current (Development):**
- Hard-coded to employee ID 101487 (Thamsanqa Moyo)
- Employer ID 189 (auto-scoped)

**Production:**
- Integrate with your SSO/authentication system
- Pass employee_id via runtime config
- See `HR_ADMIN_README.md` for JWT/OAuth examples

## Technology Stack

- **LangChain** - Agent framework and tool calling
- **LangGraph** - State management and workflow orchestration
- **Claude Haiku 4.5** - Fast LLM for classification and queries
- **Neo4j Aura** - Graph database for employee and leave data
- **Pandas** - CSV processing and data manipulation
- **Pydantic** - Structured outputs and validation
- **Pytest** - Testing framework

## Performance

- **Classification:** 1-2 seconds (Claude Haiku)
- **Simple queries:** 3-5 seconds
- **Leave operations:** 5-10 seconds
- **Bulk CSV (5000 records):** ~4 minutes
- **Data cleaning:** ~5 seconds for 5-record CSV

## Project Structure

```
jem-product-2027/
├── src/
│   ├── agent/
│   │   ├── graph.py                   # Employee greeting agent
│   │   ├── hr_admin_graph.py          # HR Admin supervisor agent
│   │   ├── schemas/                   # Pydantic models
│   │   ├── subagents/                 # Specialized agents
│   │   │   ├── employee_crud_agent.py
│   │   │   ├── leave_agent.py
│   │   │   ├── query_agent.py
│   │   │   ├── bulk_processing_agent.py
│   │   │   └── smart_csv_agent.py
│   │   ├── tools/                     # Neo4j tools, auth, CSV processing
│   │   └── utils/                     # Context extraction utilities
│   └── database/
│       └── migrations/                # Schema and seed scripts
├── tests/
│   └── test_hr_admin/                 # Comprehensive test suite
├── data/
│   ├── sample_csvs/                   # Example CSV files
│   └── csv_results/                   # Processing results
└── Documentation (5 guides)
```

## Key Features

### ✅ Implemented

- [x] Multi-agent supervisor pattern
- [x] Employee CRUD with RBAC
- [x] Leave request workflows
- [x] Bulk CSV processing (5000 records)
- [x] Smart CSV with data cleaning
- [x] Enhanced classification system
- [x] Confidence scoring and context awareness
- [x] Multi-tenant data isolation
- [x] Human-in-the-loop approvals
- [x] Audit logging
- [x] Comprehensive tests
- [x] Fuzzy column matching
- [x] Mobile number cleaning (20+ formats)
- [x] Email validation
- [x] Employer scoping for all queries

### 🚀 Tested & Verified

- Employee 101487 authenticated as HR Admin ✓
- Leave balance queries (21 annual, 10 sick, 3 family days) ✓
- Manager relationship updates via CSV (2/2 successful) ✓
- Organizational queries scoped to employer 189 ✓
- Messy CSV processing (4/5 cleaned successfully) ✓
- Data cleaning (mobile, email, salary normalization) ✓

## Contributing

This project uses:
- Black for code formatting
- pytest for testing
- Type hints throughout
- Comprehensive documentation

## License

See [LICENSE](./LICENSE)

## Support

For issues and questions:
- GitHub Issues: https://github.com/Jem-HR/jem-product-graph-agents/issues
- Documentation: See markdown files in project root

---

**Built with LangChain, LangGraph, and Claude** 🤖
