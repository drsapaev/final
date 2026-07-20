"""Operations mixin for MedicalEquipmentService. Split from medical_equipment_service.py."""
from __future__ import annotations

from app.services.medical_equipment._base import *  # noqa: F401, F403
from app.services.medical_equipment._base import (
    MedicalEquipmentServiceMixinBase,  # noqa: F401
)


class OperationsMixin(MedicalEquipmentServiceMixinBase):
    """Operations methods."""

    async def get_status(self) -> DeviceStatus:
        self.device_info.last_seen = datetime.now()
        return DeviceStatus.ONLINE if self.is_connected else DeviceStatus.OFFLINE


    async def take_measurement(
        self, device_id: str, patient_id: str | None = None
    ) -> MeasurementData | None:
        """Выполнить измерение"""
        driver = self.devices.get(device_id)
        if driver:
            measurement = await driver.take_measurement(patient_id)
            if measurement:
                self.measurements.append(measurement)
                logger.info(
                    f"Измерение сохранено: {device_id} -> {measurement.measurements}"
                )
            return measurement
        return None


    async def calibrate(self) -> bool:
        await asyncio.sleep(2)  # Имитация калибровки
        self.device_info.calibration_date = datetime.now()
        return True


    async def connect(self) -> bool:
        await asyncio.sleep(0.1)  # Имитация подключения
        self.is_connected = True
        self.device_info.status = DeviceStatus.ONLINE
        self.device_info.last_seen = datetime.now()
        logger.info(f"Mock подключение к устройству {self.device_info.id}")
        return True


    async def disconnect(self) -> bool:
        self.is_connected = False
        self.device_info.status = DeviceStatus.OFFLINE
        return True


    async def get_status(self) -> DeviceStatus:
        self.device_info.last_seen = datetime.now()
        return DeviceStatus.ONLINE if self.is_connected else DeviceStatus.OFFLINE


    async def take_measurement(
        self, device_id: str, patient_id: str | None = None
    ) -> MeasurementData | None:
        """Выполнить измерение"""
        driver = self.devices.get(device_id)
        if driver:
            measurement = await driver.take_measurement(patient_id)
            if measurement:
                self.measurements.append(measurement)
                logger.info(
                    f"Измерение сохранено: {device_id} -> {measurement.measurements}"
                )
            return measurement
        return None


    async def calibrate(self) -> bool:
        await asyncio.sleep(2)  # Имитация калибровки
        self.device_info.calibration_date = datetime.now()
        return True


    def _generate_mock_data(self) -> dict[str, Any]:
        """Генерация тестовых данных"""
        import random

        if self.device_info.device_type == DeviceType.BLOOD_PRESSURE:
            return {
                'sys': random.randint(110, 140),
                'dia': random.randint(70, 90),
                'pulse': random.randint(60, 80),
            }
        elif self.device_info.device_type == DeviceType.PULSE_OXIMETER:
            return {'spo2': random.randint(95, 100), 'pulse': random.randint(60, 80)}
        elif self.device_info.device_type == DeviceType.GLUCOMETER:
            return {'glucose': round(random.uniform(4.0, 7.0), 1)}
        elif self.device_info.device_type == DeviceType.THERMOMETER:
            return {'temperature': round(random.uniform(36.0, 37.5), 1)}
        elif self.device_info.device_type == DeviceType.SCALE:
            return {'weight': round(random.uniform(50.0, 100.0), 1)}
        else:
            return {'value': random.randint(50, 150), 'unit': 'units'}


