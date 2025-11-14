"""CSV file processing tools for bulk employee and leave operations.

Handles parsing, validation, and batch processing of employee data from CSV files.
Supports up to 5000 records per file with comprehensive error reporting.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from langchain_core.tools import tool


# CSV upload directory
CSV_UPLOAD_DIR = Path("data/csv_uploads")
CSV_RESULTS_DIR = Path("data/csv_results")

# Ensure directories exist
CSV_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CSV_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@tool
def upload_csv_file(
    file_content: str,
    filename: str,
    operation_type: str,
) -> dict[str, Any]:
    """Save uploaded CSV file for processing.

    Args:
        file_content: CSV file content as string.
        filename: Original filename.
        operation_type: Type of operation (employee_create, employee_update, manager_update).

    Returns:
        Upload confirmation with file path.
    """
    try:
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{operation_type}_{timestamp}_{filename}"
        file_path = CSV_UPLOAD_DIR / safe_filename

        # Save file
        file_path.write_text(file_content)

        return {
            "success": True,
            "file_path": str(file_path),
            "filename": safe_filename,
            "message": f"CSV uploaded successfully: {safe_filename}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to upload CSV: {str(e)}"
        }


@tool
def parse_employee_csv(
    file_path: str,
) -> dict[str, Any]:
    """Parse and validate employee CSV file.

    Expected columns for employee creation:
    - first_name, last_name, mobile_number, email, employee_no, salary (optional)

    Expected columns for manager updates:
    - employee_id, new_manager_id

    Args:
        file_path: Path to the CSV file.

    Returns:
        Parsed records and validation errors.
    """
    try:
        # Read CSV
        df = pd.read_csv(file_path)

        # Basic validation
        if df.empty:
            return {
                "success": False,
                "error": "CSV file is empty"
            }

        if len(df) > 5000:
            return {
                "success": False,
                "error": f"CSV contains {len(df)} records. Maximum allowed is 5000."
            }

        # Convert to records
        records = df.to_dict('records')

        # Validation
        errors = []
        warnings = []

        # Detect operation type based on columns
        columns = set(df.columns)

        if "employee_id" in columns and "new_manager_id" in columns:
            operation_type = "manager_update"
            required_cols = ["employee_id", "new_manager_id"]
        elif "first_name" in columns and "last_name" in columns:
            operation_type = "employee_create"
            required_cols = ["first_name", "last_name", "mobile_number", "email", "employee_no"]
        elif "employee_id" in columns and any(col in columns for col in ["first_name", "email", "status"]):
            operation_type = "employee_update"
            required_cols = ["employee_id"]
        else:
            return {
                "success": False,
                "error": "Could not determine operation type from CSV columns"
            }

        # Check required columns
        missing_cols = set(required_cols) - columns
        if missing_cols:
            return {
                "success": False,
                "error": f"Missing required columns: {', '.join(missing_cols)}"
            }

        # Validate each record
        valid_records = []
        invalid_records = []

        for idx, record in enumerate(records, start=2):  # Start at 2 (header is row 1)
            record_errors = []

            if operation_type == "employee_create":
                # Validate mobile number format
                mobile = str(record.get("mobile_number", ""))
                if not mobile.startswith("27") or len(mobile) != 11:
                    record_errors.append(f"Invalid mobile format: {mobile}")

                # Check required fields
                for field in required_cols:
                    if pd.isna(record.get(field)) or record.get(field) == "":
                        record_errors.append(f"Missing {field}")

            elif operation_type == "manager_update":
                # Validate IDs are integers
                try:
                    int(record["employee_id"])
                    int(record["new_manager_id"])
                except (ValueError, KeyError):
                    record_errors.append("Invalid employee_id or new_manager_id")

            if record_errors:
                invalid_records.append({
                    "row": idx,
                    "record": record,
                    "errors": record_errors
                })
            else:
                valid_records.append(record)

        return {
            "success": True,
            "operation_type": operation_type,
            "total_records": len(records),
            "valid_records": valid_records,
            "valid_count": len(valid_records),
            "invalid_records": invalid_records,
            "invalid_count": len(invalid_records),
            "warnings": warnings
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error parsing CSV: {str(e)}"
        }


@tool
def save_processing_results(
    operation_id: str,
    results: dict[str, Any],
) -> dict[str, Any]:
    """Save processing results to CSV files.

    Creates two CSV files:
    - success.csv: Successfully processed records
    - errors.csv: Failed records with error messages

    Args:
        operation_id: Unique operation identifier.
        results: Processing results with successes and failures.

    Returns:
        Paths to result files.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save successful records
        if results.get("successes"):
            success_df = pd.DataFrame(results["successes"])
            success_path = CSV_RESULTS_DIR / f"{operation_id}_{timestamp}_success.csv"
            success_df.to_csv(success_path, index=False)
        else:
            success_path = None

        # Save failed records
        if results.get("failures"):
            failures_df = pd.DataFrame(results["failures"])
            errors_path = CSV_RESULTS_DIR / f"{operation_id}_{timestamp}_errors.csv"
            failures_df.to_csv(errors_path, index=False)
        else:
            errors_path = None

        # Save summary report
        summary_path = CSV_RESULTS_DIR / f"{operation_id}_{timestamp}_summary.txt"
        with open(summary_path, "w") as f:
            f.write(f"Bulk Operation Summary\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Operation ID: {operation_id}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Total Records: {results.get('total', 0)}\n")
            f.write(f"Successful: {len(results.get('successes', []))}\n")
            f.write(f"Failed: {len(results.get('failures', []))}\n")
            f.write(f"\nSuccess Rate: {results.get('success_rate', 0):.1f}%\n")

        return {
            "success": True,
            "success_file": str(success_path) if success_path else None,
            "errors_file": str(errors_path) if errors_path else None,
            "summary_file": str(summary_path),
            "message": f"Results saved to {CSV_RESULTS_DIR}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save results: {str(e)}"
        }
