from __future__ import annotations

from typing import Any


def _field(
    field_key: str,
    label: str,
    *,
    analyte_code: str | None = None,
    unit_code: str | None = None,
    value_type: str = "text",
    unit: str | None = None,
    reference_mode: str = "static_text",
    reference_text: str | None = None,
    reference_rule: dict[str, Any] | None = None,
    visibility_rule: dict[str, Any] | None = None,
    highlight_rule: dict[str, Any] | None = None,
    choice_options: list[str] | None = None,
    sort_order: int = 0,
    required: bool = False,
) -> dict[str, Any]:
    field = {
        "field_key": field_key,
        "label": label,
        "value_type": value_type,
        "unit": unit,
        "reference_mode": reference_mode,
        "reference_text": reference_text,
        "reference_rule": reference_rule,
        "visibility_rule": visibility_rule,
        "highlight_rule": highlight_rule,
        "choice_options": choice_options,
        "sort_order": sort_order,
        "required": required,
    }
    if analyte_code is not None:
        field["analyte_code"] = analyte_code
    if unit_code is not None:
        field["unit_code"] = unit_code
    return field


def _section(
    key: str,
    title: str,
    sort_order: int,
    fields: list[dict[str, Any]],
    *,
    section_style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "sort_order": sort_order,
        "section_style": section_style or {},
        "fields": fields,
    }


