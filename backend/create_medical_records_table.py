#!/usr/bin/env python3
"""
СОЗДАНИЕ ТАБЛИЦЫ MEDICAL_RECORDS
"""
import sqlite3
import os

def create_medical_records_table():
    print("🔧 СОЗДАНИЕ ТАБЛИЦЫ MEDICAL_RECORDS")
    print("=" * 50)
    
    db_path = 'clinic.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Проверяем существование таблицы
        print("1. Проверяем существование таблицы medical_records...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medical_records';")
        if cursor.fetchone():
            print("   ✅ Таблица medical_records уже существует")
        else:
            print("   ❌ Таблица medical_records не найдена")
            
            # 2. Создаем таблицу medical_records
            print("2. Создаем таблицу medical_records...")
            cursor.execute("""
                CREATE TABLE medical_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    appointment_id INTEGER,
                    doctor_id INTEGER NOT NULL,
                    record_type VARCHAR(50) NOT NULL DEFAULT 'general',
                    chief_complaint TEXT,
                    history_of_present_illness TEXT,
                    past_medical_history TEXT,
                    medications TEXT,
                    allergies TEXT,
                    family_history TEXT,
                    social_history TEXT,
                    review_of_systems TEXT,
                    physical_examination TEXT,
                    vital_signs TEXT,
                    assessment TEXT,
                    plan TEXT,
                    diagnosis TEXT,
                    treatment_notes TEXT,
                    follow_up_instructions TEXT,
                    additional_notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER NOT NULL,
                    updated_by INTEGER,
                    status VARCHAR(20) DEFAULT 'active',
                    is_confidential BOOLEAN DEFAULT 0,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (appointment_id) REFERENCES appointments(id),
                    FOREIGN KEY (doctor_id) REFERENCES users(id),
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (updated_by) REFERENCES users(id)
                );
            """)
            print("   ✅ Таблица medical_records создана")
        
        # 3. Создаем индексы для оптимизации
        print("3. Создаем индексы...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_medical_records_patient_id ON medical_records(patient_id);",
            "CREATE INDEX IF NOT EXISTS idx_medical_records_appointment_id ON medical_records(appointment_id);",
            "CREATE INDEX IF NOT EXISTS idx_medical_records_doctor_id ON medical_records(doctor_id);",
            "CREATE INDEX IF NOT EXISTS idx_medical_records_created_at ON medical_records(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_medical_records_status ON medical_records(status);"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        print("   ✅ Индексы созданы")
        
        # 4. Проверяем структуру таблицы
        print("4. Проверяем структуру таблицы...")
        cursor.execute("PRAGMA table_info(medical_records);")
        columns = cursor.fetchall()
        print("   📊 Колонки таблицы medical_records:")
        for col in columns:
            print(f"      - {col[1]} ({col[2]})")
        
        # 5. Добавляем тестовые данные
        print("5. Добавляем тестовые данные...")
        
        # Проверяем есть ли уже данные
        cursor.execute("SELECT COUNT(*) FROM medical_records;")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Получаем ID пациента и врача
            cursor.execute("SELECT id FROM patients LIMIT 1;")
            patient_result = cursor.fetchone()
            cursor.execute("SELECT id FROM users WHERE role = 'doctor' LIMIT 1;")
            doctor_result = cursor.fetchone()
            
            if patient_result and doctor_result:
                patient_id = patient_result[0]
                doctor_id = doctor_result[0]
                
                # Добавляем тестовую запись
                cursor.execute("""
                    INSERT INTO medical_records (
                        patient_id, doctor_id, record_type, chief_complaint,
                        history_of_present_illness, physical_examination,
                        assessment, plan, diagnosis, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_id, doctor_id, 'general',
                    'Головная боль',
                    'Пациент жалуется на головную боль в течение 2 дней',
                    'АД 120/80, ЧСС 72, температура 36.6°C',
                    'Головная боль напряжения',
                    'Рекомендован отдых, обильное питье',
                    'Головная боль напряжения',
                    doctor_id
                ))
                print("   ✅ Тестовые данные добавлены")
            else:
                print("   ⚠️ Нет пациентов или врачей для тестовых данных")
        else:
            print(f"   ℹ️ В таблице уже есть {count} записей")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Создание таблицы medical_records завершено успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    create_medical_records_table()
