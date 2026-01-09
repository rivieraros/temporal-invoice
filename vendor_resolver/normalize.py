"""Name Normalization Utilities.

This module provides functions to normalize vendor/feedlot names
for consistent matching. The normalization process:
1. Converts to uppercase
2. Removes common suffixes (INC, LLC, DBA, etc.)
3. Removes punctuation
4. Collapses whitespace
5. Tokenizes for fuzzy matching

Examples:
    "BOVINA FEEDERS INC. DBA BF2" → "BOVINA FEEDERS BF2"
    "Mesquite Cattle Feeders, LLC" → "MESQUITE CATTLE FEEDERS"
    "Sugar Mountain Livestock"     → "SUGAR MOUNTAIN LIVESTOCK"
"""

import re
from typing import List, Set, Tuple


# Common business suffixes to remove during normalization
BUSINESS_SUFFIXES = {
    # Legal entity types
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY",
    "LLC", "L.L.C.", "LTD", "LIMITED", "LP", "L.P.", "LLP", "L.L.P.",
    "PC", "P.C.", "PA", "P.A.", "PLLC", "P.L.L.C.",
    
    # Doing business as
    "DBA", "D.B.A.", "D/B/A", "AKA", "A.K.A.",
    
    # Other common suffixes
    "AND", "&", "THE",
}

# Words that are often noise in vendor names
NOISE_WORDS = {
    "THE", "AND", "OF", "FOR", "A", "AN",
}

# State abbreviations for address matching
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU",
}


def normalize_vendor_name(name: str) -> str:
    """Normalize a vendor/feedlot name for matching.
    
    The normalization process:
    1. Convert to uppercase
    2. Remove business suffixes (INC, LLC, DBA, etc.)
    3. Remove punctuation
    4. Collapse whitespace
    
    Args:
        name: Raw vendor/feedlot name from extraction
        
    Returns:
        Normalized name string
        
    Examples:
        >>> normalize_vendor_name("BOVINA FEEDERS INC. DBA BF2")
        'BOVINA FEEDERS BF2'
        >>> normalize_vendor_name("Mesquite Cattle Feeders, LLC")
        'MESQUITE CATTLE FEEDERS'
    """
    if not name:
        return ""
    
    # Step 1: Uppercase
    text = name.upper().strip()
    
    # Step 2: Remove punctuation (except hyphens in names)
    # Replace common punctuation with spaces
    text = re.sub(r'[.,;:!?()"\'\[\]{}]', ' ', text)
    
    # Step 3: Tokenize and remove suffixes
    tokens = text.split()
    filtered_tokens = []
    
    for token in tokens:
        # Clean the token
        clean_token = token.strip()
        
        # Skip business suffixes
        if clean_token in BUSINESS_SUFFIXES:
            continue
        
        # Skip standalone punctuation
        if not clean_token or clean_token in ("&", "-", "/"):
            continue
        
        filtered_tokens.append(clean_token)
    
    # Step 4: Join and collapse whitespace
    result = " ".join(filtered_tokens)
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result


def tokenize_name(name: str) -> List[str]:
    """Tokenize a name into significant words for matching.
    
    Removes noise words and returns unique significant tokens.
    
    Args:
        name: Name string (should be normalized first)
        
    Returns:
        List of significant tokens
        
    Examples:
        >>> tokenize_name("BOVINA FEEDERS BF2")
        ['BOVINA', 'FEEDERS', 'BF2']
    """
    if not name:
        return []
    
    # Split and filter
    tokens = name.upper().split()
    
    # Remove noise words and short tokens
    significant = [
        t for t in tokens 
        if t not in NOISE_WORDS and len(t) > 1
    ]
    
    # Return unique tokens preserving order
    seen = set()
    result = []
    for t in significant:
        if t not in seen:
            seen.add(t)
            result.append(t)
    
    return result


def calculate_token_similarity(tokens1: List[str], tokens2: List[str]) -> float:
    """Calculate similarity between two token lists using Jaccard + ordering.
    
    Combines:
    - Jaccard similarity (set overlap)
    - Order bonus (if first tokens match)
    - Substring matching (partial token matches)
    
    Args:
        tokens1: First token list
        tokens2: Second token list
        
    Returns:
        Similarity score from 0.0 to 1.0
    """
    if not tokens1 or not tokens2:
        return 0.0
    
    set1 = set(tokens1)
    set2 = set(tokens2)
    
    # Exact token matches
    intersection = set1 & set2
    union = set1 | set2
    
    if not union:
        return 0.0
    
    # Base Jaccard similarity
    jaccard = len(intersection) / len(union)
    
    # Bonus for matching first token (company name usually starts with key word)
    first_match_bonus = 0.0
    if tokens1 and tokens2 and tokens1[0] == tokens2[0]:
        first_match_bonus = 0.15
    
    # Partial token matching (for abbreviations)
    partial_matches = 0
    for t1 in set1 - intersection:
        for t2 in set2 - intersection:
            # Check if one is substring of other (min 3 chars)
            if len(t1) >= 3 and len(t2) >= 3:
                if t1 in t2 or t2 in t1:
                    partial_matches += 0.5
                    break
    
    partial_bonus = min(0.2, partial_matches * 0.1)
    
    # Combine scores (capped at 1.0)
    return min(1.0, jaccard + first_match_bonus + partial_bonus)


