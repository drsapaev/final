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
schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_admin_required = require_roles("Admin")

# Создаем GraphQL роутер для FastAPI
graphql_router = GraphQLRouter(
    schema,
    graphql_ide="graphiql",
    path="/graphql",
    dependencies=[Depends(graphql_admin_required)],
)
