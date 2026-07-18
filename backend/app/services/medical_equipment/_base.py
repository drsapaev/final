"""
Сервис для интеграции с медицинским оборудованием
Поддерживает различные типы медицинских устройств и протоколы связи
"""

import asyncio  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
import socket  # noqa: F401
from abc import ABC, abstractmethod  # noqa: F401
from dataclasses import asdict, dataclass  # noqa: F401
from datetime import datetime, timedelta  # noqa: F401
from enum import Enum  # noqa: F401
from typing import Any  # noqa: F401

import httpx  # noqa: F401
import serial  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Типы медицинских устройств"""

    ECG = "ecg"  # ЭКГ аппарат
    BLOOD_PRESSURE = "blood_pressure"  # Тонометр
    PULSE_OXIMETER = "pulse_oximeter"  # Пульсоксиметр
    GLUCOMETER = "glucometer"  # Глюкометр
    THERMOMETER = "thermometer"  # Термометр
    SPIROMETER = "spirometer"  # Спирометр
    ULTRASOUND = "ultrasound"  # УЗИ аппарат
    XRAY = "xray"  # Рентген аппарат
    ANALYZER = "analyzer"  # Анализатор (биохимический)
    SCALE = "scale"  # Весы
    HEIGHT_METER = "height_meter"  # Ростомер


class DeviceStatus(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Статусы устройств"""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    CALIBRATING = "calibrating"


