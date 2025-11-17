# Testing Guide - Backup & Restore for Safe Testing

## Overview

When testing the HR Admin agent (especially bulk operations), you want to safely test without permanently affecting your production data. This guide shows how to create backups and restore your Neo4j database.

---

## Quick Start: Testing Workflow

### Step 1: Create Snapshot Before Testing

```bash
# Create snapshot of employer 189 data
python src/database/backup_restore.py snapshot 189
```

**Output:**
```
🔍 Backing up Neo4j database...
   Scope: Employer ID 189 only
   📦 Backing up Employee nodes...
   📦 Backing up REPORTS_TO relationships...
   📦 Backing up LeaveBalance nodes...
   📦 Backing up LeaveRequest nodes...

✅ Backup complete: data/neo4j_backups/test_snapshot_employer_189.cypher
   Total size: 45.3 KB

💾 Test snapshot created: data/neo4j_backups/test_snapshot_employer_189.cypher
   Use this to restore after testing
```

### Step 2: Run Your Tests

```bash
# Now test freely - bulk imports, manager updates, etc.
python test_bulk_manager_updates.py

# Or test via LangGraph Studio
# Message: "Import messy CSV with 5000 employees"
```

### Step 3: Restore from Snapshot

```bash
# Rollback to pre-test state
python src/database/backup_restore.py rollback data/neo4j_backups/test_snapshot_employer_189.cypher
```

**Output:**
```
🔄 Rolling back to snapshot: data/neo4j_backups/test_snapshot_employer_189.cypher
⚠️  Clearing existing data...
   ✅ Database cleared
📥 Restoring from: data/neo4j_backups/test_snapshot_employer_189.cypher
   Found 245 statements to execute
   Progress: 100/245 statements...
   Progress: 200/245 statements...

✅ Restore complete: 245 statements executed
✅ Rollback successful!
```

---

## Backup Commands

### Full Database Backup

```bash
# Backup entire database (all employers)
python src/database/backup_restore.py backup

# Creates: data/neo4j_backups/backup_20251114_143022.cypher
```

**Use for:** Production backups, full system restore

### Employer-Scoped Backup

```bash
# Backup only employer 189 data
python src/database/backup_restore.py backup 189

# Creates: data/neo4j_backups/backup_20251114_143022_employer_189.cypher
```

**Use for:** Multi-tenant testing, scoped restores

### Test Snapshot (Recommended for Testing)

```bash
# Create named snapshot for testing
python src/database/backup_restore.py snapshot 189

# Creates: data/neo4j_backups/test_snapshot_employer_189.cypher
```

**Use for:** Before running destructive tests

---

## Restore Commands

### Restore from Backup

```bash
# Restore database (WARNING: Deletes existing data!)
python src/database/backup_restore.py restore data/neo4j_backups/backup_20251114_143022.cypher
```

**⚠️ Warning:** This **deletes all existing data** before restoring!

### Rollback to Snapshot

```bash
# Rollback to pre-test state
python src/database/backup_restore.py rollback data/neo4j_backups/test_snapshot_employer_189.cypher
```

**Use after:** Bulk import tests, manager updates, data experiments

---

## List Backups

```bash
# See all available backups
python src/database/backup_restore.py list
```

**Output:**
```
📦 Available Backups:
============================================================
1. test_snapshot_employer_189.cypher
   Size: 45.3 KB
   Created: 2025-11-14 14:30:22

2. backup_20251114_120000_employer_189.cypher
   Size: 45.1 KB
   Created: 2025-11-14 12:00:00

3. backup_20251113_180000.cypher
   Size: 523.7 KB
   Created: 2025-11-13 18:00:00
```

---

## Testing Best Practices

### Recommended Workflow

**1. Daily Testing:**
```bash
# Morning: Create fresh snapshot
python src/database/backup_restore.py snapshot 189

# During day: Test freely
# - Bulk imports
# - Manager updates
# - Leave approvals
# - CRUD operations

# End of day: Rollback if needed
python src/database/backup_restore.py rollback data/neo4j_backups/test_snapshot_employer_189.cypher
```

**2. Before Bulk Operations:**
```bash
# Before importing 5000 employees
python src/database/backup_restore.py snapshot 189

# Run bulk import
"Process data/new_hires_5000.csv to import employees"

# If something went wrong:
python src/database/backup_restore.py rollback data/neo4j_backups/test_snapshot_employer_189.cypher
```

**3. Automated Testing:**
```python
# In your test files
import pytest
from src.database.backup_restore import create_test_snapshot, rollback_to_snapshot

@pytest.fixture(scope="module")
async def neo4j_snapshot():
    """Create snapshot before tests, restore after."""
    snapshot = await create_test_snapshot(employer_id=189)
    yield snapshot
    await rollback_to_snapshot(snapshot)

async def test_bulk_import(neo4j_snapshot):
    """Test runs in isolated snapshot."""
    # Test bulk import...
    # Database will be restored automatically after test
```

---

## What Gets Backed Up

### Nodes:
- ✅ Employee (all properties)
- ✅ LeaveBalance (balances for all leave types)
- ✅ LeaveRequest (pending, approved, rejected)
- ⚠️ Employer, Division, Branch (if referenced)
- ⚠️ AuditLog (optional - can be large)

### Relationships:
- ✅ REPORTS_TO (manager hierarchy)
- ✅ HAS_BALANCE (leave balances)
- ✅ SUBMITTED_LEAVE (leave requests)
- ✅ APPROVED_LEAVE (approval relationships)
- ✅ WORKS_FOR (employment)

### Not Backed Up:
- Constraints and indexes (reapply with schema migration)
- Graph-level metadata

---

## Backup File Format

