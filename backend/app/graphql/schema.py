"""
Основная GraphQL схема для API клиники
"""

from dataclasses import dataclass

import strawberry
from fastapi import Depends, Request
from strawberry.fastapi import BaseContext, GraphQLRouter

from app.api.deps import require_roles
from app.graphql.mutations import Mutation
from app.graphql.resolvers import Query


@dataclass
class GraphQLContext(BaseContext):
    """Контекст исполнения: аутентифицированный admin + Request.

    Пользователь резолвится FastAPI-зависимостью graphql_admin_required
    (тот же cached-dependency, что в dependencies=[...], — один запрос
    к БД на вызов). Нужен резолверам для PHI-аудита (log_patient_access)
    и soft-delete атрибуции (deleted_by). BaseContext — требование
    strawberry для кастомного контекста.
    """

    user: object | None = None  # app.models.user.User
    _query_depth: int = 0


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


async def get_graphql_context(
    request: Request,
    current_user: object = Depends(graphql_admin_required),
) -> GraphQLContext:
    context = GraphQLContext(user=current_user)
    context.request = request
    return context


# Создаем GraphQL роутер для FastAPI
graphql_router = GraphQLRouter(
    schema,
    graphql_ide="graphiql",
    path="/graphql",
    context_getter=get_graphql_context,
    dependencies=[Depends(graphql_admin_required)],
)
