"""Parity checks for RegistrarPanel service-code category logic."""


def get_service_category_by_code(service_code: str | None) -> str | None:
    """Mirror RegistrarPanel.getServiceCategoryByCode for critical code contracts."""
    if not service_code:
        return None

    normalized_code = str(service_code).upper()

    if normalized_code in {"K002", "ECG01"}:
        return "ECG"
    if normalized_code == "K11":
        return "ECHO"
    if (
        normalized_code == "K10"
        or normalized_code == "CARD_ECG"
        or "ECG" in normalized_code
        or "ЭКГ" in normalized_code
    ):
        return "ECG"
    if normalized_code == "CARD_ECHO" or "ECHO" in normalized_code or "ЭХОКГ" in normalized_code:
        return "ECHO"
    if normalized_code.startswith("P") and normalized_code[1:].isdigit():
        return "P"
    if normalized_code.startswith("D_PROC") and normalized_code[6:].isdigit():
        return "D_PROC"
    if normalized_code.startswith("C") and normalized_code[1:].isdigit():
        return "C"
    if normalized_code.startswith("K") and normalized_code[1:].isdigit() and normalized_code != "K10":
        return "K"
    if normalized_code.startswith("S") and normalized_code[1:].isdigit():
        return "S"
    if normalized_code.startswith("L") and normalized_code[1:].isdigit():
        return "L"
    if normalized_code == "D01":
        return "D"
    if normalized_code.startswith("CONS_CARD"):
        return "K"
    if normalized_code.startswith("CONS_DERM") or normalized_code.startswith("DERMA_"):
        return "D"
    if (
        normalized_code.startswith("CONS_DENT")
        or normalized_code.startswith("DENT_")
        or normalized_code.startswith("STOM_")
    ):
        return "S"
    if normalized_code.startswith("LAB_"):
        return "L"
    if normalized_code.startswith("COSM_"):
        return "C"
    if normalized_code.startswith("PHYSIO_"):
        return "P"
    if normalized_code.startswith("DERM_PROC_"):
        return "D_PROC"
    if normalized_code.startswith("CARD_") and "ECG" not in normalized_code:
        return "K"

    return None


def test_frontend_logic_keeps_ecg_canonical_and_legacy_aliases() -> None:
    assert get_service_category_by_code("K10") == "ECG"
    assert get_service_category_by_code("K002") == "ECG"
    assert get_service_category_by_code("ECG01") == "ECG"
    assert get_service_category_by_code("CARD_ECG") == "ECG"
    assert get_service_category_by_code("legacy_ecg") == "ECG"


def test_frontend_logic_keeps_echo_canonical_before_generic_k_codes() -> None:
    assert get_service_category_by_code("K11") == "ECHO"
    assert get_service_category_by_code("CARD_ECHO") == "ECHO"
    assert get_service_category_by_code("legacy_echo") == "ECHO"
    assert get_service_category_by_code("K01") == "K"


def test_frontend_logic_keeps_other_department_categories() -> None:
    assert get_service_category_by_code("P01") == "P"
    assert get_service_category_by_code("C01") == "C"
    assert get_service_category_by_code("D_PROC01") == "D_PROC"
    assert get_service_category_by_code("D01") == "D"
    assert get_service_category_by_code("S01") == "S"
    assert get_service_category_by_code("L01") == "L"
    assert get_service_category_by_code(None) is None