class ConnectionType(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Типы подключения"""

    SERIAL = "serial"  # COM порт
    TCP = "tcp"  # TCP/IP
    UDP = "udp"  # UDP
    HTTP = "http"  # HTTP API
    BLUETOOTH = "bluetooth"  # Bluetooth
    USB = "usb"  # USB
    MOCK = "mock"  # Тестовое подключение


@dataclass
class MeasurementData:
    """Данные измерения"""

    device_id: str
    device_type: DeviceType
    timestamp: datetime
    patient_id: str | None = None
    measurements: dict[str, Any] = None
    raw_data: str | None = None
    quality_score: float | None = None
    notes: str | None = None

    def __post_init__(self):
        if self.measurements is None:
            self.measurements = {}
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class DeviceInfo:
    """Информация об устройстве"""

    id: str
    name: str
    device_type: DeviceType
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str
    connection_type: ConnectionType
    connection_params: dict[str, Any]
    status: DeviceStatus
    location: str = ""
    last_seen: datetime = None
    last_measurement: datetime = None
    calibration_date: datetime = None
    maintenance_date: datetime = None

    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now()


class BaseDeviceDriver(ABC):
    """Базовый класс для драйверов устройств"""

    def __init__(self, device_info: DeviceInfo):
        self.device_info = device_info
        self.connection = None
        self.is_connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Подключиться к устройству"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Отключиться от устройства"""
        pass

    @abstractmethod
    async def get_status(self) -> DeviceStatus:
        """Получить статус устройства"""
        pass

    @abstractmethod
    async def take_measurement(
        self, patient_id: str | None = None
    ) -> MeasurementData | None:
        """Выполнить измерение"""
        pass

    @abstractmethod
    async def calibrate(self) -> bool:
        """Калибровать устройство"""
        pass

    async def get_device_info(self) -> DeviceInfo:
        """Получить информацию об устройстве"""
        return self.device_info


class SerialDeviceDriver(BaseDeviceDriver):
    """Драйвер для устройств с последовательным подключением"""

    async def connect(self) -> bool:
        try:
            params = self.device_info.connection_params
            self.connection = serial.Serial(
                port=params.get('port', 'COM1'),
                baudrate=params.get('baudrate', 9600),
                bytesize=params.get('bytesize', 8),
                parity=params.get('parity', 'N'),
                stopbits=params.get('stopbits', 1),
                timeout=params.get('timeout', 1),
            )
            self.is_connected = True
            self.device_info.status = DeviceStatus.ONLINE
            self.device_info.last_seen = datetime.now()
            logger.info(
                f"Подключено к устройству {self.device_info.id} через {params.get('port')}"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к устройству {self.device_info.id}: {e}")
            self.device_info.status = DeviceStatus.ERROR
            return False

    async def disconnect(self) -> bool:
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
            self.is_connected = False
            self.device_info.status = DeviceStatus.OFFLINE
            logger.info(f"Отключено от устройства {self.device_info.id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отключения от устройства {self.device_info.id}: {e}")
            return False

    async def get_status(self) -> DeviceStatus:
        if not self.is_connected:
            return DeviceStatus.OFFLINE

        try:
            # Отправляем команду статуса (зависит от протокола устройства)
            if self.connection and self.connection.is_open:
                self.connection.write(b'STATUS\r\n')
                response = self.connection.readline().decode().strip()
                if response:
                    self.device_info.last_seen = datetime.now()
                    return DeviceStatus.ONLINE
            return DeviceStatus.ERROR
        except Exception as e:
            logger.error(
                f"Ошибка получения статуса устройства {self.device_info.id}: {e}"
            )
            return DeviceStatus.ERROR

    async def take_measurement(
        self, patient_id: str | None = None
    ) -> MeasurementData | None:
        if not self.is_connected:
            await self.connect()

        try:
            # Отправляем команду измерения
            self.connection.write(b'MEASURE\r\n')
            await asyncio.sleep(2)  # Ждем завершения измерения

            response = self.connection.readline().decode().strip()
            if response:
                # Парсим ответ в зависимости от типа устройства
                measurements = self._parse_measurement_data(response)

                measurement = MeasurementData(
                    device_id=self.device_info.id,
                    device_type=self.device_info.device_type,
                    timestamp=datetime.now(),
                    patient_id=patient_id,
                    measurements=measurements,
                    raw_data=response,
                    quality_score=self._calculate_quality_score(measurements),
                )

                self.device_info.last_measurement = datetime.now()
                logger.info(f"Измерение выполнено устройством {self.device_info.id}")
                return measurement
        except Exception as e:
            logger.error(f"Ошибка измерения устройством {self.device_info.id}: {e}")

        return None

    async def calibrate(self) -> bool:
        try:
            if not self.is_connected:
                await self.connect()

            self.device_info.status = DeviceStatus.CALIBRATING
            self.connection.write(b'CALIBRATE\r\n')
            await asyncio.sleep(10)  # Ждем завершения калибровки

            response = self.connection.readline().decode().strip()
            if 'OK' in response:
                self.device_info.calibration_date = datetime.now()
                self.device_info.status = DeviceStatus.ONLINE
                logger.info(f"Калибровка устройства {self.device_info.id} завершена")
                return True
            else:
                self.device_info.status = DeviceStatus.ERROR
                return False
        except Exception as e:
            logger.error(f"Ошибка калибровки устройства {self.device_info.id}: {e}")
            self.device_info.status = DeviceStatus.ERROR
            return False

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
        try:
            params = self.device_info.connection_params
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.settimeout(params.get('timeout', 5))
            self.connection.connect((params.get('host'), params.get('port')))
            self.is_connected = True
            self.device_info.status = DeviceStatus.ONLINE
            self.device_info.last_seen = datetime.now()
            logger.info(f"TCP подключение к устройству {self.device_info.id}")
            return True
        except Exception as e:
            logger.error(
                f"Ошибка TCP подключения к устройству {self.device_info.id}: {e}"
            )
            self.device_info.status = DeviceStatus.ERROR
            return False

    async def disconnect(self) -> bool:
        try:
            if self.connection:
                self.connection.close()
            self.is_connected = False
            self.device_info.status = DeviceStatus.OFFLINE
            return True
        except Exception as e:
            logger.error(
                f"Ошибка TCP отключения от устройства {self.device_info.id}: {e}"
            )
            return False

    async def get_status(self) -> DeviceStatus:
        if not self.is_connected:
            return DeviceStatus.OFFLINE

        try:
            self.connection.send(b'STATUS\n')
            response = self.connection.recv(1024).decode().strip()
            if response:
                self.device_info.last_seen = datetime.now()
                return DeviceStatus.ONLINE
            return DeviceStatus.ERROR
        except Exception as e:
            logger.error(
                f"Ошибка получения TCP статуса устройства {self.device_info.id}: {e}"
            )
            return DeviceStatus.ERROR

    async def take_measurement(
        self, patient_id: str | None = None
    ) -> MeasurementData | None:
        if not self.is_connected:
            await self.connect()

        try:
            self.connection.send(b'MEASURE\n')
            response = self.connection.recv(1024).decode().strip()

            if response:
                measurements = self._parse_tcp_data(response)

                measurement = MeasurementData(
                    device_id=self.device_info.id,
                    device_type=self.device_info.device_type,
                    timestamp=datetime.now(),
                    patient_id=patient_id,
                    measurements=measurements,
                    raw_data=response,
                )

                self.device_info.last_measurement = datetime.now()
                return measurement
        except Exception as e:
            logger.error(f"Ошибка TCP измерения устройством {self.device_info.id}: {e}")

        return None

    async def calibrate(self) -> bool:
        try:
            if not self.is_connected:
                await self.connect()

            self.device_info.status = DeviceStatus.CALIBRATING
            self.connection.send(b'CALIBRATE\n')
            response = self.connection.recv(1024).decode().strip()

            if 'OK' in response:
                self.device_info.calibration_date = datetime.now()
                self.device_info.status = DeviceStatus.ONLINE
                return True
            else:
                self.device_info.status = DeviceStatus.ERROR
                return False
        except Exception as e:
            logger.error(f"Ошибка TCP калибровки устройства {self.device_info.id}: {e}")
            self.device_info.status = DeviceStatus.ERROR
            return False

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
        try:
            params = self.device_info.connection_params
            base_url = params.get('base_url')
            auth = params.get('auth', {})

            # Тестовый запрос для проверки подключения
            response = httpx.get(  # nosec B113 — timeout on next line via params.get
                f"{base_url}/status",
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 5),
            )

            if response.status_code == 200:
                self.is_connected = True
                self.device_info.status = DeviceStatus.ONLINE
                self.device_info.last_seen = datetime.now()
                logger.info(f"HTTP подключение к устройству {self.device_info.id}")
                return True
            else:
                self.device_info.status = DeviceStatus.ERROR
                return False
        except Exception as e:
            logger.error(
                f"Ошибка HTTP подключения к устройству {self.device_info.id}: {e}"
            )
            self.device_info.status = DeviceStatus.ERROR
            return False

    async def disconnect(self) -> bool:
        self.is_connected = False
        self.device_info.status = DeviceStatus.OFFLINE
        return True

    async def get_status(self) -> DeviceStatus:
        try:
            params = self.device_info.connection_params
            base_url = params.get('base_url')
            auth = params.get('auth', {})

            response = httpx.get(  # nosec B113 — timeout on next line via params.get
                f"{base_url}/status",
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 5),
            )

            if response.status_code == 200:
                self.device_info.last_seen = datetime.now()
                return DeviceStatus.ONLINE
            else:
                return DeviceStatus.ERROR
        except Exception as e:
            logger.error(
                f"Ошибка получения HTTP статуса устройства {self.device_info.id}: {e}"
            )
            return DeviceStatus.ERROR

    async def take_measurement(
        self, patient_id: str | None = None
    ) -> MeasurementData | None:
        try:
            params = self.device_info.connection_params
            base_url = params.get('base_url')
            auth = params.get('auth', {})

            data = {'patient_id': patient_id} if patient_id else {}

            response = httpx.post(  # nosec B113 — timeout on next line via params.get
                f"{base_url}/measure",
                json=data,
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 30),
            )

            if response.status_code == 200:
                result = response.json()

                measurement = MeasurementData(
                    device_id=self.device_info.id,
                    device_type=self.device_info.device_type,
                    timestamp=datetime.now(),
                    patient_id=patient_id,
                    measurements=result.get('measurements', {}),
                    raw_data=json.dumps(result),
                    quality_score=result.get('quality_score', 1.0),
                )

                self.device_info.last_measurement = datetime.now()
                return measurement
        except Exception as e:
            logger.error(
                f"Ошибка HTTP измерения устройством {self.device_info.id}: {e}"
            )

        return None

    async def calibrate(self) -> bool:
        try:
            params = self.device_info.connection_params
            base_url = params.get('base_url')
            auth = params.get('auth', {})

            self.device_info.status = DeviceStatus.CALIBRATING

            response = httpx.post(  # nosec B113 — timeout on next line via params.get
                f"{base_url}/calibrate",
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 60),
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.device_info.calibration_date = datetime.now()
                    self.device_info.status = DeviceStatus.ONLINE
                    return True

            self.device_info.status = DeviceStatus.ERROR
            return False
        except Exception as e:
            logger.error(
                f"Ошибка HTTP калибровки устройства {self.device_info.id}: {e}"
            )
            self.device_info.status = DeviceStatus.ERROR
            return False


class MockDeviceDriver(BaseDeviceDriver):
    """Мок-драйвер для тестирования"""

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
        self, patient_id: str | None = None
    ) -> MeasurementData | None:
        await asyncio.sleep(1)  # Имитация измерения

        # Генерируем тестовые данные в зависимости от типа устройства
        measurements = self._generate_mock_data()

        measurement = MeasurementData(
            device_id=self.device_info.id,
            device_type=self.device_info.device_type,
            timestamp=datetime.now(),
            patient_id=patient_id,
            measurements=measurements,
            raw_data=json.dumps(measurements),
            quality_score=0.95,
        )

        self.device_info.last_measurement = datetime.now()
        return measurement

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



class MedicalEquipmentServiceMixinBase:
    """Type-hint anchor."""













































