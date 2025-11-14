// Leave Management Schema Migration
// This script extends the existing Employee schema with leave management capabilities

// ============================================================================
// CREATE CONSTRAINTS
// ============================================================================

// Ensure unique leave request IDs
CREATE CONSTRAINT leave_request_id IF NOT EXISTS
FOR (lr:LeaveRequest) REQUIRE lr.id IS UNIQUE;

// Ensure unique leave balance combinations (employee + year + leave_type)
CREATE CONSTRAINT leave_balance_unique IF NOT EXISTS
FOR (lb:LeaveBalance) REQUIRE (lb.employee_id, lb.year, lb.leave_type) IS UNIQUE;

// ============================================================================
// CREATE INDEXES FOR PERFORMANCE
// ============================================================================

// Index on leave request status for filtering
CREATE INDEX leave_request_status IF NOT EXISTS
FOR (lr:LeaveRequest) ON (lr.status);

// Index on leave request dates for range queries
CREATE INDEX leave_request_start_date IF NOT EXISTS
FOR (lr:LeaveRequest) ON (lr.start_date);

// Index on employee_id for quick lookups
CREATE INDEX leave_request_employee_id IF NOT EXISTS
FOR (lr:LeaveRequest) ON (lr.employee_id);

// Index on leave balance year for current year queries
CREATE INDEX leave_balance_year IF NOT EXISTS
FOR (lb:LeaveBalance) ON (lb.year);

// ============================================================================
// SCHEMA DOCUMENTATION
// ============================================================================

// LeaveRequest Node Properties:
// - id: int (unique identifier)
// - employee_id: int (references Employee.id)
// - leave_type: str ('annual', 'sick', 'unpaid', 'maternity', 'paternity', 'study', 'compassionate')
// - start_date: date (format: YYYY-MM-DD)
// - end_date: date (format: YYYY-MM-DD)
// - days_requested: float (calculated business days)
// - status: str ('pending', 'approved', 'rejected', 'cancelled', 'withdrawn')
// - reason: str (employee's reason for leave)
// - rejection_reason: str (optional - manager's reason for rejection)
// - approved_by_id: int (optional - manager who approved)
// - created_at: datetime
// - updated_at: datetime

// LeaveBalance Node Properties:
// - employee_id: int (references Employee.id)
// - year: int (e.g., 2025)
// - leave_type: str (same types as LeaveRequest)
// - total_days: float (annual allocation)
// - used_days: float (days taken/approved)
// - pending_days: float (days in pending requests)
// - remaining_days: float (total - used - pending)
// - updated_at: datetime

// Relationships:
// (:Employee)-[:SUBMITTED_LEAVE]->(:LeaveRequest)
// (:Employee)-[:APPROVED_LEAVE]->(:LeaveRequest)  // Manager who approved
// (:Employee)-[:HAS_BALANCE]->(:LeaveBalance)

// ============================================================================
// SAMPLE DATA (for testing purposes)
// ============================================================================

// Note: Run this separately after understanding your existing employee data
// This is commented out by default to prevent accidental data insertion

// Example: Initialize leave balances for all active employees (2025)
/*
MATCH (e:Employee)
WHERE e.status = 'active'
MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
    employee_id: e.id,
    year: 2025,
    leave_type: 'annual'
})
SET lb.total_days = 21.0,
    lb.used_days = 0.0,
    lb.pending_days = 0.0,
    lb.remaining_days = 21.0,
    lb.updated_at = datetime()
*/

// Example: Create sick leave balance
/*
MATCH (e:Employee)
WHERE e.status = 'active'
MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
    employee_id: e.id,
    year: 2025,
    leave_type: 'sick'
})
SET lb.total_days = 30.0,
    lb.used_days = 0.0,
    lb.pending_days = 0.0,
    lb.remaining_days = 30.0,
    lb.updated_at = datetime()
*/
