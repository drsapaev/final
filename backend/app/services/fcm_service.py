"""
Firebase Cloud Messaging (FCM) сервис для push-уведомлений
"""
import json
import logging
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)

class FCMService:
    """Сервис для отправки push-уведомлений через FCM"""
    
    def __init__(self):
        self.app = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Инициализация Firebase Admin SDK"""
        try:
            # Проверяем, есть ли Firebase в requirements
            try:
                from firebase_admin import messaging, credentials, initialize_app
                from firebase_admin.exceptions import FirebaseError
                
                # Проверяем, есть ли уже инициализированное приложение
                if not messaging._get_app():
                    # Используем переменные окружения для конфигурации
                    firebase_config = {
                        "type": "service_account",
                        "project_id": os.getenv("FIREBASE_PROJECT_ID", "clinic-mobile-app"),
                        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID", ""),
                        "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
                        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL", ""),
                        "client_id": os.getenv("FIREBASE_CLIENT_ID", ""),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL", "")
                    }
                    
                    # Создаем credentials объект
                    cred = credentials.Certificate(firebase_config)
                    
                    # Инициализируем приложение
                    self.app = initialize_app(cred, name="clinic-fcm")
                    logger.info("Firebase Admin SDK инициализирован успешно")
                else:
                    self.app = messaging._get_app()
                    logger.info("Firebase Admin SDK уже инициализирован")
                    
            except ImportError:
                logger.warning("Firebase Admin SDK не установлен. Используется режим эмуляции.")
                self.app = None
                
        except Exception as e:
            logger.error(f"Ошибка инициализации Firebase: {e}")
            self.app = None
    
    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """Отправка уведомления на одно устройство"""
        try:
            if not self.app:
                # Режим эмуляции - логируем уведомление
                logger.info(f"[ЭМУЛЯЦИЯ] Push уведомление: {title} - {body} -> {device_token}")
                logger.info(f"[ЭМУЛЯЦИЯ] Данные: {data}")
                return True
            
            # Реальная отправка через Firebase
            from firebase_admin import messaging
            from firebase_admin.exceptions import FirebaseError
            
            # Создаем сообщение
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                token=device_token
            )
            
            # Отправляем сообщение
            response = messaging.send(message, app=self.app)
            logger.info(f"Уведомление отправлено успешно: {response}")
            return True
            
        except ImportError:
            # Firebase не установлен - эмулируем
            logger.info(f"[ЭМУЛЯЦИЯ] Push уведомление: {title} - {body} -> {device_token}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
            return False
    
    async def send_multicast_notification(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> Dict[str, int]:
        """Отправка уведомления на несколько устройств"""
        try:
            if not self.app:
                # Режим эмуляции
                logger.info(f"[ЭМУЛЯЦИЯ] Multicast уведомление: {title} - {body} -> {len(device_tokens)} устройств")
                return {"success": len(device_tokens), "failure": 0}
            
            # Реальная отправка через Firebase
            from firebase_admin import messaging
            from firebase_admin.exceptions import FirebaseError
            
            # Создаем multicast сообщение
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                tokens=device_tokens
            )
            
            # Отправляем сообщение
            response = messaging.send_multicast(message, app=self.app)
            
            logger.info(f"Multicast уведомление отправлено: {response.success_count} успешно, {response.failure_count} неудачно")
            
            return {
                "success": response.success_count,
                "failure": response.failure_count
            }
            
        except ImportError:
            # Firebase не установлен - эмулируем
            logger.info(f"[ЭМУЛЯЦИЯ] Multicast уведомление: {title} - {body} -> {len(device_tokens)} устройств")
            return {"success": len(device_tokens), "failure": 0}
        except Exception as e:
            logger.error(f"Ошибка при отправке multicast уведомления: {e}")
            return {"success": 0, "failure": len(device_tokens)}
    
    async def send_topic_notification(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """Отправка уведомления на тему (topic)"""
        try:
            if not self.app:
                # Режим эмуляции
                logger.info(f"[ЭМУЛЯЦИЯ] Topic уведомление: {title} - {body} -> {topic}")
                return True
            
            # Реальная отправка через Firebase
            from firebase_admin import messaging
            from firebase_admin.exceptions import FirebaseError
            
            # Создаем сообщение для темы
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                topic=topic
            )
            
            # Отправляем сообщение
            response = messaging.send(message, app=self.app)
            logger.info(f"Topic уведомление отправлено успешно: {response}")
            return True
            
        except ImportError:
            # Firebase не установлен - эмулируем
            logger.info(f"[ЭМУЛЯЦИЯ] Topic уведомление: {title} - {body} -> {topic}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке topic уведомления: {e}")
            return False

# Глобальный экземпляр сервиса
fcm_service = FCMService()

async def get_fcm_service() -> FCMService:
    """Получение экземпляра FCM сервиса"""
    return fcm_service
