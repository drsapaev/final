# ruff: noqa: I001

from __future__ import annotations

from app.services.lab_seed_data_extra import EXTRA_LAB_TEMPLATE_DEFINITIONS


CBC_OAK_FIELDS = [
    ("rbc", "Эритроцитлар (RBC)", "3.5-5*1012/л"),
    ("hgb", "Гемоглобин концентрацияси (HGB)", "110-160 г/л"),
    ("wbc", "Лейкоцитлар (WBC)", "4-10*109/л"),
    ("neutrophils_segmented", "Сегмент ядроли нейтрофиллар", "50-70%"),
    ("neutrophils_band", "Таёқча ядроли нейтрофиллар", "1-6%"),
    ("eosinophils", "Эозинофиллар %", "0,5-5%"),
    ("basophils", "Базофиллар %", "0-1%"),
    ("lymphocytes", "Лимфоцитлар %", "20-40%"),
    ("monocytes", "Моноцитлар %", "3-11%"),
    (
        "plt",
        "Тромбоцитлар (PLT)",
        "1ойлик-5ёш – 217-553*109/л\nКатталар – 180-320*109/л",
    ),
    ("mpv", "Тромбоцитларнинг ўртача ҳажми (MPV)", "7-11фл"),
    ("pdw", "Тромбоцитларнинг тарқалиш ҳажми (PDW)", "15-17фл"),
    ("pct", "Тромбокрит (PCT)", "1,08-2,82мл/л"),
    ("hct", "Гематокрит (HCT)", "37-44%"),
    ("mcv", "Эритроцитнинг ўртача ҳажми (MCV)", "82-95фл"),
    (
        "mch",
        "Эритроцитда гемоглобиннинг ўртача миқдори  (MCH)",
        "27-31пг",
    ),
    (
        "mchc",
        "Эритроцитда гемоглобиннинг ўртача концентрацияси (MCHC)",
        "320-360г/л",
    ),
    (
        "rdw_cv",
        "Эритроцитларнинг тарқалиш ҳажми – вариация коэффиценти (RDW-CV)",
        "0,110-0,160",
    ),
    (
        "rdw_sd",
        "Эритроцитларнинг тарқалиш ҳажми – стандарт оғиш (RDW-SD)",
        "35-56фл",
    ),
    (
        "esr",
        "Эритроцитларнинг чўкиш тезлиги – СОЭ (ESR)",
        "Эр.: 2-10 мм/соат\nАёл.: 2-15 мм/соат\n60ёшдан катта эр: 2-25мм/с\n60ёшдан катта аёл: 2-35мм/с\nХомиладорлар: 2-45 мм/соат",
    ),
    (
        "vsk",
        "Қон ивиш вақти – ВСК\n(Сухарев бўйича)",
        "Бошлаш :                   Тугаш :\nБошл.: 30 сек – 2 мин\nТугаш: 3 – 5 мин",
    ),
]

BIOCHEM_FIELDS = [
    ("total_protein", "Умумий оқсил", "66-87 г/л"),
    ("glucose", "Глюкоза", "3,3-6,1 ммоль/л"),
    ("cholesterol", "Холестерин (умумий)", "3,5-5,0 ммоль/л"),
    ("urea", "Мочевина", "2,5-7,5ммоль/л"),
    ("creatinine", "Креатинин", "Эр: 53-123  Мкмоль/л\nАёл: 44-97  Мкмоль/л"),
    ("alt", "АлАТ (аланинаминотрансфераза)", "Эр: 40 Ед/л  гача\nАёл: 32 Ед/л  гача"),
    ("ast", "АсАТ (аспартатаминотрансфераза)", "Эр: 38 Ед/л  гача\nАёл: 31 Ед/л  гача"),
    ("bilirubin_total", "Билирубин (умумий)", "≤18,8 Мкмоль/л\nЯнги туғилган чақалоқ: ≤205,2 Мкмоль/л"),
    ("bilirubin_direct", "Билирубин (бевосита)", "≤4,3 Мкмоль/л"),
    ("bilirubin_indirect", "Билирубин (билвосита)", "≤14,5 Мкмоль/л"),
    ("alkaline_phosphatase", "Щелочная фосфатаза", ""),
    ("alpha_amylase", "α-Амилаза", "≤90 Ед/л"),
    ("potassium", "Калий", "3,6-5,5 ммоль/л"),
    ("calcium", "Кальций", "Катта:2,1-2,6 ммоль/л\nБола: 2,5-3,0 ммоль/л"),
    ("sodium", "Натрий", "135-155 ммоль/л"),
]

DEFAULT_LAB_TEMPLATE_DEFINITIONS = [
    {
        "code": "cbc_oak",
        "name": "ОАК",
        "family": "hematology",
        "description": "Пилотный шаблон общего анализа крови.",
        "initial_version": {
            "layout_preset": "lab_table_classic_v1",
            "page_settings": {"paper_size": "A4", "orientation": "portrait"},
            "branding_overrides": {
                "document_title": "УМУМИЙ ҚОН ТАХЛИЛИ",
                "document_subtitle": "Тўрткўл автовокзал ёнида",
                "address": "Турткул ш. Беруний кўчаси",
                "phone": "55. 104. 34. 34.",
            },
            "signer_defaults": {
                "lab_technician_label": "Врач лаборант",
                "lab_technician_name": "Ганжаев Н.",
                "approver_label": "",
                "approver_name": "",
            },
            "footer_notes": "",
            "sections": [
                {
                    "key": "cbc_main",
                    "title": "",
                    "sort_order": 10,
                    "section_style": {"render": "docx_three_column"},
                    "fields": [
                        *[
                            {
                                "field_key": field_key,
                                "label": label,
                                "value_type": "text" if field_key == "vsk" else "numeric",
                                "reference_mode": "static_text",
                                "reference_text": reference_text,
                                "sort_order": (index + 1) * 10,
                                "required": False,
                            }
                            for index, (field_key, label, reference_text) in enumerate(CBC_OAK_FIELDS)
                        ],
                    ],
                },
            ],
        },
    },
    {
        "code": "biochem_panel",
        "name": "Биохимия",
        "family": "biochemistry",
        "description": "Пилотный шаблон биохимического бланка.",
        "initial_version": {
            "layout_preset": "lab_table_compact_v1",
            "page_settings": {"paper_size": "A4", "orientation": "portrait"},
            "branding_overrides": {
                "document_title": "БИОКИМЁВИЙ ҚОН ТАХЛИЛИ",
                "document_subtitle": "Тўрткўл автовокзал ёнида",
                "address": "Турткул ш. Беруний кўчаси",
                "phone": "+998 55 104 34 34",
            },
            "signer_defaults": {
                "lab_technician_label": "Врач лаборант",
                "lab_technician_name": "Ганжаев Н.",
                "approver_label": "",
                "approver_name": "",
            },
            "footer_notes": "",
            "sections": [
                {
                    "key": "biochem_main",
                    "title": "",
                    "sort_order": 10,
                    "section_style": {"render": "docx_three_column"},
                    "fields": [
                        *[
                            {
                                "field_key": field_key,
                                "label": label,
                                "value_type": "numeric",
                                "reference_mode": "static_text",
                                "reference_text": reference_text,
                                "sort_order": (index + 1) * 10,
                                "required": False,
                            }
                            for index, (field_key, label, reference_text) in enumerate(BIOCHEM_FIELDS)
                        ],
                    ],
                },
            ],
        },
    },
]

DEFAULT_LAB_TEMPLATE_DEFINITIONS.extend(EXTRA_LAB_TEMPLATE_DEFINITIONS)