**Example Backup File:**
```cypher
// Neo4j Database Backup
// Created: 2025-11-14T14:30:22
// Scope: Employer ID 189
//

// Employee Nodes (9 records)
CREATE (e101487:Employee {id: 101487, first_name: 'Thamsanqa', last_name: 'Moyo', ...});
CREATE (e22483:Employee {id: 22483, first_name: 'Sinta', last_name: 'Reynolds', ...});
...

// REPORTS_TO Relationships (8 records)
MATCH (e:Employee {id: 22483}), (m:Employee {id: 101487}) CREATE (e)-[:REPORTS_TO]->(m);
...

// LeaveBalance Nodes (27 records)
MATCH (e:Employee {id: 101487}) CREATE (e)-[:HAS_BALANCE]->(:LeaveBalance {employee_id: 101487, year: 2025, leave_type: 'annual', ...});
...

// Backup complete
```

---

## Advanced Options

### Python API

```python
from src.database.backup_restore import (
    backup_neo4j_database,
    restore_neo4j_database,
    create_test_snapshot,
    rollback_to_snapshot,
)

# Create backup
backup_path = await backup_neo4j_database(
    backup_name="before_bulk_import",
    employer_id=189
)

# Restore
success = await restore_neo4j_database(backup_path, clear_existing=True)
```

### Scheduled Backups (Optional)

```bash
# Add to crontab for daily backups
0 2 * * * cd /path/to/project && python src/database/backup_restore.py backup 189
```

### Differential Backups

For large databases, consider:
- Backup only changed data since last backup
- Use Neo4j APOC procedures for incremental exports
- Store backups in S3/cloud storage

---

## Neo4j Aura Cloud Backups

If using Neo4j Aura, you also have:

### **1. Automatic Snapshots (Aura Professional)**
- Daily automatic backups
- 7-day retention
- Restore via Aura Console

### **2. Manual Snapshots (Aura Console)**
- Go to: https://console.neo4j.io
- Select your database
- Click "Snapshots"
- Create snapshot manually
- Restore when needed

### **3. Export Database**
- Aura Console → "Actions" → "Export"
- Downloads .dump file
- Import to new instance

---

## Testing Strategies

### Strategy 1: Snapshot & Rollback (Recommended)

**Best for:** Daily testing, experimenting with bulk operations

```bash
# Before testing
python src/database/backup_restore.py snapshot 189

# Test
# ...

# Restore
python src/database/backup_restore.py rollback data/neo4j_backups/test_snapshot_employer_189.cypher
```

**Pros:** Fast, complete isolation, repeatable
**Cons:** Clears ALL data during restore

### Strategy 2: Separate Test Database

**Best for:** Continuous testing, CI/CD

- Create separate Neo4j Aura instance for testing
- Use TEST_NEO4J_URI in .env.test
- Never affects production
- Can destroy/recreate freely

**Pros:** True isolation, no restore needed
**Cons:** Additional database cost

### Strategy 3: Transaction Rollback (Limited)

**Best for:** Unit tests, small operations

```python
async with driver.session() as session:
    tx = await session.begin_transaction()
    try:
        # Run test operations
        await tx.run("CREATE (e:Employee {...})")

        # Verify results
        # ...

        # Rollback instead of commit
        await tx.rollback()
    finally:
        await session.close()
```

**Pros:** Fast, no backup needed
**Cons:** Only works within single session, limited scope

### Strategy 4: Test Data Markers

**Best for:** Shared test environments

```python
# Mark test data
CREATE (e:Employee {id: 999001, first_name: 'TEST', is_test_data: true, ...})

# Clean up test data
MATCH (n {is_test_data: true}) DETACH DELETE n
```

**Pros:** Can run tests alongside real data
**Cons:** Risk of mixing test and real data

---

## Recommended Approach for Your Use Case

### For Bulk CSV Testing (5000 records):

```bash
# 1. Create snapshot BEFORE bulk import
python src/database/backup_restore.py snapshot 189

# 2. Test bulk import
"Process data/test_5000_employees.csv to import employees"

# 3. Verify results
"Show me all employees in my company"
"Who reports to Gustavo Mendes?"

# 4. Rollback when done
python src/database/backup_restore.py rollback data/neo4j_backups/test_snapshot_employer_189.cypher

# 5. Verify restore
"Show me all employees"
# Should be back to original 9 employees
```

---

## Troubleshooting

**Issue: "Backup file too large"**
- Use employer-scoped backups: `snapshot 189`
- Exclude audit logs if not needed
- Compress with gzip: `gzip backup.cypher`

**Issue: "Restore fails partway"**
- Check Cypher syntax in backup file
- Verify constraints are created first
- Check Neo4j connection limits

**Issue: "Snapshot doesn't include new nodes"**
- Ensure employer_id is set correctly on all nodes
- Check scoping query in backup script
- Verify relationships are captured

---

## Safety Checklist

Before running `restore` or `rollback`:

- [ ] Confirm you have a recent backup
- [ ] Verify backup file exists and is valid
- [ ] Check backup file size is reasonable
- [ ] Understand this DELETES existing data
- [ ] Not running in production (use test database)
- [ ] Have confirmed from team if shared database

---

## Backup Schedule Recommendations

**Development:**
- Snapshot before each testing session
- Keep last 7 days of snapshots
- Delete old snapshots monthly

**Staging:**
- Daily automatic backups
- Keep last 30 days
- Weekly archives for 6 months

**Production:**
- Use Neo4j Aura automatic backups
- Manual snapshot before major changes
- Disaster recovery plan in place

---

**🎯 You're now ready to test safely with full backup/restore capabilities!**

Create a snapshot, test your bulk operations, and rollback when done. Your data is protected! 🛡️
