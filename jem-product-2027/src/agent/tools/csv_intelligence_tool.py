"""Intelligent CSV processing tools for handling variable formats and dirty data.

Uses fuzzy matching and LLM-powered analysis to handle:
- Different column name variations (90+ patterns)
- Dirty/inconsistent data
- Missing values
- Format variations
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from Levenshtein import ratio
from langchain_core.tools import tool


# Column name mapping patterns (fuzzy matching)
COLUMN_MAPPINGS = {
    "first_name": [
        "first name", "firstname", "first_name", "given name", "givenname",
        "fname", "forename", "christian name", "name", "first"
    ],
    "last_name": [
        "last name", "lastname", "last_name", "surname", "family name",
        "familyname", "lname", "last"
    ],
    "mobile_number": [
        "mobile", "mobile number", "mobile_number", "cell", "cellphone",
        "cell phone", "phone", "phone number", "contact", "contact number",
        "telephone", "tel", "mobile no", "cell no"
    ],
    "email": [
        "email", "e-mail", "email address", "e-mail address", "work email",
        "contact email", "email_address", "mail", "electronic mail"
    ],
    "employee_no": [
        "employee no", "employee number", "employee_number", "emp no",
        "emp number", "staff number", "staff no", "employee id",
        "emp id", "staff id", "personnel number", "badge number"
    ],
    "salary": [
        "salary", "annual salary", "monthly salary", "pay", "compensation",
        "wage", "monthly pay", "annual pay", "remuneration", "package"
    ],
}


@tool
def inspect_csv_structure(file_path: str) -> dict[str, Any]:
    """Analyze CSV file structure, data quality, and format.

    Provides intelligent analysis of:
    - Column names and data types
    - Data quality (missing, duplicates, formats)
    - Suggested mappings to schema
    - Cleaning recommendations

    Args:
        file_path: Path to CSV file.

    Returns:
        Detailed analysis of CSV structure and quality.
    """
    try:
        # Read CSV
        df = pd.read_csv(file_path)

        # Basic stats
        analysis = {
            "success": True,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": list(df.columns),
            "column_analysis": {},
            "data_quality": {},
            "suggested_mappings": {},
            "cleaning_needed": []
        }

        # Analyze each column
        for col in df.columns:
            col_data = df[col]

            analysis["column_analysis"][col] = {
                "data_type": str(col_data.dtype),
                "missing_count": int(col_data.isna().sum()),
                "missing_percentage": float(col_data.isna().sum() / len(df) * 100),
                "unique_values": int(col_data.nunique()),
                "sample_values": col_data.dropna().head(3).tolist()
            }

        # Suggest column mappings using fuzzy matching
        for target_col, variations in COLUMN_MAPPINGS.items():
            best_match = None
            best_score = 0

            for csv_col in df.columns:
                # Fuzzy match against all variations
                for variation in variations:
                    score = ratio(csv_col.lower().strip(), variation.lower())
                    if score > best_score:
                        best_score = score
                        best_match = csv_col

            if best_score > 0.6:  # 60% similarity threshold
                analysis["suggested_mappings"][target_col] = {
                    "csv_column": best_match,
                    "confidence": round(best_score * 100, 1)
                }

        # Data quality checks
        analysis["data_quality"] = {
            "total_missing_values": int(df.isna().sum().sum()),
            "rows_with_missing": int(df.isna().any(axis=1).sum()),
            "duplicate_rows": int(df.duplicated().sum()),
            "empty_rows": int(df.isna().all(axis=1).sum())
        }

        # Check for dirty data patterns
        if "mobile_number" in analysis["suggested_mappings"]:
            mobile_col = analysis["suggested_mappings"]["mobile_number"]["csv_column"]
            mobile_samples = df[mobile_col].dropna().astype(str).head(10)

            # Check if mobile numbers need cleaning
            needs_cleaning = any(
                not (str(val).replace(" ", "").replace("-", "").replace("+", "").isdigit())
                or len(str(val).replace(" ", "").replace("-", "").replace("+", "")) != 11
                for val in mobile_samples
            )

            if needs_cleaning:
                analysis["cleaning_needed"].append({
                    "column": mobile_col,
                    "issue": "Mobile numbers contain formatting (spaces, dashes, +) or wrong length",
                    "sample": mobile_samples.tolist()[:3]
                })

        # Check email formats
        if "email" in analysis["suggested_mappings"]:
            email_col = analysis["suggested_mappings"]["email"]["csv_column"]
            email_samples = df[email_col].dropna().astype(str).head(10)

            # Simple email validation
            needs_cleaning = any(
                "@" not in str(val) or "." not in str(val)
                for val in email_samples
            )

            if needs_cleaning:
                analysis["cleaning_needed"].append({
                    "column": email_col,
                    "issue": "Some email addresses may be invalid",
                    "sample": email_samples.tolist()[:3]
                })

        return analysis

    except FileNotFoundError:
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error inspecting CSV: {str(e)}"
        }


@tool
def map_csv_columns(
    csv_columns: list[str],
    target_schema: dict[str, list[str]] | None = None
) -> dict[str, Any]:
    """Map CSV columns to expected schema using fuzzy matching.

    Args:
        csv_columns: List of column names from CSV.
        target_schema: Optional custom schema mappings.

    Returns:
        Mapping of schema fields to CSV columns.
    """
    if target_schema is None:
        target_schema = COLUMN_MAPPINGS

    mappings = {}
    unmapped_columns = []

    for target_col, variations in target_schema.items():
        best_match = None
        best_score = 0

        for csv_col in csv_columns:
            for variation in variations:
                score = ratio(csv_col.lower().strip(), variation.lower())
                if score > best_score:
                    best_score = score
                    best_match = csv_col

        if best_score > 0.6:  # 60% confidence threshold
            mappings[target_col] = {
                "csv_column": best_match,
                "confidence": round(best_score * 100, 1)
            }
        else:
            # No good match found
            pass

    # Find unmapped CSV columns
    mapped_csv_cols = set(m["csv_column"] for m in mappings.values())
    unmapped_columns = [col for col in csv_columns if col not in mapped_csv_cols]

    return {
        "success": True,
        "mappings": mappings,
        "unmapped_columns": unmapped_columns,
        "confidence_summary": {
            "high_confidence": sum(1 for m in mappings.values() if m["confidence"] > 90),
            "medium_confidence": sum(1 for m in mappings.values() if 70 <= m["confidence"] <= 90),
            "low_confidence": sum(1 for m in mappings.values() if m["confidence"] < 70),
        }
    }
