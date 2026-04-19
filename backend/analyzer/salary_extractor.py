"""Salary extraction from JD text + H-1B LCA median fallback."""
import re
import logging

logger = logging.getLogger("jobnavigator.salary")


def extract_salary(description: str, h1b_median_salary: int = None) -> dict:
    """Extract salary range from job description text.
    Falls back to H-1B LCA median if no salary found in text.
    """
    if not description:
        if h1b_median_salary:
            return {
                "salary_min": h1b_median_salary,
                "salary_max": h1b_median_salary,
                "salary_source": "lca_estimate",
            }
        return {"salary_min": None, "salary_max": None, "salary_source": "unknown"}

    # Cap input size before any regex runs. Matches the scraper's existing 30K truncation.
    # Bounds polynomial-time HTML stripper + salary regex to defend against pathological input.
    description = description[:30_000]

    # Strip HTML tags and decode entities before parsing
    if "<" in description and ">" in description:
        import html as _html
        description = _html.unescape(re.sub(r'<[^>]+>', ' ', description))

    # Pattern 1: $XXX,XXX - $XXX,XXX (full dollar amounts with range)
    # Handles: $140,000 USD - $210,000 USD, USD$150,000 - USD$200,000,
    #          173,900.00 - 235,200.00 USD, $122,550.00-$201,000.00
    match = re.search(
        r'(?:USD\s*)?\$\s*(\d{1,3}(?:,\d{3})*)(?:\.\d{1,2})?\s*(?:USD|per\s*year|annually|/\s*yr|/\s*year|a\s*year)?\s*(?:[-–—/]+|(?:and\s+)?up\s+to|to|and)\s*(?:USD\s*)?\$?\s*(\d{1,3}(?:,\d{3})*)(?:\.\d{1,2})?',
        description
    )
    if not match:
        # Bare numbers with USD: 173,900.00 - 235,200.00 USD
        match = re.search(
            r'(\d{1,3}(?:,\d{3})*)(?:\.\d{1,2})?\s*(?:USD\s*)?(?:[-–—/]+|(?:and\s+)?up\s+to|to)\s*(\d{1,3}(?:,\d{3})*)(?:\.\d{1,2})?\s*USD',
            description
        )
    if match:
        low = int(match.group(1).replace(",", ""))
        high = int(match.group(2).replace(",", ""))
        return {"salary_min": low, "salary_max": high, "salary_source": "posting"}

    # Pattern 2: $XXXk - $XXXk (k notation range)
    match = re.search(
        r'\$\s*(\d{2,3})\s*[kK]\s*(?:[-–—/]+|(?:and\s+)?up\s+to|to)\s*\$\s*(\d{2,3})\s*[kK]',
        description
    )
    if match:
        low = int(match.group(1)) * 1000
        high = int(match.group(2)) * 1000
        return {"salary_min": low, "salary_max": high, "salary_source": "posting"}

    # Pattern 3: $XXX,XXX per year / annually (single amount)
    match = re.search(
        r'\$\s*(\d{1,3}(?:,\d{3})*)(?:\.\d{1,2})?\s*(?:per\s*year|annually|/\s*yr|/\s*year|a\s*year)',
        description, re.IGNORECASE
    )
    if match:
        val = int(match.group(1).replace(",", ""))
        return {"salary_min": val, "salary_max": val, "salary_source": "posting"}

    # Pattern 4: $XXXk (single k notation)
    match = re.search(r'\$\s*(\d{2,3})\s*[kK]', description)
    if match:
        val = int(match.group(1)) * 1000
        return {"salary_min": val, "salary_max": val, "salary_source": "posting"}

    # Pattern 5: bare range like $120,000
    match = re.search(r'\$\s*(\d{3},\d{3})(?:\.\d{1,2})?', description)
    if match:
        val = int(match.group(1).replace(",", ""))
        if val >= 30000:  # Sanity check it's an annual salary
            return {"salary_min": val, "salary_max": val, "salary_source": "posting"}

    # Fallback to LCA median
    if h1b_median_salary:
        return {
            "salary_min": h1b_median_salary,
            "salary_max": h1b_median_salary,
            "salary_source": "lca_estimate",
        }

    return {"salary_min": None, "salary_max": None, "salary_source": "unknown"}


def apply_salary_to_job(job, company_h1b_median: int = None) -> None:
    """Extract salary from job description and update job fields.
    Only updates if no salary already set from scraper.
    """
    if job.salary_min and job.salary_source == "posting":
        return  # Already have salary from scraper

    result = extract_salary(job.description or "", company_h1b_median)
    job.salary_min = result["salary_min"]
    job.salary_max = result["salary_max"]
    job.salary_source = result["salary_source"]
