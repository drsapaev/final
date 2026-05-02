#!/usr/bin/env python3
"""
Обновление кодов услуг в базе данных согласно правильному распределению
"""

import sqlite3
import os

def update_services_codes():
    """Обновляем коды услуг в базе данных"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔄 Обновляем коды услуг в базе данных...")

        # Обновляем коды услуг согласно новому распределению
        updates = [
            # Кардиология
            ("consultation.cardiology", "K01"),
            ("echo.cardiography", "K11"),

            # ЭКГ
            ("ecg", "ECG01"),

            # Дерматология
            ("consultation.dermatology", "D01"),
            ("derm.skin_diagnostics", "D02"),

            # Физиотерапия
            ("physio.darsonval", "P01"),
            ("physio.ufo", "P02"),
            ("physio.diode_mask", "P03"),
            ("physio.bioptron", "P04"),
            ("physio.excimer_laser", "P05"),

            # Косметология
            ("cosmetology.plasmolifting_face", "C01"),
            ("cosmetology.plasmolifting_hair", "C02"),
            ("cosmetology.mesotherapy_cosmetology", "C03"),
            ("cosmetology.face_cleaning", "C04"),
            ("cosmetology.blepharoplasty", "C05"),
            ("cosmetology.wen_removal", "C06"),
            ("cosmetology.tattoo_removal", "C07"),
            ("cosmetology.carbon_peeling", "C08"),

            # Дерматологические процедуры
            ("derm_proc.cryodestruction_warts", "D_PROC01"),
            ("derm_proc.cryodestruction_papillomas", "D_PROC02"),
            ("derm_proc.mesotherapy_scars", "D_PROC03"),

            # Стоматология
            ("consultation.dentistry", "S01"),
            ("dentistry.xray", "S10"),

            # Лаборатория (первые несколько)
            ("lab.cbc", "L01"),
        ]

        updated_count = 0
        for service_code, new_service_code in updates:
            cursor.execute("""
                UPDATE services
                SET service_code = ?, category_code = ?
                WHERE code = ?
            """, (new_service_code, new_service_code[0], service_code))

            if cursor.rowcount > 0:
                print(f"✅ Обновлена услуга: {service_code} -> {new_service_code}")
                updated_count += 1
            else:
                print(f"⚠️ Услуга не найдена: {service_code}")

        print(f"\n📊 Обновлено услуг: {updated_count}")

        # Обновляем лабораторные услуги (L02-L65)
        lab_updates = [
            ("lab.biochem", "L02"),
            ("lab.urine", "L25"),
            ("lab.coag", "L03"),
            ("lab.hormones", "L50"),
            ("lab.infection", "L31"),
        ]

        # Обновляем косметологические услуги без кодов
        cosmetology_updates = [
            ("cosmetology.botox", "C09"),
            ("cosmetology.mesotherapy", "C10"),
            ("cosmetology.peel", "C11"),
            ("cosmetology.laser", "C12"),
        ]

        # Обновляем прочие услуги
        other_updates = [
            ("other.general", "O01"),
        ]

        for service_code, new_service_code in lab_updates:
            cursor.execute("""
                UPDATE services
                SET service_code = ?, category_code = 'L'
                WHERE code = ?
            """, (new_service_code, service_code))

            if cursor.rowcount > 0:
                print(f"✅ Обновлена лабораторная услуга: {service_code} -> {new_service_code}")

        # Обновляем косметологические услуги без кодов
        for service_code, new_service_code in cosmetology_updates:
            cursor.execute("""
                UPDATE services
                SET service_code = ?, category_code = 'C'
                WHERE code = ?
            """, (new_service_code, service_code))

            if cursor.rowcount > 0:
                print(f"✅ Обновлена косметологическая услуга: {service_code} -> {new_service_code}")

        # Обновляем прочие услуги
        for service_code, new_service_code in other_updates:
            cursor.execute("""
                UPDATE services
                SET service_code = ?, category_code = 'O'
                WHERE code = ?
            """, (new_service_code, service_code))

            if cursor.rowcount > 0:
                print(f"✅ Обновлена прочая услуга: {service_code} -> {new_service_code}")

        conn.commit()
        print("✅ Обновление кодов услуг завершено")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    update_services_codes()
