from __future__ import annotations

from app.services.lab_seed_data_extra import TORCH_ANALYTES

DEFAULT_LAB_UNIT_DEFINITIONS = [
    {"code": "10e9_per_l", "name": "10^9 per liter", "symbol": "10^9/L", "sort_order": 10},
    {"code": "10e12_per_l", "name": "10^12 per liter", "symbol": "10^12/L", "sort_order": 20},
    {"code": "g_per_l", "name": "gram per liter", "symbol": "g/L", "sort_order": 30},
    {"code": "percent", "name": "percent", "symbol": "%", "sort_order": 40},
    {"code": "mm_per_h", "name": "millimeter per hour", "symbol": "mm/soat", "sort_order": 50},
    {"code": "mmol_per_l", "name": "millimole per liter", "symbol": "mmol/L", "sort_order": 60},
    {"code": "umol_per_l", "name": "micromole per liter", "symbol": "mkmol/L", "sort_order": 70},
    {"code": "u_per_l", "name": "unit per liter", "symbol": "U/L", "sort_order": 80},
    {"code": "pmol_per_l", "name": "picomole per liter", "symbol": "pmol/L", "sort_order": 90},
    {"code": "nmol_per_l", "name": "nanomole per liter", "symbol": "nmol/L", "sort_order": 100},
    {"code": "miu_per_l", "name": "milli-international unit per liter", "symbol": "mIU/L", "sort_order": 110},
    {"code": "iu_per_ml", "name": "international unit per milliliter", "symbol": "IU/mL", "sort_order": 120},
    {"code": "me_per_ml", "name": "international unit per milliliter", "symbol": "МЕ/мл", "sort_order": 130},
    {"code": "index", "name": "index", "symbol": "Index", "sort_order": 140},
    {"code": "ml", "name": "milliliter", "symbol": "ml", "sort_order": 150},
    {"code": "min", "name": "minute", "symbol": "min", "sort_order": 160},
    {"code": "cm", "name": "centimeter", "symbol": "cm", "sort_order": 170},
    {"code": "million_per_ml", "name": "million per milliliter", "symbol": "10^6/ml", "sort_order": 180},
    {"code": "ph", "name": "pH", "symbol": "pH", "sort_order": 190},
    {"code": "sg", "name": "specific gravity", "symbol": "SG", "sort_order": 200},
    {"code": "cells_per_fov", "name": "cells per field of view", "symbol": "кл/зр", "sort_order": 210},
    {"code": "ng_per_ml", "name": "nanogram per milliliter", "symbol": "ng/mL", "sort_order": 220},
]


