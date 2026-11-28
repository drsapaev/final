"""Clinic-neutral parsing contracts for laboratory instrument messages.

Adapters only parse protocol structure. They deliberately ignore patient identity
segments and never persist raw messages. A trusted application workflow must still
resolve the target report; the canonical import service then checks the exact
accepted specimen barcode, analyte, unit, method, and idempotency receipt.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Mapping, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas.lab_import import LabImportRow, LabImportValue

MAX_ANALYZER_MESSAGE_BYTES = 1_000_000
MAX_ANALYZER_RESULTS = 100
MAX_INSTRUMENT_FLAGS = 16
_SAFE_MAPPING_CODE = re.compile(r"^[A-Za-z0-9_.%/^-]{1,64}$")


class AnalyzerAdapterError(ValueError):
    """A bounded error code that never includes source message content."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AnalyzerObservation:
    source_analyte_code: str = field(repr=False)
    raw_value: str = field(repr=False)
    source_unit_code: str = field(default="", repr=False)
    instrument_flags: tuple[str, ...] = field(default=(), repr=False)
    value_type: str = ""


@dataclass(frozen=True, slots=True)
class ParsedAnalyzerMessage:
    adapter_key: str
    message_token: str = field(repr=False)
    accession_id: str = field(repr=False)
    specimen_id: str = field(repr=False)
    observations: tuple[AnalyzerObservation, ...] = field(repr=False)


class AnalyzerMessageAdapter(Protocol):
    adapter_key: str

    def parse(self, payload: str | bytes) -> ParsedAnalyzerMessage: ...


def _decode(payload: str | bytes) -> str:
    if isinstance(payload, bytes):
        if len(payload) > MAX_ANALYZER_MESSAGE_BYTES:
            raise AnalyzerAdapterError("message_too_large")
        try:
            decoded = payload.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise AnalyzerAdapterError("invalid_encoding") from exc
    elif isinstance(payload, str):
        if len(payload.encode("utf-8")) > MAX_ANALYZER_MESSAGE_BYTES:
            raise AnalyzerAdapterError("message_too_large")
        decoded = payload
    else:
        raise AnalyzerAdapterError("invalid_message_type")
    if not decoded or any(ord(char) < 32 and char not in "\r\n\t" for char in decoded):
        raise AnalyzerAdapterError("invalid_control_character")
    return decoded


def _components(value: str, separator: str) -> str:
    """Return the coded identifier component; never use its display label."""
    return value.split(separator, 1)[0].strip()


def _instrument_flags(value: str, repetition: str = "~") -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in value.split(repetition) if token.strip())
    if len(tokens) > MAX_INSTRUMENT_FLAGS or any(
        not _SAFE_MAPPING_CODE.fullmatch(token) for token in tokens
    ):
        raise AnalyzerAdapterError("invalid_instrument_flags")
    return tokens


