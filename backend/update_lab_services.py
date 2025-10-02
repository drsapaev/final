#!/usr/bin/env python3
"""
Обновление лабораторных услуг в базе данных согласно полному списку
"""

import sqlite3
import os

def update_lab_services():
    """Обновляем лабораторные услуги"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔄 Обновляем лабораторные услуги...")

        # Полный список лабораторных услуг согласно требованиям
        lab_services = [
            ("lab.cbc", "Общий анализ крови", "L01"),
            ("lab.coag", "Время свертываемости крови", "L03"),
            ("lab.urine", "Общий анализ мочи", "L25"),
            ("lab.glucose_express", "Глюкоза экспресс тест", "L35"),
            ("lab.hbsag", "HBsAg Экспресс тест", "L30"),
            ("lab.hcv", "HCV Экспресс тест", "L31"),
            ("lab.hiv", "HIV Экспресс тест", "L32"),
            ("lab.rw", "RW Экспресс тест", "L33"),
            ("lab.protein", "Общий белок", "L10"),
            ("lab.glucose", "Глюкоза", "L11"),
            ("lab.cholesterol", "Холестерин", "L12"),
            ("lab.urea", "Мочевина", "L13"),
            ("lab.creatinine", "Креатинин", "L14"),
            ("lab.alt", "АлАТ - аланинаминотрансфераза", "L15"),
            ("lab.ast", "АсАТ - аспартатаминотрансфераза", "L16"),
            ("lab.bilirubin", "Билирубин (общ, прям, непрям)", "L17"),
            ("lab.alkaline", "Щелочная фосфатаза", "L18"),
            ("lab.amylase", "Альфа-амилаза", "L19"),
            ("lab.potassium", "Калий", "L20"),
            ("lab.calcium", "Кальций", "L21"),
            ("lab.sodium", "Натрий", "L22"),
            ("lab.vitamin_d", "Витамин Д", "L23"),
            ("lab.immunoglobulin", "Иммуноглобулин Е", "L65"),
            ("lab.spermogram", "Спермограмма", "L34"),
            ("lab.rheumatoid", "Ревматоидный фактор (RF)", "L40"),
            ("lab.crp", "С-реактивный белок (CRP)", "L41"),
            ("lab.aslo", "Антистрептолизин-О (ASlO)", "L42"),
            ("lab.brucellosis", "Бруцеллез (Rose Bengal)", "L43"),
            ("lab.tsh", "ТТГ (тиреотропный гормон)", "L50"),
            ("lab.t4", "Т4 (тироксин)", "L51"),
            ("lab.t3", "Т3 (трийодтиронин)", "L52"),
            ("lab.at_tpo", "АТ-ТПО (аутоантитело к тиреопероксидазе)", "L53"),
            ("lab.testosterone", "Тестостерон", "L54"),
            ("lab.fungi", "Нити грибки", "L60"),
            ("lab.malassezia", "Malassezia furfur", "L61"),
            ("lab.demodex", "Демодекоз", "L62"),
            ("lab.smear", "Мазок на степень чистоты", "L63"),
            ("lab.stool", "Кал на я/г", "L64"),
        ]

        updated_count = 0
        for service_code, service_name, new_service_code in lab_services:
            cursor.execute("""
                UPDATE services
                SET service_code = ?, category_code = 'L', name = ?
                WHERE code = ?
            """, (new_service_code, service_name, service_code))

            if cursor.rowcount > 0:
                print(f"✅ Обновлена лабораторная услуга: {service_code} -> {new_service_code} ({service_name})")
                updated_count += 1
            else:
                print(f"⚠️ Лабораторная услуга не найдена: {service_code}")

        print(f"\n📊 Обновлено лабораторных услуг: {updated_count}")

        conn.commit()
        print("✅ Обновление лабораторных услуг завершено")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    update_lab_services()