DEFAULT_LAB_ANALYTE_DEFINITIONS = [
    {"code": "wbc", "name": "Leukocytes", "short_name": "WBC", "category": "hematology", "default_unit_code": "10e9_per_l", "sort_order": 10},
    {"code": "rbc", "name": "Erythrocytes", "short_name": "RBC", "category": "hematology", "default_unit_code": "10e12_per_l", "sort_order": 20},
    {"code": "hgb", "name": "Hemoglobin", "short_name": "HGB", "category": "hematology", "default_unit_code": "g_per_l", "sort_order": 30},
    {"code": "hct", "name": "Hematocrit", "short_name": "HCT", "category": "hematology", "default_unit_code": "percent", "sort_order": 40},
    {"code": "plt", "name": "Platelets", "short_name": "PLT", "category": "hematology", "default_unit_code": "10e9_per_l", "sort_order": 50},
    {"code": "esr", "name": "ESR", "short_name": "ESR", "category": "hematology", "default_unit_code": "mm_per_h", "sort_order": 60},
    {"code": "neutrophils", "name": "Neutrophils", "short_name": "NEUT", "category": "hematology", "default_unit_code": "percent", "sort_order": 70},
    {"code": "lymphocytes", "name": "Lymphocytes", "short_name": "LYMPH", "category": "hematology", "default_unit_code": "percent", "sort_order": 80},
    {"code": "monocytes", "name": "Monocytes", "short_name": "MONO", "category": "hematology", "default_unit_code": "percent", "sort_order": 90},
    {"code": "eosinophils", "name": "Eosinophils", "short_name": "EOS", "category": "hematology", "default_unit_code": "percent", "sort_order": 100},
    {"code": "basophils", "name": "Basophils", "short_name": "BASO", "category": "hematology", "default_unit_code": "percent", "sort_order": 110},
    {"code": "total_protein", "name": "Total Protein", "short_name": "TP", "category": "biochemistry", "default_unit_code": "g_per_l", "sort_order": 120},
    {"code": "glucose", "name": "Glucose", "short_name": "GLU", "category": "biochemistry", "default_unit_code": "mmol_per_l", "sort_order": 130},
    {"code": "cholesterol", "name": "Total Cholesterol", "short_name": "CHOL", "category": "biochemistry", "default_unit_code": "mmol_per_l", "sort_order": 140},
    {"code": "urea", "name": "Urea", "short_name": "UREA", "category": "biochemistry", "default_unit_code": "mmol_per_l", "sort_order": 150},
    {"code": "creatinine", "name": "Creatinine", "short_name": "CREA", "category": "biochemistry", "default_unit_code": "umol_per_l", "sort_order": 160},
    {"code": "alt", "name": "Alanine aminotransferase", "short_name": "ALT", "category": "biochemistry", "default_unit_code": "u_per_l", "sort_order": 170},
    {"code": "ast", "name": "Aspartate aminotransferase", "short_name": "AST", "category": "biochemistry", "default_unit_code": "u_per_l", "sort_order": 180},
    {"code": "bilirubin_total", "name": "Total Bilirubin", "short_name": "TBIL", "category": "biochemistry", "default_unit_code": "umol_per_l", "sort_order": 190},
    {"code": "bilirubin_direct", "name": "Direct Bilirubin", "short_name": "DBIL", "category": "biochemistry", "default_unit_code": "umol_per_l", "sort_order": 200},
    {"code": "total_ige", "name": "Total IgE", "short_name": "IgE", "category": "allergy", "default_unit_code": "me_per_ml", "sort_order": 210},
    {"code": "t3_free", "name": "Free triiodothyronine", "short_name": "T3", "category": "endocrinology", "default_unit_code": "pmol_per_l", "sort_order": 220},
    {"code": "t4_total", "name": "Total thyroxine", "short_name": "T4", "category": "endocrinology", "default_unit_code": "nmol_per_l", "sort_order": 230},
    {"code": "tsh", "name": "Thyroid stimulating hormone", "short_name": "TSH", "category": "endocrinology", "default_unit_code": "miu_per_l", "sort_order": 240},
    {"code": "at_tpo", "name": "Thyroid peroxidase antibody", "short_name": "AT-ТПО", "category": "endocrinology", "default_unit_code": "iu_per_ml", "sort_order": 250},
    {"code": "vitamin_d_25_hydroxy", "name": "Vitamin D, 25-Hydroxy", "short_name": "Vit D", "category": "endocrinology", "default_unit_code": "ng_per_ml", "sort_order": 255},
    {"code": "hba1c", "name": "Hemoglobin A1c", "short_name": "HbA1c", "category": "glycemic", "default_unit_code": "percent", "sort_order": 256},
    {"code": "testosterone_total", "name": "Testosterone, Total", "short_name": "TEST", "category": "endocrinology", "default_unit_code": "nmol_per_l", "sort_order": 257},
]

DEFAULT_LAB_ANALYTE_DEFINITIONS.extend(
    [
        {
            "code": code,
            "name": label,
            "short_name": label[:16],
            "category": "infectious",
            "default_unit_code": "index",
            "sort_order": 260 + index * 10,
        }
        for index, (code, label) in enumerate(TORCH_ANALYTES, start=1)
    ]
)

