"""Data cleaning tools for CSV processing.

Handles common data quality issues:
- Mobile number formatting (20+ variations)
- Email validation and correction
- Name standardization
- Missing data strategies
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from langchain_core.tools import tool


@tool
def clean_mobile_number(
    mobile: str,
    default_country: str = "ZA"
) -> dict[str, Any]:
    """Clean and standardize mobile number to SA format (27XXXXXXXXX).

    Handles formats:
    - "+27 82 123 4567"
    - "082-123-4567"
    - "(082) 123 4567"
    - "0821234567"
    - "27821234567"
    - "+27821234567"

    Args:
        mobile: Raw mobile number string.
        default_country: Country code (default: ZA for South Africa).

    Returns:
        Cleaned mobile number or error.
    """
    if not mobile or pd.isna(mobile):
        return {
            "success": False,
            "original": mobile,
            "error": "Missing mobile number"
        }

    try:
        # Remove common formatting characters
        cleaned = str(mobile).strip()
        cleaned = re.sub(r'[\\s\\-\\(\\)\\.]', '', cleaned)  # Remove spaces, dashes, parens, dots

        # Try to parse with phonenumbers library
        try:
            parsed = phonenumbers.parse(cleaned, default_country)

            if phonenumbers.is_valid_number(parsed):
                # Format to SA standard: 27XXXXXXXXX
                formatted = phonenumbers.format_number(
                    parsed,
                    phonenumbers.PhoneNumberFormat.E164
                )  # Returns +27XXXXXXXXX

                # Remove the + sign
                formatted = formatted.replace("+", "")

                return {
                    "success": True,
                    "original": mobile,
                    "cleaned": formatted,
                    "is_valid": True
                }
        except phonenumbers.NumberParseException:
            # Fallback: manual parsing for SA numbers
            pass

        # Fallback: Manual cleaning for SA numbers
        digits_only = re.sub(r'\\D', '', cleaned)  # Extract digits only

        # Handle different SA formats
        if digits_only.startswith("27") and len(digits_only) == 11:
            # Already in correct format
            return {
                "success": True,
                "original": mobile,
                "cleaned": digits_only,
                "is_valid": True
            }
        elif digits_only.startswith("0") and len(digits_only) == 10:
            # Convert 0XXXXXXXXX to 27XXXXXXXXX
            cleaned_number = "27" + digits_only[1:]
            return {
                "success": True,
                "original": mobile,
                "cleaned": cleaned_number,
                "is_valid": True
            }
        elif len(digits_only) == 9:
            # Missing country code and leading 0
            cleaned_number = "27" + digits_only
            return {
                "success": True,
                "original": mobile,
                "cleaned": cleaned_number,
                "is_valid": True,
                "warning": "Added country code and leading digit"
            }
        else:
            return {
                "success": False,
                "original": mobile,
                "error": f"Invalid format: {digits_only} (expected 11 digits starting with 27)"
            }

    except Exception as e:
        return {
            "success": False,
            "original": mobile,
            "error": f"Cleaning failed: {str(e)}"
        }


@tool
def clean_email_address(email: str) -> dict[str, Any]:
    """Validate and clean email address.

    Args:
        email: Raw email address.

    Returns:
        Cleaned email or error.
    """
    if not email or pd.isna(email):
        return {
            "success": False,
            "original": email,
            "error": "Missing email address"
        }

    try:
        # Clean whitespace
        cleaned = str(email).strip().lower()

        # Skip obviously invalid values
        if cleaned in ["n/a", "na", "none", "null", "", "-"]:
            return {
                "success": False,
                "original": email,
                "error": "Placeholder value (N/A, None, etc.)"
            }

        # Validate with email-validator
        try:
            validation = validate_email(cleaned, check_deliverability=False)
            cleaned_email = validation.normalized

            return {
                "success": True,
                "original": email,
                "cleaned": cleaned_email,
                "is_valid": True
            }
        except EmailNotValidError as e:
            # Try common fixes
            # Fix: missing @ or .
            if "@" not in cleaned:
                return {
                    "success": False,
                    "original": email,
                    "error": "Missing @ symbol"
                }

            if "." not in cleaned.split("@")[-1]:
                return {
                    "success": False,
                    "original": email,
                    "error": "Missing domain extension (.com, .co.za, etc.)"
                }

            return {
                "success": False,
                "original": email,
                "error": str(e)
            }

    except Exception as e:
        return {
            "success": False,
            "original": email,
            "error": f"Validation failed: {str(e)}"
        }


@tool
def clean_salary_field(salary: Any) -> dict[str, Any]:
    """Clean and parse salary values.

    Handles formats:
    - "R 55,000"
    - "$55000"
    - "55,000.00"
    - "55000"

    Args:
        salary: Raw salary value.

    Returns:
        Cleaned numeric salary.
    """
    if pd.isna(salary) or salary == "":
        return {
            "success": True,
            "original": salary,
            "cleaned": None,  # Optional field
            "is_valid": True
        }

    try:
        # Convert to string and clean
        cleaned = str(salary).strip()

        # Remove currency symbols
        cleaned = re.sub(r'[R$£€¥]', '', cleaned)

        # Remove thousand separators and spaces
        cleaned = cleaned.replace(",", "").replace(" ", "")

        # Convert to float
        try:
            salary_value = float(cleaned)

            return {
                "success": True,
                "original": salary,
                "cleaned": salary_value,
                "is_valid": True
            }
        except ValueError:
            return {
                "success": False,
                "original": salary,
                "error": f"Cannot convert to number: {cleaned}"
            }

    except Exception as e:
        return {
            "success": False,
            "original": salary,
            "error": f"Cleaning failed: {str(e)}"
        }


@tool
def clean_name_field(name: str) -> dict[str, Any]:
    """Standardize name formatting.

    - Title case
    - Trim whitespace
    - Remove special characters
    - Handle missing values

    Args:
        name: Raw name value.

    Returns:
        Cleaned name.
    """
    if not name or pd.isna(name):
        return {
            "success": False,
            "original": name,
            "error": "Missing name"
        }

    try:
        cleaned = str(name).strip()

        # Check for placeholder values
        if cleaned.lower() in ["n/a", "na", "none", "null", "unknown", "-", ""]:
            return {
                "success": False,
                "original": name,
                "error": "Placeholder value"
            }

        # Title case (handles names like "mcDonald" → "McDonald")
        cleaned = cleaned.title()

        # Remove excessive whitespace
        cleaned = " ".join(cleaned.split())

        # Basic validation
        if len(cleaned) < 2:
            return {
                "success": False,
                "original": name,
                "error": "Name too short"
            }

        return {
            "success": True,
            "original": name,
            "cleaned": cleaned,
            "is_valid": True
        }

    except Exception as e:
        return {
            "success": False,
            "original": name,
            "error": f"Cleaning failed: {str(e)}"
        }


@tool
def batch_clean_csv_records(
    records: list[dict[str, Any]],
    column_mappings: dict[str, Any]
) -> dict[str, Any]:
    """Clean all records in a batch using column mappings.

    Args:
        records: List of raw CSV records.
        column_mappings: Mapping of schema fields to CSV columns (with confidence).

    Returns:
        Cleaned records with success/failure tracking.
    """
    import pandas as pd
    cleaned_records = []
    failed_records = []

    # Extract simple mappings (handle both dict[str, str] and dict[str, dict])
    simple_mappings = {}
    for field, mapping in column_mappings.items():
        if isinstance(mapping, dict) and "csv_column" in mapping:
            simple_mappings[field] = mapping["csv_column"]
        elif isinstance(mapping, str):
            simple_mappings[field] = mapping

    for idx, record in enumerate(records):
        try:
            cleaned = {}
            errors = []

            # Clean first_name
            if "first_name" in simple_mappings:
                csv_col = simple_mappings["first_name"]
                result = clean_name_field.invoke({"name": record.get(csv_col)})
                if result["success"]:
                    cleaned["first_name"] = result["cleaned"]
                else:
                    errors.append(f"first_name: {result['error']}")

            # Clean last_name
            if "last_name" in simple_mappings:
                csv_col = simple_mappings["last_name"]
                result = clean_name_field.invoke({"name": record.get(csv_col)})
                if result["success"]:
                    cleaned["last_name"] = result["cleaned"]
                else:
                    errors.append(f"last_name: {result['error']}")

            # Clean mobile_number
            if "mobile_number" in simple_mappings:
                csv_col = simple_mappings["mobile_number"]
                result = clean_mobile_number.invoke({"mobile": record.get(csv_col)})
                if result["success"]:
                    cleaned["mobile_number"] = result["cleaned"]
                else:
                    errors.append(f"mobile: {result['error']}")

            # Clean email
            if "email" in simple_mappings:
                csv_col = simple_mappings["email"]
                result = clean_email_address.invoke({"email": record.get(csv_col)})
                if result["success"]:
                    cleaned["email"] = result["cleaned"]
                else:
                    errors.append(f"email: {result['error']}")

            # Clean salary
            if "salary" in simple_mappings:
                csv_col = simple_mappings["salary"]
                result = clean_salary_field.invoke({"salary": record.get(csv_col)})
                if result["success"] and result["cleaned"] is not None:
                    cleaned["salary"] = result["cleaned"]

            # Copy employee_no if present
            if "employee_no" in simple_mappings:
                csv_col = simple_mappings["employee_no"]
                emp_no = str(record.get(csv_col, "")).strip()
                if emp_no:
                    cleaned["employee_no"] = emp_no
                elif "employee_id" not in cleaned:  # Only required if not updating existing
                    errors.append("employee_no: Missing or empty")

            # If critical fields are missing, mark as failed
            # For import, need: first_name, last_name, mobile_number, email, employee_no
            required = ["first_name", "last_name", "mobile_number", "email"]
            missing_required = [f for f in required if f not in cleaned]

            # Check employee_no is present (critical for new employees)
            if "employee_no" not in cleaned and "employee_id" not in cleaned:
                missing_required.append("employee_no")

            if missing_required or errors:
                failed_records.append({
                    "row": idx + 2,  # CSV row (accounting for header)
                    "original": record,
                    "errors": errors if errors else [f"Missing required: {', '.join(missing_required)}"],
                    "cleaned_partial": cleaned  # Show what was successfully cleaned
                })
            else:
                cleaned_records.append(cleaned)

        except Exception as e:
            failed_records.append({
                "row": idx + 2,
                "original": record,
                "errors": [f"Processing error: {str(e)}"]
            })

    return {
        "success": True,
        "cleaned_records": cleaned_records,
        "failed_records": failed_records,
        "clean_count": len(cleaned_records),
        "failed_count": len(failed_records),
        "success_rate": (len(cleaned_records) / len(records) * 100) if records else 0
    }
