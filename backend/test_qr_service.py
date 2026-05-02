"""
Тестирование QR сервиса
"""
from app.db.session import SessionLocal
from app.services.qr_queue_service import QRQueueService
from app.models.clinic import Doctor
from app.models.user import User

def test_qr_service():
    db = SessionLocal()
    try:
        # Создаем тестового врача если его нет
        doctor = db.query(Doctor).first()
        if not doctor:
            print('❌ Нет врачей в базе данных для тестирования')
            return
        else:
            print(f'✅ Найден врач: {doctor.name if hasattr(doctor, "name") else doctor.id}')
        
        # Создаем тестового пользователя если его нет
        user = db.query(User).first()
        if not user:
            print('❌ Нет пользователей в базе данных для тестирования')
            return
        else:
            print(f'✅ Найден пользователь: {user.username}')
            
            # Тестируем создание QR токена
            service = QRQueueService(db)
            
            try:
                qr_data = service.generate_qr_token(
                    specialist_id=doctor.id,
                    department='cardiology',
                    generated_by_user_id=user.id,
                    expires_hours=24
                )
                
                print(f'✅ QR токен создан: {qr_data["token"][:16]}...')
                print(f'✅ QR URL: {qr_data["qr_url"]}')
                print(f'✅ Истекает: {qr_data["expires_at"]}')
                
                # Тестируем получение информации о токене
                token_info = service.get_qr_token_info(qr_data["token"])
                if token_info:
                    print(f'✅ Информация о токене получена: {token_info["specialist_name"]}')
                    print(f'✅ Отделение: {token_info["department_name"]}')
                    print(f'✅ Длина очереди: {token_info["queue_length"]}')
                else:
                    print('❌ Не удалось получить информацию о токене')
                    
            except Exception as e:
                print(f'❌ Ошибка тестирования: {e}')
        
    finally:
        db.close()

if __name__ == "__main__":
    test_qr_service()
