"""
Основная GraphQL схема для API клиники
"""

import strawberry
from strawberry.fastapi import GraphQLRouter

from app.graphql.mutations import Mutation
from app.graphql.resolvers import Query

# Создаем GraphQL схему
schema = strawberry.Schema(query=Query, mutation=Mutation)

# Создаем GraphQL роутер для FastAPI
graphql_router = GraphQLRouter(
    schema, graphiql=True, path="/graphql"  # Включаем GraphiQL интерфейс для разработки
)
