"""
GraphQL API для клиники
"""

from .schema import graphql_router, schema

__all__ = ["schema", "graphql_router"]