def calculate_string_similarity(s1: str, s2: str) -> float:
    """Calculate similarity between two strings using character-level comparison.
    
    Uses a simplified Levenshtein-like approach optimized for vendor names.
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Similarity score from 0.0 to 1.0
    """
    if not s1 or not s2:
        return 0.0
    
    s1 = s1.upper()
    s2 = s2.upper()
    
    if s1 == s2:
        return 1.0
    
    # Simple containment check
    if s1 in s2 or s2 in s1:
        shorter = min(len(s1), len(s2))
        longer = max(len(s1), len(s2))
        return shorter / longer
    
    # Character-level overlap
    chars1 = set(s1.replace(" ", ""))
    chars2 = set(s2.replace(" ", ""))
    
    if not chars1 or not chars2:
        return 0.0
    
    overlap = len(chars1 & chars2)
    total = len(chars1 | chars2)
    
    return overlap / total


def extract_address_components(
    address_line1: str = None,
    city: str = None,
    state: str = None,
    postal_code: str = None,
) -> Tuple[str, str, str]:
    """Extract and normalize address components.
    
    Args:
        address_line1: Street address
        city: City name
        state: State code
        postal_code: ZIP/postal code
        
    Returns:
        Tuple of (normalized_street, normalized_city, state_code)
    """
    # Normalize street
    street = ""
    if address_line1:
        street = address_line1.upper().strip()
        street = re.sub(r'[.,#]', '', street)
        street = re.sub(r'\s+', ' ', street)
    
    # Normalize city
    city_norm = ""
    if city:
        city_norm = city.upper().strip()
    
    # Normalize state
    state_code = ""
    if state:
        state_upper = state.upper().strip()
        if state_upper in US_STATES:
            state_code = state_upper
        elif len(state_upper) > 2:
            # Try to match full state name
            state_abbrevs = {
                "TEXAS": "TX", "CALIFORNIA": "CA", "WASHINGTON": "WA",
                "NEW YORK": "NY", "FLORIDA": "FL", "ARIZONA": "AZ",
                # Add more as needed
            }
            state_code = state_abbrevs.get(state_upper, state_upper[:2])
    
    return street, city_norm, state_code


def calculate_address_similarity(
    addr1: Tuple[str, str, str],
    addr2: Tuple[str, str, str],
) -> float:
    """Calculate similarity between two addresses.
    
    Args:
        addr1: (street, city, state) tuple
        addr2: (street, city, state) tuple
        
    Returns:
        Similarity score from 0.0 to 1.0
    """
    street1, city1, state1 = addr1
    street2, city2, state2 = addr2
    
    score = 0.0
    components = 0
    
    # State match (most important)
    if state1 and state2:
        components += 1
        if state1 == state2:
            score += 0.4
    
    # City match
    if city1 and city2:
        components += 1
        if city1 == city2:
            score += 0.35
        elif city1 in city2 or city2 in city1:
            score += 0.2
    
    # Street similarity (least reliable)
    if street1 and street2:
        components += 1
        street_sim = calculate_string_similarity(street1, street2)
        score += street_sim * 0.25
    
    if components == 0:
        return 0.0
    
    # Normalize by number of components we could compare
    return score


def is_likely_same_vendor(
    name1: str,
    name2: str,
    state1: str = None,
    state2: str = None,
) -> Tuple[bool, float, str]:
    """Quick check if two names likely refer to the same vendor.
    
    Args:
        name1: First vendor name
        name2: Second vendor name
        state1: Optional state of first vendor
        state2: Optional state of second vendor
        
    Returns:
        Tuple of (is_match, confidence, reason)
    """
    norm1 = normalize_vendor_name(name1)
    norm2 = normalize_vendor_name(name2)
    
    # Exact match after normalization
    if norm1 == norm2:
        return True, 1.0, "Exact normalized match"
    
    # Token similarity
    tokens1 = tokenize_name(norm1)
    tokens2 = tokenize_name(norm2)
    
    token_sim = calculate_token_similarity(tokens1, tokens2)
    
    # State mismatch is a strong negative signal
    if state1 and state2:
        s1 = state1.upper().strip()
        s2 = state2.upper().strip()
        if s1 in US_STATES and s2 in US_STATES and s1 != s2:
            return False, token_sim * 0.5, "State mismatch"
    
    if token_sim >= 0.85:
        return True, token_sim, f"High token similarity ({token_sim:.2f})"
    elif token_sim >= 0.6:
        return False, token_sim, f"Moderate similarity ({token_sim:.2f}) - needs confirmation"
    else:
        return False, token_sim, f"Low similarity ({token_sim:.2f})"
