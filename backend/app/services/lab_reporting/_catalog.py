"""Catalog mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class CatalogMixin(LabReportingServiceMixinBase):
    """Catalog methods for LabReportingService."""

    def list_catalog_units(self) -> list[LabCatalogUnit]:
        logger.info("[LAB] list_catalog_units")
        self.ensure_default_catalog()
        return self.repository.list_catalog_units()


    def list_catalog_analytes(
        self, *, category: str | None = None
    ) -> list[LabCatalogAnalyte]:
        logger.info("[LAB] list_catalog_analytes category=%s", category)
        self.ensure_default_catalog()
        return self.repository.list_catalog_analytes(category=category)


    def list_catalog_reference_ranges(
        self, *, analyte_code: str | None = None
    ) -> list[LabCatalogReferenceRange]:
        logger.info("[LAB] list_catalog_reference_ranges analyte_code=%s", analyte_code)
        self.ensure_default_catalog()
        return self.repository.list_catalog_reference_ranges(analyte_code=analyte_code)


    def ensure_default_catalog(self) -> None:
        from app.services.lab_reporting._base import (
            _SEED_LOCK,
            _mark_seed_ensured,
            _seed_cache_fresh,
        )

        bind = self.repository.db.get_bind()
        with _SEED_LOCK:
            if not _seed_cache_fresh(bind, "catalog"):
                return
            logger.info("[LAB] ensure_default_catalog seeding analytes/units/reference ranges")
            touched = 0

            # Perf (#2977): probe each table once and diff in memory. The previous
            # row-by-row get_catalog_unit/get_catalog_analyte probes plus a
            # per-analyte range listing cost ~80 sequential roundtrips to the
            # remote Postgres on EVERY read (>20s per GET /lab/templates).
            # Seeding semantics (create missing, refresh drifted rows) unchanged.
            existing_units = {
                unit.code: unit for unit in self.repository.list_catalog_units()
            }
            for definition in DEFAULT_LAB_UNIT_DEFINITIONS:
                unit = existing_units.get(definition["code"])
                if unit is None:
                    unit = LabCatalogUnit(
                        code=definition["code"],
                        name=definition["name"],
                        symbol=definition["symbol"],
                        sort_order=definition.get("sort_order", 0),
                        is_active=definition.get("is_active", True),
                    )
                    self.repository.add_catalog_unit(unit)
                else:
                    unit.name = definition["name"]
                    unit.symbol = definition["symbol"]
                    unit.sort_order = definition.get("sort_order", 0)
                    unit.is_active = definition.get("is_active", True)
                self._catalog_unit_cache[unit.code] = unit
                touched += 1

            existing_analytes = {
                analyte.code: analyte
                for analyte in self.repository.list_catalog_analytes()
            }
            for definition in DEFAULT_LAB_ANALYTE_DEFINITIONS:
                analyte = existing_analytes.get(definition["code"])
                if analyte is None:
                    analyte = LabCatalogAnalyte(
                        code=definition["code"],
                        name=definition["name"],
                        short_name=definition.get("short_name"),
                        category=definition["category"],
                        default_unit_code=definition.get("default_unit_code"),
                        sort_order=definition.get("sort_order", 0),
                        is_active=definition.get("is_active", True),
                    )
                    self.repository.add_catalog_analyte(analyte)
                else:
                    analyte.name = definition["name"]
                    analyte.short_name = definition.get("short_name")
                    analyte.category = definition["category"]
                    analyte.default_unit_code = definition.get("default_unit_code")
                    analyte.sort_order = definition.get("sort_order", 0)
                    analyte.is_active = definition.get("is_active", True)
                self._catalog_analyte_cache[analyte.code] = analyte
                touched += 1

            seeded_ranges_by_key = {
                self._catalog_reference_key(definition): definition
                for definition in DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS
            }

            ranges_by_analyte: dict[str, list[LabCatalogReferenceRange]] = {}
            for item in self.repository.list_catalog_reference_ranges():
                ranges_by_analyte.setdefault(item.analyte_code, []).append(item)

            for analyte in DEFAULT_LAB_ANALYTE_DEFINITIONS:
                analyte_code = analyte["code"]
                existing_ranges = {
                    self._catalog_reference_key(
                        {
                            "analyte_code": item.analyte_code,
                            "sex": item.sex,
                            "age_min_months": item.age_min_months,
                            "age_max_months": item.age_max_months,
                            "sort_order": item.sort_order,
                        }
                    ): item
                    for item in ranges_by_analyte.get(analyte_code, [])
                }
                for key, definition in seeded_ranges_by_key.items():
                    if definition["analyte_code"] != analyte_code:
                        continue
                    reference_range = existing_ranges.get(key)
                    if reference_range is None:
                        reference_range = LabCatalogReferenceRange(
                            analyte_code=definition["analyte_code"],
                            sex=definition.get("sex"),
                            age_min_months=definition.get("age_min_months"),
                            age_max_months=definition.get("age_max_months"),
                            sort_order=definition.get("sort_order", 0),
                        )
                        self.repository.add_catalog_reference_range(reference_range)
                    reference_range.text = definition.get("text")
                    reference_range.low = self._coerce_decimal(definition.get("low"))
                    reference_range.high = self._coerce_decimal(definition.get("high"))
                    reference_range.warning_low = self._coerce_decimal(
                        definition.get("warning_low")
                    )
                    reference_range.warning_high = self._coerce_decimal(
                        definition.get("warning_high")
                    )
                    reference_range.critical_low = self._coerce_decimal(
                        definition.get("critical_low")
                    )
                    reference_range.critical_high = self._coerce_decimal(
                        definition.get("critical_high")
                    )
                    reference_range.sort_order = definition.get("sort_order", 0)
                    reference_range.is_active = definition.get("is_active", True)
                    touched += 1
                self._catalog_reference_cache.pop(analyte_code, None)

            _mark_seed_ensured(bind, "catalog")
            if touched:
                self.repository.commit()