DEFAULT_LAB_ANALYTE_DEFINITIONS.extend(
    [
        {"code": "volume", "name": "Sperm volume", "short_name": "VOL", "category": "andrology", "default_unit_code": "ml", "sort_order": 500},
        {"code": "viscosity", "name": "Sperm viscosity", "short_name": "VIS", "category": "andrology", "default_unit_code": "cm", "sort_order": 510},
        {"code": "liquefaction_time", "name": "Liquefaction time", "short_name": "LQF", "category": "andrology", "default_unit_code": "min", "sort_order": 520},
        {"code": "ph", "name": "Semen pH", "short_name": "pH", "category": "andrology", "default_unit_code": "ph", "sort_order": 530},
        {"code": "actively_motile", "name": "Actively motile spermatozoa", "short_name": "AMOT", "category": "andrology", "default_unit_code": "percent", "sort_order": 540},
        {"code": "slowly_motile", "name": "Slowly motile spermatozoa", "short_name": "SMOT", "category": "andrology", "default_unit_code": "percent", "sort_order": 550},
        {"code": "immobile", "name": "Immobile spermatozoa", "short_name": "IMM", "category": "andrology", "default_unit_code": "percent", "sort_order": 560},
        {"code": "alive", "name": "Alive spermatozoa", "short_name": "ALIVE", "category": "andrology", "default_unit_code": "percent", "sort_order": 570},
        {"code": "dead", "name": "Dead spermatozoa", "short_name": "DEAD", "category": "andrology", "default_unit_code": "percent", "sort_order": 580},
        {"code": "count_per_ml", "name": "Sperm count per ml", "short_name": "CNT", "category": "andrology", "default_unit_code": "million_per_ml", "sort_order": 590},
        {"code": "normal_forms", "name": "Normal forms", "short_name": "NORM", "category": "andrology", "default_unit_code": "percent", "sort_order": 600},
        {"code": "changed_forms", "name": "Changed forms", "short_name": "CHG", "category": "andrology", "default_unit_code": "percent", "sort_order": 610},
        {"code": "heads", "name": "Head defects", "short_name": "HD", "category": "andrology", "default_unit_code": "percent", "sort_order": 620},
        {"code": "bodies", "name": "Body defects", "short_name": "BD", "category": "andrology", "default_unit_code": "percent", "sort_order": 630},
        {"code": "tails", "name": "Tail defects", "short_name": "TL", "category": "andrology", "default_unit_code": "percent", "sort_order": 640},
        {"code": "spermatogenesis_cells", "name": "Spermatogenesis cells", "short_name": "SPM", "category": "andrology", "default_unit_code": "percent", "sort_order": 650},
    ]
)


DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS = [
    {"analyte_code": "wbc", "text": "4.0 - 9.0", "low": 4.0, "high": 9.0, "sort_order": 10},
    {"analyte_code": "rbc", "sex": "M", "text": "4.0 - 5.5", "low": 4.0, "high": 5.5, "sort_order": 10},
    {"analyte_code": "rbc", "sex": "F", "text": "3.7 - 4.7", "low": 3.7, "high": 4.7, "sort_order": 20},
    {"analyte_code": "hgb", "sex": "M", "text": "130 - 170", "low": 130, "high": 170, "sort_order": 10},
    {"analyte_code": "hgb", "sex": "F", "text": "120 - 150", "low": 120, "high": 150, "sort_order": 20},
    {"analyte_code": "hct", "text": "36 - 50", "low": 36, "high": 50, "sort_order": 10},
    {"analyte_code": "plt", "text": "150 - 400", "low": 150, "high": 400, "sort_order": 10},
    {"analyte_code": "esr", "text": "2 - 15", "low": 2, "high": 15, "sort_order": 10},
    {"analyte_code": "neutrophils", "text": "47 - 72", "low": 47, "high": 72, "sort_order": 10},
    {"analyte_code": "lymphocytes", "text": "19 - 37", "low": 19, "high": 37, "sort_order": 10},
    {"analyte_code": "monocytes", "text": "3 - 11", "low": 3, "high": 11, "sort_order": 10},
    {"analyte_code": "eosinophils", "text": "0.5 - 5", "low": 0.5, "high": 5, "sort_order": 10},
    {"analyte_code": "basophils", "text": "0 - 1", "low": 0, "high": 1, "sort_order": 10},
    {"analyte_code": "total_protein", "text": "64 - 83", "low": 64, "high": 83, "sort_order": 10},
    {"analyte_code": "glucose", "text": "3.3 - 5.5", "low": 3.3, "high": 5.5, "sort_order": 10},
    {"analyte_code": "cholesterol", "text": "0 - 5.2", "low": 0, "high": 5.2, "sort_order": 10},
    {"analyte_code": "urea", "text": "2.5 - 8.3", "low": 2.5, "high": 8.3, "sort_order": 10},
    {"analyte_code": "creatinine", "sex": "M", "text": "62 - 115", "low": 62, "high": 115, "sort_order": 10},
    {"analyte_code": "creatinine", "sex": "F", "text": "53 - 97", "low": 53, "high": 97, "sort_order": 20},
    {"analyte_code": "alt", "text": "0 - 41", "low": 0, "high": 41, "sort_order": 10},
    {"analyte_code": "ast", "text": "0 - 40", "low": 0, "high": 40, "sort_order": 10},
    {"analyte_code": "bilirubin_total", "text": "3.4 - 20.5", "low": 3.4, "high": 20.5, "sort_order": 10},
    {"analyte_code": "bilirubin_direct", "text": "0 - 8.6", "low": 0, "high": 8.6, "sort_order": 10},
    {"analyte_code": "total_ige", "age_max_months": 5, "text": "< 12 МЕ/мл", "high": 12, "sort_order": 10},
    {"analyte_code": "total_ige", "age_min_months": 6, "age_max_months": 11, "text": "< 30 МЕ/мл", "high": 30, "sort_order": 20},
    {"analyte_code": "total_ige", "age_min_months": 12, "age_max_months": 47, "text": "< 45 МЕ/мл", "high": 45, "sort_order": 30},
    {"analyte_code": "total_ige", "age_min_months": 48, "age_max_months": 83, "text": "< 70 МЕ/мл", "high": 70, "sort_order": 40},
    {"analyte_code": "total_ige", "age_min_months": 84, "age_max_months": 119, "text": "< 90 МЕ/мл", "high": 90, "sort_order": 50},
    {"analyte_code": "total_ige", "age_min_months": 120, "age_max_months": 179, "text": "< 120 МЕ/мл", "high": 120, "sort_order": 60},
    {"analyte_code": "total_ige", "age_min_months": 180, "text": "< 130 МЕ/мл", "high": 130, "sort_order": 70},
    {"analyte_code": "t3_free", "text": "1.03 - 4.03", "low": 1.03, "high": 4.03, "sort_order": 10},
    {"analyte_code": "t4_total", "text": "4.71 - 10.73", "low": 4.71, "high": 10.73, "sort_order": 10},
    {"analyte_code": "tsh", "text": "0.32 - 6.58", "low": 0.32, "high": 6.58, "sort_order": 10},
    {"analyte_code": "at_tpo", "text": "0 - 45", "low": 0, "high": 45, "sort_order": 10},
    {"analyte_code": "vitamin_d_25_hydroxy", "text": "30 - 100 ng/mL", "low": 30, "high": 100, "sort_order": 10},
    {"analyte_code": "hba1c", "text": "4.8 - 5.6 %", "low": 4.8, "high": 5.6, "sort_order": 10},
    {"analyte_code": "testosterone_total", "sex": "M", "text": "9.16 - 31.80 nmol/L", "low": 9.16, "high": 31.80, "sort_order": 10},
    {"analyte_code": "testosterone_total", "sex": "F", "text": "0.35 - 1.91 nmol/L", "low": 0.35, "high": 1.91, "sort_order": 20},
]

DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS.extend(
    [
        {"analyte_code": code, "text": "0 - 0.9", "low": 0, "high": 0.9, "sort_order": 10}
        for code, _ in TORCH_ANALYTES
    ]
)

DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS.extend(
    [
        {"analyte_code": "volume", "text": "2 - 6", "low": 2, "high": 6, "sort_order": 10},
        {"analyte_code": "viscosity", "text": "0.1 - 0.5", "low": 0.1, "high": 0.5, "sort_order": 10},
        {"analyte_code": "liquefaction_time", "text": "20 - 30", "low": 20, "high": 30, "sort_order": 10},
        {"analyte_code": "ph", "text": "7.2 - 8.0", "low": 7.2, "high": 8.0, "sort_order": 10},
        {"analyte_code": "actively_motile", "text": "70 - 100", "low": 70, "high": 100, "sort_order": 10},
        {"analyte_code": "slowly_motile", "text": "4 - 30", "low": 4, "high": 30, "sort_order": 10},
        {"analyte_code": "immobile", "text": "0 - 14", "low": 0, "high": 14, "sort_order": 10},
        {"analyte_code": "alive", "text": "80 - 90", "low": 80, "high": 90, "sort_order": 10},
        {"analyte_code": "dead", "text": "10 - 20", "low": 10, "high": 20, "sort_order": 10},
        {"analyte_code": "count_per_ml", "text": "60 - 150", "low": 60, "high": 150, "sort_order": 10},
        {"analyte_code": "normal_forms", "text": "81 - 100", "low": 81, "high": 100, "sort_order": 10},
        {"analyte_code": "changed_forms", "text": "0 - 19", "low": 0, "high": 19, "sort_order": 10},
        {"analyte_code": "heads", "text": "0 - 15", "low": 0, "high": 15, "sort_order": 10},
        {"analyte_code": "bodies", "text": "0 - 2", "low": 0, "high": 2, "sort_order": 10},
        {"analyte_code": "tails", "text": "0 - 2", "low": 0, "high": 2, "sort_order": 10},
        {"analyte_code": "spermatogenesis_cells", "text": "1 - 2", "low": 1, "high": 2, "sort_order": 10},
    ]
)

DEFAULT_LAB_ANALYTE_DEFINITIONS.extend(
    [
        {"code": "urine_ph", "name": "Urine pH", "short_name": "U-PH", "category": "urinalysis", "default_unit_code": "ph", "sort_order": 660},
        {"code": "urine_specific_gravity", "name": "Urine specific gravity", "short_name": "SG", "category": "urinalysis", "default_unit_code": "sg", "sort_order": 670},
        {"code": "urine_squamous_epithelium", "name": "Urine squamous epithelium", "short_name": "SQUAM", "category": "urinalysis", "default_unit_code": "cells_per_fov", "sort_order": 680},
        {"code": "urine_transitional_epithelium", "name": "Urine transitional epithelium", "short_name": "TRANS", "category": "urinalysis", "default_unit_code": "cells_per_fov", "sort_order": 690},
        {"code": "urine_leukocytes", "name": "Urine leukocytes", "short_name": "LEU", "category": "urinalysis", "default_unit_code": "cells_per_fov", "sort_order": 700},
        {"code": "urine_unmodified_erythrocytes", "name": "Urine erythrocytes", "short_name": "ERY", "category": "urinalysis", "default_unit_code": "cells_per_fov", "sort_order": 710},
    ]
)

DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS.extend(
    [
        {"analyte_code": "urine_ph", "text": "4 - 7", "low": 4, "high": 7, "sort_order": 10},
        {"analyte_code": "urine_specific_gravity", "text": "1015 - 1025", "low": 1015, "high": 1025, "sort_order": 10},
        {"analyte_code": "urine_squamous_epithelium", "text": "0 - 2", "low": 0, "high": 2, "sort_order": 10},
        {"analyte_code": "urine_transitional_epithelium", "text": "0 - 1", "low": 0, "high": 1, "sort_order": 10},
        {"analyte_code": "urine_leukocytes", "sex": "M", "text": "Эр: 0 - 3", "low": 0, "high": 3, "sort_order": 10},
        {"analyte_code": "urine_leukocytes", "sex": "F", "text": "Аёл: 0 - 6", "low": 0, "high": 6, "sort_order": 20},
        {"analyte_code": "urine_unmodified_erythrocytes", "sex": "M", "text": "Эр: 0 - 1", "low": 0, "high": 1, "sort_order": 10},
        {"analyte_code": "urine_unmodified_erythrocytes", "sex": "F", "text": "Аёл: 0 - 3", "low": 0, "high": 3, "sort_order": 20},
    ]
)
