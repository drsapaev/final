from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT id, username, role FROM users WHERE username="cardio"')).fetchone()
    if result:
        print(f'From backend DB: ID={result[0]}, User={result[1]}, Role={result[2]}')
    else:
        print('User not found in backend DB')
    
    # Проверяем путь к БД
    print(f'\nDatabase URL: {engine.url}')