def _template(
    *,
    code: str,
    name: str,
    family: str,
    description: str,
    layout_preset: str,
    document_title: str,
    document_subtitle: str,
    branding_overrides: dict[str, Any] | None = None,
    footer_notes: str = "",
    sections: list[dict[str, Any]],
    signer_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overrides = {
        "document_title": document_title,
        "document_subtitle": document_subtitle,
    }
    if branding_overrides:
        overrides.update(branding_overrides)
    return {
        "code": code,
        "name": name,
        "family": family,
        "description": description,
        "initial_version": {
            "layout_preset": layout_preset,
            "page_settings": {"paper_size": "A4", "orientation": "portrait"},
            "branding_overrides": overrides,
            "signer_defaults": signer_defaults
            or {
                "lab_technician_label": "Врач лаборант",
                "approver_label": "Подпись",
            },
            "footer_notes": footer_notes,
            "sections": sections,
        },
    }


def _sex_reference_rule(
    *,
    male_text: str,
    male_low: float | int,
    male_high: float | int,
    female_text: str,
    female_low: float | int,
    female_high: float | int,
    default_text: str,
    default_low: float | int,
    default_high: float | int,
) -> dict[str, Any]:
    return {
        "cases": [
            {
                "when": {"source": "patient.sex", "op": "eq", "value": "M"},
                "text": male_text,
                "low": male_low,
                "high": male_high,
            },
            {
                "when": {"source": "patient.sex", "op": "eq", "value": "F"},
                "text": female_text,
                "low": female_low,
                "high": female_high,
            },
        ],
        "default": {"text": default_text, "low": default_low, "high": default_high},
    }


def _ige_reference_rule() -> dict[str, Any]:
    return {
        "cases": [
            {
                "when": {"source": "patient.age_months", "op": "lt", "value": 6},
                "text": "< 12 МЕ/мл",
                "low": None,
                "high": 12,
            },
            {
                "when": {"source": "patient.age_months", "op": "between", "min": 6, "max": 12},
                "text": "< 30 МЕ/мл",
                "low": None,
                "high": 30,
            },
            {
                "when": {"source": "patient.age_years", "op": "between", "min": 1, "max": 3},
                "text": "< 45 МЕ/мл",
                "low": None,
                "high": 45,
            },
            {
                "when": {"source": "patient.age_years", "op": "between", "min": 4, "max": 6},
                "text": "< 70 МЕ/мл",
                "low": None,
                "high": 70,
            },
            {
                "when": {"source": "patient.age_years", "op": "between", "min": 7, "max": 9},
                "text": "< 90 МЕ/мл",
                "low": None,
                "high": 90,
            },
            {
                "when": {"source": "patient.age_years", "op": "between", "min": 10, "max": 14},
                "text": "< 120 МЕ/мл",
                "low": None,
                "high": 120,
            },
            {
                "when": {"source": "patient.age_years", "op": "gte", "value": 15},
                "text": "< 130 МЕ/мл",
                "low": None,
                "high": 130,
            },
        ],
        "default": {"text": "< 130 МЕ/мл", "low": None, "high": 130},
    }


def _negative_text_flag_rule(
    field_key: str,
    negative_text: str,
    *,
    positive_flag: str = "critical",
) -> dict[str, Any]:
    return {
        "cases": [
            {
                "when": {
                    "source": f"field.{field_key}",
                    "op": "ineq",
                    "value": negative_text,
                },
                "flag": positive_flag,
            }
        ],
        "default": {"flag": None},
    }


def _single_catalog_template(
    *,
    code: str,
    name: str,
    family: str,
    description: str,
    document_title: str,
    document_subtitle: str,
    section_key: str,
    section_title: str,
    field_key: str,
    field_label: str,
    analyte_code: str,
    unit_code: str,
    unit: str,
    reference_text: str,
    footer_notes: str = "",
) -> dict[str, Any]:
    return _template(
        code=code,
        name=name,
        family=family,
        description=description,
        layout_preset="lab_table_classic_v1",
        document_title=document_title,
        document_subtitle=document_subtitle,
        footer_notes=footer_notes,
        sections=[
            _section(
                section_key,
                section_title,
                10,
                [
                    _field(
                        field_key,
                        field_label,
                        analyte_code=analyte_code,
                        unit_code=unit_code,
                        value_type="numeric",
                        unit=unit,
                        reference_mode="catalog",
                        reference_text=reference_text,
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    )
                ],
            )
        ],
    )


URINALYSIS_MICRO_ROWS = [
    ("leukocytes", "Лейкоцит"),
    ("epithelium", "Эпителий"),
    ("mucus", "Шиллиқ"),
    ("microflora", "Микрофлора"),
    ("trichomonas", "Трихомонада"),
    ("gonococci", "Гонококклар"),
    ("fungi", "Замбуруғлар"),
    ("gardnerella", "Гардинелла"),
    ("chlamydia", "Хламидия"),
]

SMEAR_SAMPLE_SITES = [
    ("urethra", "Сийдик йўли"),
    ("vagina", "Қин"),
    ("cervix", "Бачадон бўйни"),
]

SMEAR_POSITIVE_ROWS = {
    "trichomonas",
    "gonococci",
    "fungi",
    "gardnerella",
    "chlamydia",
}

SMEAR_ROW_CHOICES = {
    "leukocytes": ["Единичные", "Умеренно", "Много"],
    "epithelium": ["Единичные", "Умеренно", "Много"],
    "mucus": ["Нет", "Немного", "Много"],
    "microflora": ["Лактобациллярная", "Смешанная", "Кокковая"],
    "trichomonas": ["Бўлмайди", "Аниқланади"],
    "gonococci": ["Бўлмайди", "Аниқланади"],
    "fungi": ["Бўлмайди", "Аниқланади"],
    "gardnerella": ["Бўлмайди", "Аниқланади"],
    "chlamydia": ["Бўлмайди", "Аниқланади"],
}

SMEAR_ROW_REFERENCE_TEXTS = {
    "leukocytes": "Единичные",
    "epithelium": "Единичные",
    "mucus": "Нет",
    "microflora": "Лактобациллярная",
    "trichomonas": "Бўлмайди",
    "gonococci": "Бўлмайди",
    "fungi": "Бўлмайди",
    "gardnerella": "Бўлмайди",
    "chlamydia": "Бўлмайди",
}

TORCH_ANALYTES = [
    ("toxoplasma_gondii_igg", "Toxoplasma Gondii – IgG"),
    ("toxoplasma_gondii_igm", "Toxoplasma Gondii – IgM"),
    ("cytomegalovirus_igg", "Cytomegalovirus – IgG"),
    ("cytomegalovirus_igm", "Cytomegalovirus – IgM"),
    ("rubella_igg", "Rubella – IgG"),
    ("rubella_igm", "Rubella – IgM"),
    ("herpes_simplex_igg", "Herpes simplex 1/2 – IgG"),
    ("herpes_simplex_igm", "Herpes simplex 1/2 – IgM"),
    ("chlamidia_trachomatis_igg", "Chlamidia trachomatis – IgG"),
    ("chlamidia_trachomatis_igm", "Chlamidia trachomatis – IgM"),
    ("mycoplasma_hominis_igg", "Mycoplasma hominis – IgG"),
    ("mycoplasma_hominis_igm", "Mycoplasma hominis – IgM"),
    ("ureaplasma_urealyticum_igg", "Ureaplasma urealyticum – IgG"),
    ("ureaplasma_urealyticum_igm", "Ureaplasma urealyticum – IgM"),
]

HELMINTH_ROWS = [
    ("entamoeba_coli", "Цисты Entamoeba coli (Кишечная амёба)"),
    ("entamoeba_histolytica", "Цисты Entamoeba histolytica (амёба дизентерийная)"),
    ("lamblia_intestinalis", "Цисты Lamblia intestinalis (лямблия)"),
    ("enterobius_vermicularis", "Enterobius vermicularis (острица)"),
    ("ascaris_lumbricoides", "Ascaris lumbricoides (аскарида)"),
    ("ancylostoma_duodenale", "Ancylostoma duodenale (анкиластома)"),
    ("trichocephalus_trichiurus", "Trichosephalus trichiurus (власоглав)"),
    ("taenia_solium", "Taenia solium (свиной цепень)"),
    ("taenia_saginata", "Taenia saginata (бычий цепень)"),
    ("hymenolepis_nana", "Hymenolepis nana (карликовый цепень)"),
    ("diphyllobothrium_latum", "Diphyllobothrium latum (широкий цепень)"),
]

SIMPLE_POSITIVE_ROWS = [
    ("hbsag", "HBsAg"),
    ("hcv", "HCV"),
]

SYPHILIS_ROWS = [
    ("rw", "Rw"),
    ("hiv", "HIV"),
]

MICROBIOLOGY_ROWS = [
    ("demodex_folliculorum", "Demodex folliculorum"),
]

FUNGAL_ROWS = [
    ("fungal_hyphae", "Замбуруг ипчалари"),
]

MALASSEZIA_ROWS = [
    ("malassezia_furfur", "Malassezia furfur"),
]

EXTRA_LAB_TEMPLATE_DEFINITIONS: list[dict[str, Any]] = [
    _template(
        code="urinalysis_oam",
        name="ОАМ",
        family="urinalysis",
        description="Умумий сийдик таҳлили бланки.",
        layout_preset="lab_table_classic_v1",
        document_title="УМУМИЙ СИЙДИК ТАХЛИЛИ",
        document_subtitle="Тўрткўл автовокзал ёнида",
        branding_overrides={
            "address": "Турткул ш. Беруний кўчаси",
            "phone": "+998 91 266 66 86",
        },
        footer_notes="",
        signer_defaults={
            "lab_technician_name": "Ганжаев Н.",
        },
        sections=[
            _section(
                "oam_physical",
                "Физико-химические свойства",
                10,
                [
                    _field("volume", "Миқдори", value_type="numeric", unit="мл", sort_order=10),
                    _field("color", "Ранги", reference_text="Сариқ сомон ранг", sort_order=20),
                    _field("clarity", "Тиниқлиги", reference_text="Шаффоф", sort_order=30),
                    _field("leu_strip", "LEU / Лейкоцитлар", reference_text="Лейк/мкл", sort_order=40),
                    _field("nitrites", "NIT / Нитритлар", reference_text="Бўлмайди", sort_order=50),
                    _field("urobilinogen", "URO / Уробилиноген", reference_text="3.4 мкмоль/л гача", sort_order=60),
                    _field("protein", "PRO / Оқсил", reference_text="Бўлмайди, 0.033 гр/л гача", sort_order=70),
                    _field(
                        "ph",
                        "pH / Кислоталилиги",
                        analyte_code="urine_ph",
                        unit_code="ph",
                        value_type="numeric",
                        unit="pH",
                        reference_mode="catalog",
                        reference_text="4-7 рН",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=80,
                    ),
                    _field("blood", "BLD / Қон", reference_text="Бўлмайди", sort_order=90),
                    _field(
                        "specific_gravity",
                        "SG / Нисбий зичлиги",
                        analyte_code="urine_specific_gravity",
                        unit_code="sg",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="1015-1025 гр/литр",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=100,
                    ),
                    _field("ketones", "KET / Кетон таналар", reference_text="Бўлмайди", sort_order=110),
                    _field("bilirubin", "BIL / Билирубин", reference_text="Бўлмайди", sort_order=120),
                    _field("glucose", "GLU / Глюкоза", reference_text="Бўлмайди, %", sort_order=130),
                    _field("ascorbic_acid", "ASC / Аскорбин кислота", reference_text="0.28 ммоль/л", sort_order=140),
                    _field("bile_pigments", "Желчные пигменты", reference_text="Бўлмайди", sort_order=150),
                ],
                section_style={"render": "oam_docx"},
            ),
            _section(
                "oam_sediment",
                "Чўкма микроскопияси",
                20,
                [
                    _field(
                        "squamous_epithelium",
                        "Ясси эпителий",
                        analyte_code="urine_squamous_epithelium",
                        unit_code="cells_per_fov",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="2-2-2 та/кузатув майдонида",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    ),
                    _field(
                        "transitional_epithelium",
                        "Ўтиш эпителийси",
                        analyte_code="urine_transitional_epithelium",
                        unit_code="cells_per_fov",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="0-1 та/кузатув майдонида",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=20,
                    ),
                    _field("renal_epithelium", "Буйрак эпителийси", reference_text="Бўлмайди", sort_order=30),
                    _field(
                        "leukocytes",
                        "Лейкоцитлар",
                        analyte_code="urine_leukocytes",
                        unit_code="cells_per_fov",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="0-6 та/кузатув майдонида",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=40,
                    ),
                    _field(
                        "unmodified_erythrocytes",
                        "Ўзгармаган эритроцитлар",
                        analyte_code="urine_unmodified_erythrocytes",
                        unit_code="cells_per_fov",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="0-3 та/кузатув майдонида",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=50,
                    ),
                    _field("modified_erythrocytes", "Ўзгарган эритроцитлар", reference_text="Бўлмайди", sort_order=60),
                    _field("cylinders", "Цилиндрлар", reference_text="Бўлмайди", sort_order=70),
                    _field("bacteria", "Бактериялар", reference_text="Бўлмайди", sort_order=80),
                    _field("fungi", "Замбуруғлар", reference_text="Бўлмайди", sort_order=90),
                    _field("salts", "Тузлар", reference_text="Бўлмайди", sort_order=100),
                ],
                section_style={"render": "oam_docx"},
            ),
        ],
    ),
    _template(
        code="spermogramma",
        name="Спермограмма",
        family="andrology",
        description="Спермограмманинг клиник бланки.",
        layout_preset="lab_table_classic_v1",
        document_title="Спермограмма",
        document_subtitle="Andrologik tahlil",
        footer_notes="Материал: эякулят. Воздержание и подготовка должны быть соблюдены.",
        sections=[
            _section(
                "sperm_physical",
                "Физико-химические свойства",
                10,
                [
                    _field(
                        "volume",
                        "Объем",
                        analyte_code="volume",
                        unit_code="ml",
                        value_type="numeric",
                        unit="мл",
                        reference_mode="catalog",
                        reference_text="2-6 мл",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    ),
                    _field("color", "Цвет", reference_text="Молочно белая", sort_order=20),
                    _field("turbidity", "Мутность", reference_text="Мутный", sort_order=30),
                    _field("consistency", "Консистенция", reference_text="Тягучая", sort_order=40),
                    _field(
                        "viscosity",
                        "Вязкость",
                        analyte_code="viscosity",
                        unit_code="cm",
                        value_type="numeric",
                        unit="см",
                        reference_mode="catalog",
                        reference_text="0,1-0,5 см",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=50,
                    ),
                    _field(
                        "liquefaction_time",
                        "Время разжижения",
                        analyte_code="liquefaction_time",
                        unit_code="min",
                        value_type="numeric",
                        unit="мин",
                        reference_mode="catalog",
                        reference_text="20-30 мин",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=60,
                    ),
                    _field(
                        "ph",
                        "pH",
                        analyte_code="ph",
                        unit_code="ph",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="7,2-8,0",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=70,
                    ),
                ],
            ),
            _section(
                "spermatozoa",
                "СПЕРМАТОЗОИДЫ",
                20,
                [
                    _field(
                        "actively_motile",
                        "Активно подвижные",
                        analyte_code="actively_motile",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="70%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    ),
                    _field(
                        "slowly_motile",
                        "Слабо подвижные",
                        analyte_code="slowly_motile",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="4-30%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=20,
                    ),
                    _field(
                        "immobile",
                        "Не подвижные",
                        analyte_code="immobile",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="0-14%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=30,
                    ),
                    _field(
                        "alive",
                        "Кол-во живых сперматозоидов",
                        analyte_code="alive",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="80-90%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=40,
                    ),
                    _field(
                        "dead",
                        "Кол-во мертвых сперматозоидов",
                        analyte_code="dead",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="10-20%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=50,
                    ),
                    _field(
                        "count_per_ml",
                        "Кол-во в 1 мл",
                        analyte_code="count_per_ml",
                        unit_code="million_per_ml",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="60-150 млн",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=60,
                    ),
                ],
            ),
            _section(
                "morphology",
                "МОРФОЛОГИЧЕСКИ",
                30,
                [
                    _field(
                        "normal_forms",
                        "Нормальные",
                        analyte_code="normal_forms",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="≥81%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    ),
                    _field(
                        "changed_forms",
                        "Измененные",
                        analyte_code="changed_forms",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="≤19%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=20,
                    ),
                ],
            ),
            _section(
                "pathology",
                "ПАТОЛОГИЯ",
                40,
                [
                    _field(
                        "heads",
                        "Головки",
                        analyte_code="heads",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="≤15%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    ),
                    _field(
                        "bodies",
                        "Тела",
                        analyte_code="bodies",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="≤2%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=20,
                    ),
                    _field(
                        "tails",
                        "Хвоста",
                        analyte_code="tails",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="≤2%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=30,
                    ),
                    _field(
                        "spermatogenesis_cells",
                        "Клетки сперматогенеза",
                        analyte_code="spermatogenesis_cells",
                        unit_code="percent",
                        value_type="numeric",
                        unit="%",
                        reference_mode="catalog",
                        reference_text="1-2%",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=40,
                    ),
                    _field("leukocytes", "Лейкоциты", reference_text="0-3", sort_order=50),
                    _field("erythrocytes", "Эритроциты", reference_text="0-1", sort_order=60),
                    _field("epithelium", "Эпителий", reference_text="0-1", sort_order=70),
                    _field("bethers_crystals", "Кристаллы Бетхера", reference_text="отсутствует", sort_order=80),
                    _field("microflora", "Микрофлора", reference_text="отсутствует", sort_order=90),
                    _field("fungal_spores", "Споры патогенных грибков", reference_text="отсутствует", sort_order=100),
                    _field("agglutination", "Спермаглютинация", reference_text="Нет", sort_order=110),
                    _field("aggregate", "Агрегат", reference_text="нет", sort_order=120),
                    _field("lecithin_granules", "Лецитиновые зерна", reference_text="Густо(+++)", sort_order=130),
                    _field("macrophage", "Макрофаг", reference_text="нет", sort_order=140),
                ],
            ),
        ],
    ),
    _template(
        code="ige_total",
        name="Иммуноглобулин Е (IgE)",
        family="allergy",
        description="Возраст-зависимый IgE бланк.",
        layout_preset="lab_table_compact_v1",
        document_title="Иммуноглобулин E",
        document_subtitle="IgE",
        footer_notes="Норма зависит от возраста пациента.",
        sections=[
            _section(
                "ige_main",
                "Беморнинг  ёши",
                10,
                [
                    _field(
                        "total_ige",
                        "Натижа",
                        analyte_code="total_ige",
                        unit_code="me_per_ml",
                        value_type="numeric",
                        unit="МЕ/мл",
                        reference_mode="catalog",
                        reference_text="< 130 МЕ/мл",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    )
                ],
            ),
        ],
    ),
    _template(
        code="revmoprobe",
        name="РЕВМОПРОБА",
        family="immunology",
        description="Иммунологический экспресс-бланк.",
        layout_preset="lab_table_classic_v1",
        document_title="Иммунологик текширув",
        document_subtitle="ЭКСПРЕСС ТЕСТ",
        footer_notes="Экспресс-тест панель.",
        sections=[
            _section(
                "rheum_screen",
                "Тахлил номи",
                10,
                [
                    _field("crp", "С-РЕАКТИВ ОКСИЛ (СРБ)", reference_text="АНИКЛАНМАЙДИ", sort_order=10),
                    _field("rf", "РЕВМАТОИД ФАКТОР (РФ)", reference_text="АНИКЛАНМАЙДИ", sort_order=20),
                    _field("aslo", "АНТИСТРЕПТОЛИЗИН-О(АСЛО)", reference_text="АНИКЛАНМАЙДИ", sort_order=30),
                    _field("brucellosis", "БРУЦЕЛЛЕЗ", reference_text="АНИКЛАНМАЙДИ", sort_order=40),
                ],
            )
        ],
    ),
    _template(
        code="glucose_panel",
        name="Сахар",
        family="biochemistry",
        description="Экспресс-бланк глюкозы крови.",
        layout_preset="lab_table_classic_v1",
        document_title="Сахар крови",
        document_subtitle="Глюкоза",
        footer_notes="Экспресс-тест бланки.",
        sections=[
            _section(
                "glucose_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "glucose",
                        "Сахар",
                        analyte_code="glucose",
                        unit_code="mmol_per_l",
                        value_type="numeric",
                        unit="ммоль/л",
                        reference_mode="catalog",
                        reference_text="3.3 - 5.5 ммоль/л",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    )
                ],
            )
        ],
    ),
    _template(
        code="glucose_coag_panel",
        name="Сахар, свёрт",
        family="hemostasis",
        description="Сахар и свертываемость крови по Сухареву.",
        layout_preset="lab_table_classic_v1",
        document_title="Сахар и свертываемость",
        document_subtitle="По Сухареву",
        footer_notes="Панель объединяет глюкозу и свертываемость крови.",
        sections=[
            _section(
                "glucose_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "glucose",
                        "Сахар",
                        analyte_code="glucose",
                        unit_code="mmol_per_l",
                        value_type="numeric",
                        unit="ммоль/л",
                        reference_mode="catalog",
                        reference_text="3.3 - 5.5",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    )
                ],
            ),
            _section(
                "coag_sukharev",
                "Сверт. Крови (по Сухареву)",
                20,
                [
                    _field("start_time", "Начало", reference_text="30сек-2мин", sort_order=10),
                    _field("end_time", "Конец", reference_text="3-5 мин", sort_order=20),
                ],
            ),
        ],
    ),
    _single_catalog_template(
        code="vitamin_d_panel",
        name="Vitamin D",
        family="endocrinology",
        description="Бланк 25-OH Vitamin D.",
        document_title="Vitamin D",
        document_subtitle="25-OH Vitamin D",
        section_key="vitamin_d_main",
        section_title="Тахлил номи",
        field_key="vitamin_d_25_hydroxy",
        field_label="Vitamin D (25-OH)",
        analyte_code="vitamin_d_25_hydroxy",
        unit_code="ng_per_ml",
        unit="ng/mL",
        reference_text="30 - 100 ng/mL",
        footer_notes="Референс можно скорректировать в редакторе шаблона под локальный SOP лаборатории.",
    ),
    _single_catalog_template(
        code="hba1c_panel",
        name="HbA1c",
        family="glycemic",
        description="Бланк гликированного гемоглобина.",
        document_title="HbA1c",
        document_subtitle="Гликированный гемоглобин",
        section_key="hba1c_main",
        section_title="Тахлил номи",
        field_key="hba1c",
        field_label="Гликированный гемоглобин (HbA1c)",
        analyte_code="hba1c",
        unit_code="percent",
        unit="%",
        reference_text="4.8 - 5.6 %",
        footer_notes="Пороговые значения для предиабета и диабета можно уточнить в комментарии шаблона.",
    ),
    _template(
        code="thyroid_hormones",
        name="Гармон",
        family="endocrinology",
        description="Гормоны щитовидной железы.",
        layout_preset="lab_table_classic_v1",
        document_title="Гормоны щитовидной железы",
        document_subtitle="ТТГ / Т3 / Т4 / АТ-ТПО",
        sections=[
            _section(
                "thyroid_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "t3_free",
                        "Трийодтиронин (Т3) (свободно)",
                        analyte_code="t3_free",
                        unit_code="pmol_per_l",
                        value_type="numeric",
                        unit="pmol/L",
                        reference_mode="catalog",
                        reference_text="1,03-4,03",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=10,
                    ),
                    _field(
                        "t4_total",
                        "Тироксин (Т4) (общий)",
                        analyte_code="t4_total",
                        unit_code="nmol_per_l",
                        value_type="numeric",
                        unit="nmol/L",
                        reference_mode="catalog",
                        reference_text="4,71-10,73",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=20,
                    ),
                    _field(
                        "tsh",
                        "Тиреотропный гормон (ТТГ)",
                        analyte_code="tsh",
                        unit_code="miu_per_l",
                        value_type="numeric",
                        unit="mIU/L",
                        reference_mode="catalog",
                        reference_text="0,32-6,58",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=30,
                    ),
                    _field(
                        "at_tpo",
                        "Аутоантитела к тиреопероксидазе (АТ-ТПО)",
                        analyte_code="at_tpo",
                        unit_code="iu_per_ml",
                        value_type="numeric",
                        unit="IU/mL",
                        reference_mode="catalog",
                        reference_text="0-45",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=40,
                    ),
                ],
            )
        ],
    ),
    _single_catalog_template(
        code="testosterone_panel",
        name="Testosterone",
        family="endocrinology",
        description="Бланк общего тестостерона.",
        document_title="Testosterone",
        document_subtitle="Total Testosterone",
        section_key="testosterone_main",
        section_title="Тахлил номи",
        field_key="testosterone_total",
        field_label="Тестостерон (общий)",
        analyte_code="testosterone_total",
        unit_code="nmol_per_l",
        unit="nmol/L",
        reference_text="Эр: 9.16 - 31.80 / Аёл: 0.35 - 1.91 nmol/L",
        footer_notes="Референс зависит от пола пациента и при необходимости корректируется через редактор шаблона.",
    ),
    _template(
        code="hepatitis_bs",
        name="гепатит Б.С",
        family="infectious",
        description="HBsAg / HCV экспресс-бланк.",
        layout_preset="lab_table_classic_v1",
        document_title="Гепатит B/C",
        document_subtitle="HBsAg / HCV",
        sections=[
            _section(
                "hepatitis_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "hbsag",
                        "HBsAg",
                        reference_text="Аникланмайди",
                        highlight_rule=_negative_text_flag_rule("hbsag", "Аникланмайди"),
                        sort_order=10,
                    ),
                    _field(
                        "hcv",
                        "HCV",
                        reference_text="Аникланмайди",
                        highlight_rule=_negative_text_flag_rule("hcv", "Аникланмайди"),
                        sort_order=20,
                    ),
                ],
            )
        ],
    ),
    _template(
        code="helminth_panel",
        name="Гижжа бланка",
        family="parasitology",
        description="Кал на я/г панель.",
        layout_preset="lab_table_compact_v1",
        document_title="Гижжа бланка",
        document_subtitle="Паразитология",
        sections=[
            _section(
                "helminth_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        key,
                        label,
                        reference_text="Бўлмайди",
                        highlight_rule=_negative_text_flag_rule(key, "Бўлмайди"),
                        sort_order=(index + 1) * 10,
                    )
                    for index, (key, label) in enumerate(HELMINTH_ROWS)
                ],
            )
        ],
    ),
    _template(
        code="smear_cleanliness",
        name="Мазок",
        family="gynecology",
        description="Мазок на степень чистоты.",
        layout_preset="lab_table_compact_v1",
        document_title="СУРТМА ТАХЛИЛИ (степень чистоты)",
        document_subtitle="",
        sections=[
            _section(
                site_key,
                site_title,
                (index + 1) * 10,
                [
                    _field(
                        f"{site_key}_{row_key}",
                        row_label,
                        value_type="choice",
                        choice_options=SMEAR_ROW_CHOICES[row_key],
                        reference_text=SMEAR_ROW_REFERENCE_TEXTS[row_key],
                        highlight_rule=(
                            _negative_text_flag_rule(f"{site_key}_{row_key}", "Бўлмайди")
                            if row_key in SMEAR_POSITIVE_ROWS
                            else None
                        ),
                        sort_order=(row_index + 1) * 10,
                    )
                    for row_index, (row_key, row_label) in enumerate(URINALYSIS_MICRO_ROWS)
                ],
                section_style={"render": "smear_matrix", "copy_count": 2},
            )
            for index, (site_key, site_title) in enumerate(SMEAR_SAMPLE_SITES)
        ],
    ),
    _template(
        code="syphilis_hiv",
        name="Сифилис ОИВбланк",
        family="infectious",
        description="Rw / HIV экспресс-бланк.",
        layout_preset="lab_table_classic_v1",
        document_title="Сифилис / HIV",
        document_subtitle="Экспресс тест",
        sections=[
            _section(
                "syphilis_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "rw",
                        "Rw",
                        reference_text="Аникланмайди",
                        highlight_rule=_negative_text_flag_rule("rw", "Аникланмайди"),
                        sort_order=10,
                    ),
                    _field(
                        "hiv",
                        "HIV",
                        reference_text="Аникланмайди",
                        highlight_rule=_negative_text_flag_rule("hiv", "Аникланмайди"),
                        sort_order=20,
                    ),
                ],
            )
        ],
    ),
    _template(
        code="torch_panel",
        name="торч инфекция",
        family="infectious",
        description="TORCH инфекция серологияси.",
        layout_preset="lab_table_compact_v1",
        document_title="TORCH инфекция",
        document_subtitle="IgG / IgM",
        sections=[
            _section(
                "torch_main",
                "№ / ТАХЛИЛ НОМИ",
                10,
                [
                    _field(
                        key,
                        label,
                        analyte_code=key,
                        unit_code="index",
                        value_type="numeric",
                        reference_mode="catalog",
                        reference_text="0.90",
                        highlight_rule={"mode": "rule_based_reference"},
                        sort_order=(index + 1) * 10,
                    )
                    for index, (key, label) in enumerate(TORCH_ANALYTES)
                ],
            )
        ],
    ),
    _template(
        code="demodex_panel",
        name="Демодекоз",
        family="parasitology",
        description="Demodex folliculorum bланки.",
        layout_preset="lab_table_classic_v1",
        document_title="Демодекоз",
        document_subtitle="Demodex folliculorum",
        sections=[
            _section(
                "demodex_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "demodex_folliculorum",
                        "Demodex folliculorum",
                        reference_text="Аникланмайди",
                        highlight_rule=_negative_text_flag_rule("demodex_folliculorum", "Аникланмайди"),
                        sort_order=10,
                    ),
                ],
            )
        ],
    ),
    _template(
        code="fungal_hyphae_panel",
        name="Нити грибки",
        family="mycology",
        description="Замбуруг ипчалари бланки.",
        layout_preset="lab_table_classic_v1",
        document_title="Нити грибки",
        document_subtitle="Микология",
        sections=[
            _section(
                "fungal_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "fungal_hyphae",
                        "Замбуруг ипчалари",
                        reference_text="аникланмайди",
                        highlight_rule=_negative_text_flag_rule("fungal_hyphae", "аникланмайди"),
                        sort_order=10,
                    ),
                ],
            )
        ],
    ),
    _template(
        code="malassezia_panel",
        name="Malassezia furfur",
        family="mycology",
        description="Malassezia furfur микологик бланк.",
        layout_preset="lab_table_classic_v1",
        document_title="Malassezia furfur",
        document_subtitle="Таҳлил",
        sections=[
            _section(
                "malassezia_main",
                "Тахлил номи",
                10,
                [
                    _field(
                        "malassezia_furfur",
                        "Malassezia furfur",
                        reference_text="аникланмайди",
                        highlight_rule=_negative_text_flag_rule("malassezia_furfur", "аникланмайди"),
                        sort_order=10,
                    ),
                ],
            )
        ],
    ),
]