def _message_uuid(
    message: ParsedAnalyzerMessage, *, profile_version_id: int | None = None
) -> UUID:
    """Stable key used by the existing import receipt to reject replays/conflicts."""
    token = message.message_token or hashlib.sha256(
        "\x1e".join(
            [
                message.accession_id,
                message.specimen_id,
                *(
                    f"{item.source_analyte_code}\x1f{item.raw_value}\x1f"
                    f"{item.source_unit_code}\x1f{'~'.join(item.instrument_flags)}"
                    for item in message.observations
                ),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return uuid5(
        NAMESPACE_URL,
        f"final-clinic-lab:{message.adapter_key}:{profile_version_id or 'unresolved'}:{token}",
    )


class ASTMCLSIAdapter:
    """Parser for ASTM/CLSI record payloads after transport framing validation.

    This adapter accepts one H/P/O/R/L record sequence. TCP/serial frame bytes,
    sequence numbers, and checksums belong to the selected transport driver; a
    driver must validate those before passing the decoded record body here.
    """

    adapter_key = "astm_clsi"

    def parse(self, payload: str | bytes) -> ParsedAnalyzerMessage:
        text = _decode(payload)
        records = [line.strip() for line in text.replace("\n", "\r").split("\r") if line.strip()]
        if not records or records[0].split("|", 1)[0] != "H":
            raise AnalyzerAdapterError("invalid_astm_header")

        orders: list[list[str]] = []
        observations: list[AnalyzerObservation] = []
        current_order: list[str] | None = None
        for record in records:
            fields = record.split("|")
            kind = fields[0]
            if kind == "O":
                orders.append(fields)
                current_order = fields
            elif kind == "R":
                if current_order is None or len(fields) < 4:
                    raise AnalyzerAdapterError("result_without_order")
                test_id = fields[2].strip()
                components = test_id.split("^")
                source_code = (
                    components[3].strip()
                    if len(components) > 3 and components[3].strip()
                    else next((item.strip() for item in components if item.strip()), "")
                )
                raw_value = fields[3].strip()
                if not source_code or not raw_value:
                    raise AnalyzerAdapterError("invalid_result_record")
                unit = fields[4].strip() if len(fields) > 4 else ""
                flags = _instrument_flags(fields[6]) if len(fields) > 6 else ()
                observations.append(
                    AnalyzerObservation(
                        source_analyte_code=source_code,
                        raw_value=raw_value,
                        source_unit_code=unit,
                        instrument_flags=flags,
                    )
                )
            elif kind not in {"H", "P", "C", "L"}:
                raise AnalyzerAdapterError("unsupported_astm_record")

        if len(orders) != 1:
            raise AnalyzerAdapterError("expected_single_astm_order")
        order = orders[0]
        specimen_id = order[2].strip() if len(order) > 2 else ""
        accession_id = order[3].strip() if len(order) > 3 and order[3].strip() else specimen_id
        if not specimen_id or not accession_id or not observations:
            raise AnalyzerAdapterError("incomplete_astm_message")
        if len(observations) > MAX_ANALYZER_RESULTS:
            raise AnalyzerAdapterError("too_many_results")

        header = records[0].split("|")
        control_id = header[10].strip() if len(header) > 10 else ""
        message = ParsedAnalyzerMessage(
            adapter_key=self.adapter_key,
            message_token=control_id,
            accession_id=accession_id,
            specimen_id=specimen_id,
            observations=tuple(observations),
        )
        if not control_id:
            message = ParsedAnalyzerMessage(
                adapter_key=self.adapter_key,
                message_token=_message_uuid(message).hex,
                accession_id=message.accession_id,
                specimen_id=message.specimen_id,
                observations=message.observations,
            )
        return message


class HL7V2ORUAdapter:
    """Parser for the clinic-neutral HL7 v2 ORU^R01 result subset.

    PID, PV1, and other patient-demographic segments are intentionally ignored.
    Exactly one order group and specimen are accepted to avoid ambiguous import.
    """

    adapter_key = "hl7_v2"

    def parse(self, payload: str | bytes) -> ParsedAnalyzerMessage:
        text = _decode(payload)
        segments = [line for line in re.split(r"\r\n|\r|\n", text) if line]
        if not segments or not segments[0].startswith("MSH") or len(segments[0]) < 4:
            raise AnalyzerAdapterError("invalid_hl7_header")
        field_separator = segments[0][3]
        if field_separator.isalnum() or field_separator.isspace():
            raise AnalyzerAdapterError("invalid_hl7_delimiters")
        msh = segments[0].split(field_separator)
        if len(msh) < 10:
            raise AnalyzerAdapterError("invalid_hl7_header")
        encoding_chars = msh[1]
        if len(encoding_chars) < 4:
            raise AnalyzerAdapterError("invalid_hl7_delimiters")
        component_separator = encoding_chars[0]
        repetition_separator = encoding_chars[1]
        message_type = msh[8].split(component_separator)
        if message_type[:2] != ["ORU", "R01"]:
            raise AnalyzerAdapterError("unsupported_hl7_message_type")
        control_id = msh[9].strip()
        if not control_id:
            raise AnalyzerAdapterError("missing_hl7_control_id")

        order_segments = []
        specimen_segments = []
        observations = []
        for segment in segments[1:]:
            fields = segment.split(field_separator)
            kind = fields[0]
            if kind == "OBR":
                order_segments.append(fields)
            elif kind == "SPM":
                specimen_segments.append(fields)
            elif kind == "OBX":
                if len(fields) <= 8:
                    raise AnalyzerAdapterError("invalid_hl7_observation")
                value_type = fields[2].strip().upper()
                if value_type not in {"NM", "SN", "ST", "TX", "FT", "CE", "CWE"}:
                    raise AnalyzerAdapterError("unsupported_hl7_value_type")
                source_code = _components(fields[3], component_separator)
                raw_value = fields[5].strip()
                if not source_code or not raw_value or repetition_separator in raw_value:
                    raise AnalyzerAdapterError("invalid_hl7_observation")
                unit = _components(fields[6], component_separator)
                flags = _instrument_flags(fields[8], repetition_separator)
                observations.append(
                    AnalyzerObservation(
                        source_analyte_code=source_code,
                        raw_value=raw_value,
                        source_unit_code=unit,
                        instrument_flags=flags,
                        value_type=value_type,
                    )
                )

        if len(order_segments) != 1 or len(specimen_segments) != 1:
            raise AnalyzerAdapterError("expected_single_hl7_order_and_specimen")
        obr = order_segments[0]
        placer_order = _components(obr[2], component_separator) if len(obr) > 2 else ""
        filler_order = _components(obr[3], component_separator) if len(obr) > 3 else ""
        accession_id = filler_order or placer_order
        spm = specimen_segments[0]
        specimen_id = _components(spm[2], component_separator) if len(spm) > 2 else ""
        if not accession_id or not specimen_id or not observations:
            raise AnalyzerAdapterError("incomplete_hl7_message")
        if len(observations) > MAX_ANALYZER_RESULTS:
            raise AnalyzerAdapterError("too_many_results")
        return ParsedAnalyzerMessage(
            adapter_key=self.adapter_key,
            message_token=control_id,
            accession_id=accession_id,
            specimen_id=specimen_id,
            observations=tuple(observations),
        )


class AnalyzerAdapterRegistry:
    """Extensible registry; protocol and vendor adapters register by stable key."""

    def __init__(self) -> None:
        self._adapters: dict[str, AnalyzerMessageAdapter] = {}

    def register(self, adapter: AnalyzerMessageAdapter) -> None:
        key = adapter.adapter_key.strip().lower()
        if not key or key in self._adapters:
            raise ValueError("adapter_key_must_be_unique")
        self._adapters[key] = adapter

    def get(self, adapter_key: str) -> AnalyzerMessageAdapter:
        try:
            return self._adapters[adapter_key.strip().lower()]
        except KeyError as exc:
            raise AnalyzerAdapterError("unsupported_adapter") from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


class AnalyzerMappingProfile:
    """Explicit, exact-code mappings supplied by an approved clinic profile."""

    def __init__(
        self,
        *,
        analyte_codes: Mapping[str, str],
        unit_codes: Mapping[tuple[str, str], str | None],
        flag_codes: Mapping[str, str] | None = None,
        specimen_id_source: str = "specimen_id",
    ) -> None:
        self.analyte_codes = dict(analyte_codes)
        self.unit_codes = dict(unit_codes)
        self.flag_codes = dict(flag_codes or {})
        if not isinstance(specimen_id_source, str) or specimen_id_source not in {
            "specimen_id", "accession_id"
        }:
            raise ValueError("invalid_specimen_id_source")
        self.specimen_id_source = specimen_id_source

    def specimen_barcode(self, message: ParsedAnalyzerMessage) -> str:
        """Select one parsed identifier exactly; never guess or fall back."""
        selected = getattr(message, self.specimen_id_source)
        if not isinstance(selected, str) or not selected:
            raise AnalyzerAdapterError("selected_specimen_id_missing")
        if len(selected) > 24:
            raise AnalyzerAdapterError("specimen_identifier_too_long")
        return selected

    def map_values(
        self, message: ParsedAnalyzerMessage, *, method_code: str | None = None
    ) -> list[LabImportValue]:
        mapped: list[LabImportValue] = []
        for observation in message.observations:
            target_analyte = self.analyte_codes.get(observation.source_analyte_code)
            if not target_analyte:
                raise AnalyzerAdapterError("unmapped_analyte_code")
            if observation.source_unit_code:
                unit_key = (observation.source_analyte_code, observation.source_unit_code)
                if unit_key not in self.unit_codes:
                    raise AnalyzerAdapterError("unmapped_unit_code")
                target_unit = self.unit_codes[unit_key]
            else:
                target_unit = self.unit_codes.get((observation.source_analyte_code, ""))
            flags = tuple(
                self.flag_codes.get(code, code) for code in observation.instrument_flags
            )
            if len(flags) > MAX_INSTRUMENT_FLAGS:
                raise AnalyzerAdapterError("invalid_instrument_flags")
            value = LabImportValue(
                analyte_code=target_analyte,
                value_text=observation.raw_value,
                unit_code=target_unit,
                method_code=method_code,
                instrument_flags=list(flags),
            )
            value._source_analyte_code = observation.source_analyte_code
            value._source_instrument_flags = observation.instrument_flags
            mapped.append(value)
        return mapped


def to_lab_import_row(
    message: ParsedAnalyzerMessage,
    mapping: AnalyzerMappingProfile,
    *,
    report_instance_id: int,
    method_code: str | None = None,
    expected_updated_at=None,
    profile_version_id: int | None = None,
) -> LabImportRow:
    """Build a canonical import row after trusted report resolution.

    The caller must resolve ``report_instance_id`` from authenticated clinic
    context. This function never uses analyzer-supplied patient identifiers or
    fuzzy accession matching. The existing import service still checks that the
    exact specimen barcode belongs to this report and is accepted.
    """
    return LabImportRow(
        message_id=_message_uuid(message, profile_version_id=profile_version_id),
        report_instance_id=report_instance_id,
        specimen_barcode=mapping.specimen_barcode(message),
        expected_updated_at=expected_updated_at,
        method_code=method_code,
        values=mapping.map_values(message, method_code=method_code),
    )


ANALYZER_ADAPTERS = AnalyzerAdapterRegistry()
ANALYZER_ADAPTERS.register(ASTMCLSIAdapter())
ANALYZER_ADAPTERS.register(HL7V2ORUAdapter())


__all__ = [
    "ANALYZER_ADAPTERS",
    "ASTMCLSIAdapter",
    "AnalyzerAdapterError",
    "AnalyzerAdapterRegistry",
    "AnalyzerMappingProfile",
    "AnalyzerObservation",
    "HL7V2ORUAdapter",
    "ParsedAnalyzerMessage",
    "to_lab_import_row",
]