class MedicalEquipmentService:
    """Основной сервис для работы с медицинским оборудованием"""


    def __init__(self, db: Session):
        self.db = db
        self.devices: dict[str, BaseDeviceDriver] = {}
        self.measurements: list[MeasurementData] = []
        self._initialize_devices()


    def _initialize_devices(self):
        """Инициализация устройств"""
        # Загружаем конфигурацию устройств из настроек или БД
        mock_devices = [
            DeviceInfo(
                id="bp-001",
                name="Тонометр OMRON",
                device_type=DeviceType.BLOOD_PRESSURE,
                manufacturer="OMRON",
                model="M3 Comfort",
                serial_number="BP001234",
                firmware_version="1.2.3",
                connection_type=ConnectionType.MOCK,
                connection_params={},
                status=DeviceStatus.OFFLINE,
                location="Кабинет 101",
            ),
            DeviceInfo(
                id="po-001",
                name="Пульсоксиметр Fingertip",
                device_type=DeviceType.PULSE_OXIMETER,
                manufacturer="Generic",
                model="MD300C",
                serial_number="PO001234",
                firmware_version="2.1.0",
                connection_type=ConnectionType.MOCK,
                connection_params={},
                status=DeviceStatus.OFFLINE,
                location="Кабинет 102",
            ),
            DeviceInfo(
                id="gl-001",
                name="Глюкометр Accu-Chek",
                device_type=DeviceType.GLUCOMETER,
                manufacturer="Roche",
                model="Accu-Chek Active",
                serial_number="GL001234",
                firmware_version="1.0.5",
                connection_type=ConnectionType.MOCK,
                connection_params={},
                status=DeviceStatus.OFFLINE,
                location="Лаборатория",
            ),
            DeviceInfo(
                id="th-001",
                name="Термометр инфракрасный",
                device_type=DeviceType.THERMOMETER,
                manufacturer="Braun",
                model="ThermoScan 7",
                serial_number="TH001234",
                firmware_version="3.2.1",
                connection_type=ConnectionType.MOCK,
                connection_params={},
                status=DeviceStatus.OFFLINE,
                location="Приемная",
            ),
            DeviceInfo(
                id="sc-001",
                name="Весы медицинские",
                device_type=DeviceType.SCALE,
                manufacturer="Tanita",
                model="BWB-800",
                serial_number="SC001234",
                firmware_version="1.1.0",
                connection_type=ConnectionType.MOCK,
                connection_params={},
                status=DeviceStatus.OFFLINE,
                location="Кабинет врача",
            ),
        ]

        for device_info in mock_devices:
            driver = self._create_driver(device_info)
            if driver:
                self.devices[device_info.id] = driver

        logger.info(f"Инициализировано {len(self.devices)} медицинских устройств")


    def _create_driver(self, device_info: DeviceInfo) -> BaseDeviceDriver | None:
        """Создание драйвера для устройства"""
        try:
            if device_info.connection_type == ConnectionType.SERIAL:
                return SerialDeviceDriver(device_info)
            elif device_info.connection_type == ConnectionType.TCP:
                return TCPDeviceDriver(device_info)
            elif device_info.connection_type == ConnectionType.HTTP:
                return HTTPDeviceDriver(device_info)
            elif device_info.connection_type == ConnectionType.MOCK:
                return MockDeviceDriver(device_info)
            else:
                logger.warning(
                    f"Неподдерживаемый тип подключения: {device_info.connection_type}"
                )
                return None
        except Exception as e:
            logger.error(
                f"Ошибка создания драйвера для устройства {device_info.id}: {e}"
            )
            return None


    async def get_all_devices(self) -> list[DeviceInfo]:
        """Получить список всех устройств"""
        devices = []
        for driver in self.devices.values():
            device_info = await driver.get_device_info()
            devices.append(device_info)
        return devices


    async def get_device(self, device_id: str) -> DeviceInfo | None:
        """Получить информацию об устройстве"""
        driver = self.devices.get(device_id)
        if driver:
            return await driver.get_device_info()
        return None


    async def connect_device(self, device_id: str) -> bool:
        """Подключиться к устройству"""
        driver = self.devices.get(device_id)
        if driver:
            return await driver.connect()
        return False


    async def disconnect_device(self, device_id: str) -> bool:
        """Отключиться от устройства"""
        driver = self.devices.get(device_id)
        if driver:
            return await driver.disconnect()
        return False


    async def get_device_status(self, device_id: str) -> DeviceStatus | None:
        """Получить статус устройства"""
        driver = self.devices.get(device_id)
        if driver:
            return await driver.get_status()
        return None


    async def take_measurement(
        self, device_id: str, patient_id: str | None = None
    ) -> MeasurementData | None:
        """Выполнить измерение"""
        driver = self.devices.get(device_id)
        if driver:
            measurement = await driver.take_measurement(patient_id)
            if measurement:
                self.measurements.append(measurement)
                logger.info(
                    f"Измерение сохранено: {device_id} -> {measurement.measurements}"
                )
            return measurement
        return None


    async def calibrate_device(self, device_id: str) -> bool:
        """Калибровать устройство"""
        driver = self.devices.get(device_id)
        if driver:
            return await driver.calibrate()
        return False


    async def get_measurements(
        self,
        device_id: str | None = None,
        patient_id: str | None = None,
        device_type: DeviceType | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[MeasurementData]:
        """Получить измерения с фильтрацией"""
        filtered_measurements = self.measurements

        if device_id:
            filtered_measurements = [
                m for m in filtered_measurements if m.device_id == device_id
            ]

        if patient_id:
            filtered_measurements = [
                m for m in filtered_measurements if m.patient_id == patient_id
            ]

        if device_type:
            filtered_measurements = [
                m for m in filtered_measurements if m.device_type == device_type
            ]

        if start_date:
            filtered_measurements = [
                m for m in filtered_measurements if m.timestamp >= start_date
            ]

        if end_date:
            filtered_measurements = [
                m for m in filtered_measurements if m.timestamp <= end_date
            ]

        # Сортируем по времени (новые первые) и ограничиваем количество
        filtered_measurements.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered_measurements[:limit]


    async def get_device_statistics(self, device_id: str) -> dict[str, Any]:
        """Получить статистику устройства"""
        device_measurements = [m for m in self.measurements if m.device_id == device_id]

        if not device_measurements:
            return {
                "total_measurements": 0,
                "last_measurement": None,
                "average_quality": 0.0,
            }

        total_measurements = len(device_measurements)
        last_measurement = max(device_measurements, key=lambda x: x.timestamp)
        quality_scores = [
            m.quality_score for m in device_measurements if m.quality_score is not None
        ]
        average_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        )

        return {
            "total_measurements": total_measurements,
            "last_measurement": last_measurement.timestamp,
            "average_quality": round(average_quality, 2),
            "measurements_today": len(
                [
                    m
                    for m in device_measurements
                    if m.timestamp.date() == datetime.now().date()
                ]
            ),
            "measurements_this_week": len(
                [
                    m
                    for m in device_measurements
                    if m.timestamp >= datetime.now() - timedelta(days=7)
                ]
            ),
        }


    async def run_diagnostics(self, device_id: str) -> dict[str, Any]:
        """Запустить диагностику устройства"""
        driver = self.devices.get(device_id)
        if not driver:
            return {"success": False, "error": "Устройство не найдено"}

        results = {"device_id": device_id, "timestamp": datetime.now(), "tests": {}}

        try:
            # Тест подключения
            connection_test = await driver.connect()
            results["tests"]["connection"] = {
                "passed": connection_test,
                "message": (
                    "Подключение успешно" if connection_test else "Ошибка подключения"
                ),
            }

            if connection_test:
                # Тест статуса
                status = await driver.get_status()
                results["tests"]["status"] = {
                    "passed": status == DeviceStatus.ONLINE,
                    "status": status.value,
                    "message": f"Статус: {status.value}",
                }

                # Тест измерения
                try:
                    measurement = await driver.take_measurement()
                    results["tests"]["measurement"] = {
                        "passed": measurement is not None,
                        "message": (
                            "Тестовое измерение выполнено"
                            if measurement
                            else "Ошибка измерения"
                        ),
                        "data": asdict(measurement) if measurement else None,
                    }
                except Exception:
                    results["tests"]["measurement"] = {
                        "passed": False,
                        "message": "Внутренняя ошибка",
                    }

            results["success"] = all(
                test["passed"] for test in results["tests"].values()
            )

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

        return results


    async def update_device_config(
        self, device_id: str, config: dict[str, Any]
    ) -> bool:
        """Обновить конфигурацию устройства"""
        driver = self.devices.get(device_id)
        if not driver:
            return False

        try:
            # Обновляем параметры подключения
            if 'connection_params' in config:
                driver.device_info.connection_params.update(config['connection_params'])

            # Обновляем другие параметры
            for key, value in config.items():
                if hasattr(driver.device_info, key) and key != 'connection_params':
                    setattr(driver.device_info, key, value)

            logger.info(f"Конфигурация устройства {device_id} обновлена")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления конфигурации устройства {device_id}: {e}")
            return False


    async def export_measurements(
        self,
        format: str = "json",
        device_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> str | None:
        """Экспорт измерений"""
        measurements = await self.get_measurements(
            device_id=device_id, start_date=start_date, end_date=end_date, limit=10000
        )

        if not measurements:
            return None

        try:
            if format.lower() == "json":
                return json.dumps(
                    [asdict(m) for m in measurements], default=str, indent=2
                )
            elif format.lower() == "csv":
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Заголовки
                headers = [
                    'device_id',
                    'device_type',
                    'timestamp',
                    'patient_id',
                    'measurements',
                    'quality_score',
                ]
                writer.writerow(headers)

                # Данные
                for m in measurements:
                    writer.writerow(
                        [
                            m.device_id,
                            m.device_type.value,
                            m.timestamp.isoformat(),
                            m.patient_id or '',
                            json.dumps(m.measurements),
                            m.quality_score or '',
                        ]
                    )

                return output.getvalue()
            else:
                return None
        except Exception as e:
            logger.error(f"Ошибка экспорта измерений: {e}")
            return None


def get_medical_equipment_service(db: Session) -> MedicalEquipmentService:
    """Получить экземпляр сервиса медицинского оборудования"""
    return MedicalEquipmentService(db)


