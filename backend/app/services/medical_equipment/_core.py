"""Core mixin for MedicalEquipmentService. Split from medical_equipment_service.py."""
from __future__ import annotations

from app.services.medical_equipment._base import *  # noqa: F401, F403
from app.services.medical_equipment._base import (
    MedicalEquipmentServiceMixinBase,  # noqa: F401
)


class CoreMixin(MedicalEquipmentServiceMixinBase):
    """Core methods."""

    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now()


class BaseDeviceDriver(ABC):
    """Базовый класс для драйверов устройств"""


    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now()


class BaseDeviceDriver(ABC):
    """Базовый класс для драйверов устройств"""


    def __init__(self, db: Session):
        self.db = db
        self.devices: dict[str, BaseDeviceDriver] = {}
        self.measurements: list[MeasurementData] = []
        self._initialize_devices()


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


    async def get_device_info(self) -> DeviceInfo:
        """Получить информацию об устройстве"""
        return self.device_info


class SerialDeviceDriver(BaseDeviceDriver):
    """Драйвер для устройств с последовательным подключением"""


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


    def _parse_measurement_data(self, raw_data: str) -> dict[str, Any]:
        """Парсинг данных измерения в зависимости от типа устройства"""
        measurements = {}

        try:
            if self.device_info.device_type == DeviceType.BLOOD_PRESSURE:
                # Пример: "SYS:120,DIA:80,PULSE:72"
                parts = raw_data.split(',')
                for part in parts:
                    key, value = part.split(':')
                    measurements[key.lower()] = int(value)

            elif self.device_info.device_type == DeviceType.PULSE_OXIMETER:
                # Пример: "SPO2:98,PULSE:75"
                parts = raw_data.split(',')
                for part in parts:
                    key, value = part.split(':')
                    measurements[key.lower()] = int(value)

            elif self.device_info.device_type == DeviceType.GLUCOMETER:
                # Пример: "GLUCOSE:5.6"
                measurements['glucose'] = float(raw_data.split(':')[1])

            elif self.device_info.device_type == DeviceType.THERMOMETER:
                # Пример: "TEMP:36.6"
                measurements['temperature'] = float(raw_data.split(':')[1])

            elif self.device_info.device_type == DeviceType.SCALE:
                # Пример: "WEIGHT:70.5"
                measurements['weight'] = float(raw_data.split(':')[1])

            else:
                # Общий парсинг
                measurements['value'] = raw_data

        except Exception as e:
            logger.error(f"Ошибка парсинга данных {raw_data}: {e}")
            measurements['raw'] = raw_data

        return measurements


    def _calculate_quality_score(self, measurements: dict[str, Any]) -> float:
        """Расчет оценки качества измерения"""
        # Простая оценка качества на основе наличия данных
        if not measurements:
            return 0.0

        score = 1.0

        # Проверяем наличие основных параметров
        if 'raw' in measurements:
            score *= 0.5  # Низкое качество если не удалось распарсить

        # Дополнительные проверки в зависимости от типа устройства
        if self.device_info.device_type == DeviceType.BLOOD_PRESSURE:
            if 'sys' in measurements and 'dia' in measurements:
                sys_val = measurements['sys']
                dia_val = measurements['dia']
                if 80 <= sys_val <= 200 and 50 <= dia_val <= 120:
                    score *= 1.0
                else:
                    score *= 0.7  # Подозрительные значения

        return min(score, 1.0)


class TCPDeviceDriver(BaseDeviceDriver):
    """Драйвер для устройств с TCP подключением"""


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


    def _parse_tcp_data(self, raw_data: str) -> dict[str, Any]:
        """Парсинг TCP данных"""
        try:
            # Попытка парсинга JSON
            return json.loads(raw_data)
        except Exception:
            # Простой парсинг ключ:значение
            measurements = {}
            parts = raw_data.split(',')
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    try:
                        measurements[key.strip()] = float(value.strip())
                    except Exception:
                        measurements[key.strip()] = value.strip()
            return measurements


class HTTPDeviceDriver(BaseDeviceDriver):
    """Драйвер для устройств с HTTP API"""


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


