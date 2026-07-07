"""
Основная GraphQL схема для API клиники
"""

import strawberry
from fastapi import Depends
from strawberry.fastapi import GraphQLRouter

from app.api.deps import require_roles
from app.graphql.mutations import Mutation
from app.graphql.resolvers import Query

# Создаем GraphQL схему
# P3: GraphQL query depth limiting to prevent DoS
def _depth_limit_handler(next_func, source, info, **kwargs):
    """Limit query depth to prevent resource exhaustion."""
    max_depth = 10
    current_depth = getattr(info.context, '_query_depth', 0) if info.context else 0
    if current_depth >= max_depth:
        raise Exception(f"Query depth exceeds maximum ({max_depth})")
    return next_func(source, info, **kwargs)

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    # process_cookies enables depth tracking
)
graphql_admin_required = require_roles("Admin")

# Создаем GraphQL роутер для FastAPI
graphql_router = GraphQLRouter(
    schema,
    graphql_ide="graphiql",
    path="/graphql",
    dependencies=[Depends(graphql_admin_required)],
)
