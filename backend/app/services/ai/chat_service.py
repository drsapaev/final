"""
AI Chat Service - Управление чат-сессиями и сообщениями.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.ai_chat import AIChatSession, AIChatMessage, AIChatFeedback
from app.services.ai import get_ai_gateway, AITaskType

logger = logging.getLogger(__name__)


class AIChatService:
    """
    Сервис для управления AI чатом.
    
    Функции:
    - Создание/получение сессий
    - Сохранение сообщений
    - Генерация ответов через AI Gateway
    - Получение истории
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._gateway = get_ai_gateway()
    
    async def get_or_create_session(
        self,
        user_id: int,
        session_id: Optional[int] = None,
        context_type: Optional[str] = None,
        context_id: Optional[int] = None,
        specialty: Optional[str] = None
    ) -> AIChatSession:
        """
        Получить существующую или создать новую сессию.
        """
        if session_id:
            session = self.db.query(AIChatSession).filter(
                AIChatSession.id == session_id,
                AIChatSession.user_id == user_id,
                AIChatSession.is_active == True
            ).first()
            
            if session:
                return session
        
        # Создаем новую сессию
        session = AIChatSession(
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
            specialty=specialty
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"Created new chat session {session.id} for user {user_id}")
        return session
    
    async def send_message(
        self,
        session_id: int,
        user_id: int,
        content: str,
        include_history: bool = True,
        max_history: int = 10
    ) -> AIChatMessage:
        """
        Отправить сообщение и получить ответ AI.
        
        Args:
            session_id: ID сессии
            user_id: ID пользователя
            content: Текст сообщения
            include_history: Включить историю в контекст
            max_history: Максимум сообщений в истории
            
        Returns:
            AIChatMessage с ответом AI
        """
        # Проверяем сессию
        session = self.db.query(AIChatSession).filter(
            AIChatSession.id == session_id,
            AIChatSession.user_id == user_id
        ).first()
        
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")
        
        # Сохраняем user message
        user_message = AIChatMessage(
            session_id=session_id,
            role="user",
            content=content
        )
        self.db.add(user_message)
        self.db.commit()
        
        # Обновляем title сессии из первого сообщения
        if not session.title:
            session.title = content[:100] if len(content) <= 100 else content[:97] + "..."
            self.db.commit()
        
        # Получаем историю для контекста
        history = []
        if include_history:
            history = await self.get_history(session_id, limit=max_history)
        
        # Формируем payload
        payload = {
            "message": content,
            "history": [
                {"role": msg.role, "content": msg.content}
                for msg in history[:-1]  # Исключаем текущее сообщение
            ],
            "context_type": session.context_type,
            "specialty": session.specialty
        }
        
        # Получаем ответ от AI
        start_time = datetime.utcnow()
        
        try:
            response = await self._gateway.execute(
                task_type=AITaskType.CHAT_MESSAGE,
                payload=payload,
                user_id=user_id,
                specialty=session.specialty
            )
            
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Формируем контент ответа
            if response.status == "success":
                ai_content = response.data.get("content", str(response.data))
            else:
                ai_content = f"Ошибка: {response.error or 'Unknown error'}"
            
            # Добавляем disclaimer
            if response.status == "success":
                ai_content += f"\n\n---\n_{response.disclaimer}_"
            
            # Сохраняем AI response
            ai_message = AIChatMessage(
                session_id=session_id,
                role="assistant",
                content=ai_content,
                provider=response.provider,
                model=response.model,
                tokens_used=response.tokens_used,
                latency_ms=latency_ms,
                is_error=response.status == "error",
                was_cached=response.cached
            )
            
            self.db.add(ai_message)
            self.db.commit()
            self.db.refresh(ai_message)
            
            return ai_message
            
        except Exception as e:
            logger.exception(f"Chat error in session {session_id}: {e}")
            
            # Сохраняем error response
            error_message = AIChatMessage(
                session_id=session_id,
                role="assistant",
                content=f"Произошла ошибка: {str(e)}",
                is_error=True
            )
            
            self.db.add(error_message)
            self.db.commit()
            self.db.refresh(error_message)
            
            return error_message
    
    async def get_history(
        self,
        session_id: int,
        limit: int = 50,
        before_id: Optional[int] = None
    ) -> List[AIChatMessage]:
        """
        Получить историю сообщений сессии.
        """
        query = self.db.query(AIChatMessage).filter(
            AIChatMessage.session_id == session_id
        )
        
        if before_id:
            query = query.filter(AIChatMessage.id < before_id)
        
        messages = query.order_by(
            AIChatMessage.created_at.desc()
        ).limit(limit).all()
        
        # Возвращаем в хронологическом порядке
        return list(reversed(messages))
    
    async def get_user_sessions(
        self,
        user_id: int,
        limit: int = 20,
        include_inactive: bool = False
    ) -> List[AIChatSession]:
        """
        Получить список сессий пользователя.
        """
        query = self.db.query(AIChatSession).filter(
            AIChatSession.user_id == user_id
        )
        
        if not include_inactive:
            query = query.filter(AIChatSession.is_active == True)
        
        return query.order_by(
            AIChatSession.updated_at.desc()
        ).limit(limit).all()
    
    async def add_feedback(
        self,
        message_id: int,
        user_id: int,
        feedback_type: str,
        comment: Optional[str] = None,
        correction: Optional[str] = None
    ) -> AIChatFeedback:
        """
        Добавить feedback на сообщение AI.
        """
        # Проверяем что сообщение существует и это AI ответ
        message = self.db.query(AIChatMessage).filter(
            AIChatMessage.id == message_id,
            AIChatMessage.role == "assistant"
        ).first()
        
        if not message:
            raise ValueError(f"AI message {message_id} not found")
        
        feedback = AIChatFeedback(
            message_id=message_id,
            user_id=user_id,
            feedback_type=feedback_type,
            comment=comment,
            correction=correction
        )
        
        self.db.add(feedback)
        
        # Также обновляем rating в сообщении
        if feedback_type == "helpful":
            message.user_rating = 5
        elif feedback_type == "not_helpful":
            message.user_rating = 2
        elif feedback_type in ("incorrect", "inappropriate"):
            message.user_rating = 1
        
        if comment:
            message.user_feedback = comment
        
        self.db.commit()
        self.db.refresh(feedback)
        
        return feedback
    
    async def close_session(self, session_id: int, user_id: int) -> bool:
        """
        Закрыть (архивировать) сессию.
        """
        session = self.db.query(AIChatSession).filter(
            AIChatSession.id == session_id,
            AIChatSession.user_id == user_id
        ).first()
        
        if not session:
            return False
        
        session.is_active = False
        self.db.commit()
        
        return True
    
    async def delete_session(self, session_id: int, user_id: int) -> bool:
        """
        Удалить сессию и все сообщения.
        """
        session = self.db.query(AIChatSession).filter(
            AIChatSession.id == session_id,
            AIChatSession.user_id == user_id
        ).first()
        
        if not session:
            return False
        
        self.db.delete(session)  # Cascade удалит messages
        self.db.commit()
        
        return True


def get_chat_service(db: Session) -> AIChatService:
    """Factory function для DI"""
    return AIChatService(db)
