"""GraphQL query depth limiting to prevent DoS."""
import logging

logger = logging.getLogger(__name__)
MAX_QUERY_DEPTH = 10


def validate_query_depth(query: str, max_depth: int = MAX_QUERY_DEPTH) -> bool:
    """Validate that a GraphQL query does not exceed max depth."""
    depth = 0
    max_found = 0
    for char in query:
        if char == "{":
            depth += 1
            max_found = max(max_found, depth)
        elif char == "}":
            depth -= 1
    if max_found > max_depth:
        logger.warning("GraphQL query rejected: depth %d exceeds max %d", max_found, max_depth)
        return False
    return True
