"""
Сервис для интеграции с медицинским оборудованием
Поддерживает различные типы медицинских устройств и протоколы связи
"""

import logging
import json
import asyncio
import serial
import socket
import struct
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
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


class DeviceStatus(str, Enum):
    """Статусы устройств"""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    CALIBRATING = "calibrating"


class ConnectionType(str, Enum):
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
    patient_id: Optional[str] = None
    measurements: Dict[str, Any] = None
    raw_data: Optional[str] = None
    quality_score: Optional[float] = None
    notes: Optional[str] = None

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
    connection_params: Dict[str, Any]
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
    async def take_measurement(self, patient_id: Optional[str] = None) -> Optional[MeasurementData]:
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
                timeout=params.get('timeout', 1)
            )
            self.is_connected = True
            self.device_info.status = DeviceStatus.ONLINE
            self.device_info.last_seen = datetime.now()
            logger.info(f"Подключено к устройству {self.device_info.id} через {params.get('port')}")
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
            logger.error(f"Ошибка получения статуса устройства {self.device_info.id}: {e}")
            return DeviceStatus.ERROR

    async def take_measurement(self, patient_id: Optional[str] = None) -> Optional[MeasurementData]:
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
                    quality_score=self._calculate_quality_score(measurements)
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

    def _parse_measurement_data(self, raw_data: str) -> Dict[str, Any]:
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

    def _calculate_quality_score(self, measurements: Dict[str, Any]) -> float:
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
            logger.error(f"Ошибка TCP подключения к устройству {self.device_info.id}: {e}")
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
            logger.error(f"Ошибка TCP отключения от устройства {self.device_info.id}: {e}")
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
            logger.error(f"Ошибка получения TCP статуса устройства {self.device_info.id}: {e}")
            return DeviceStatus.ERROR

    async def take_measurement(self, patient_id: Optional[str] = None) -> Optional[MeasurementData]:
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
                    raw_data=response
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

    def _parse_tcp_data(self, raw_data: str) -> Dict[str, Any]:
        """Парсинг TCP данных"""
        try:
            # Попытка парсинга JSON
            return json.loads(raw_data)
        except:
            # Простой парсинг ключ:значение
            measurements = {}
            parts = raw_data.split(',')
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    try:
                        measurements[key.strip()] = float(value.strip())
                    except:
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
            response = requests.get(
                f"{base_url}/status",
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 5)
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
            logger.error(f"Ошибка HTTP подключения к устройству {self.device_info.id}: {e}")
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
            
            response = requests.get(
                f"{base_url}/status",
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 5)
            )
            
            if response.status_code == 200:
                self.device_info.last_seen = datetime.now()
                return DeviceStatus.ONLINE
            else:
                return DeviceStatus.ERROR
        except Exception as e:
            logger.error(f"Ошибка получения HTTP статуса устройства {self.device_info.id}: {e}")
            return DeviceStatus.ERROR

    async def take_measurement(self, patient_id: Optional[str] = None) -> Optional[MeasurementData]:
        try:
            params = self.device_info.connection_params
            base_url = params.get('base_url')
            auth = params.get('auth', {})
            
            data = {'patient_id': patient_id} if patient_id else {}
            
            response = requests.post(
                f"{base_url}/measure",
                json=data,
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 30)
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
                    quality_score=result.get('quality_score', 1.0)
                )
                
                self.device_info.last_measurement = datetime.now()
                return measurement
        except Exception as e:
            logger.error(f"Ошибка HTTP измерения устройством {self.device_info.id}: {e}")
        
        return None

    async def calibrate(self) -> bool:
        try:
            params = self.device_info.connection_params
            base_url = params.get('base_url')
            auth = params.get('auth', {})
            
            self.device_info.status = DeviceStatus.CALIBRATING
            
            response = requests.post(
                f"{base_url}/calibrate",
                auth=(auth.get('username'), auth.get('password')) if auth else None,
                timeout=params.get('timeout', 60)
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
            logger.error(f"Ошибка HTTP калибровки устройства {self.device_info.id}: {e}")
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

    async def take_measurement(self, patient_id: Optional[str] = None) -> Optional[MeasurementData]:
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
            quality_score=0.95
        )
        
        self.device_info.last_measurement = datetime.now()
        return measurement

    async def calibrate(self) -> bool:
        await asyncio.sleep(2)  # Имитация калибровки
        self.device_info.calibration_date = datetime.now()
        return True

    def _generate_mock_data(self) -> Dict[str, Any]:
        """Генерация тестовых данных"""
        import random
        
        if self.device_info.device_type == DeviceType.BLOOD_PRESSURE:
            return {
                'sys': random.randint(110, 140),
                'dia': random.randint(70, 90),
                'pulse': random.randint(60, 80)
            }
        elif self.device_info.device_type == DeviceType.PULSE_OXIMETER:
            return {
                'spo2': random.randint(95, 100),
                'pulse': random.randint(60, 80)
            }
        elif self.device_info.device_type == DeviceType.GLUCOMETER:
            return {
                'glucose': round(random.uniform(4.0, 7.0), 1)
            }
        elif self.device_info.device_type == DeviceType.THERMOMETER:
            return {
                'temperature': round(random.uniform(36.0, 37.5), 1)
            }
        elif self.device_info.device_type == DeviceType.SCALE:
            return {
                'weight': round(random.uniform(50.0, 100.0), 1)
            }
        else:
            return {
                'value': random.randint(50, 150),
                'unit': 'units'
            }


class MedicalEquipmentService:
    """Основной сервис для работы с медицинским оборудованием"""

    def __init__(self, db: Session):
        self.db = db
        self.devices: Dict[str, BaseDeviceDriver] = {}
        self.measurements: List[MeasurementData] = []
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
                location="Кабинет 101"
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
                location="Кабинет 102"
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
                location="Лаборатория"
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
                location="Приемная"
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
                location="Кабинет врача"
            )
        ]

        for device_info in mock_devices:
            driver = self._create_driver(device_info)
            if driver:
                self.devices[device_info.id] = driver

        logger.info(f"Инициализировано {len(self.devices)} медицинских устройств")

    def _create_driver(self, device_info: DeviceInfo) -> Optional[BaseDeviceDriver]:
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
                logger.warning(f"Неподдерживаемый тип подключения: {device_info.connection_type}")
                return None
        except Exception as e:
            logger.error(f"Ошибка создания драйвера для устройства {device_info.id}: {e}")
            return None

    async def get_all_devices(self) -> List[DeviceInfo]:
        """Получить список всех устройств"""
        devices = []
        for driver in self.devices.values():
            device_info = await driver.get_device_info()
            devices.append(device_info)
        return devices

    async def get_device(self, device_id: str) -> Optional[DeviceInfo]:
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

    async def get_device_status(self, device_id: str) -> Optional[DeviceStatus]:
        """Получить статус устройства"""
        driver = self.devices.get(device_id)
        if driver:
            return await driver.get_status()
        return None

    async def take_measurement(self, device_id: str, patient_id: Optional[str] = None) -> Optional[MeasurementData]:
        """Выполнить измерение"""
        driver = self.devices.get(device_id)
        if driver:
            measurement = await driver.take_measurement(patient_id)
            if measurement:
                self.measurements.append(measurement)
                logger.info(f"Измерение сохранено: {device_id} -> {measurement.measurements}")
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
        device_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        device_type: Optional[DeviceType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[MeasurementData]:
        """Получить измерения с фильтрацией"""
        filtered_measurements = self.measurements

        if device_id:
            filtered_measurements = [m for m in filtered_measurements if m.device_id == device_id]
        
        if patient_id:
            filtered_measurements = [m for m in filtered_measurements if m.patient_id == patient_id]
        
        if device_type:
            filtered_measurements = [m for m in filtered_measurements if m.device_type == device_type]
        
        if start_date:
            filtered_measurements = [m for m in filtered_measurements if m.timestamp >= start_date]
        
        if end_date:
            filtered_measurements = [m for m in filtered_measurements if m.timestamp <= end_date]

        # Сортируем по времени (новые первые) и ограничиваем количество
        filtered_measurements.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered_measurements[:limit]

    async def get_device_statistics(self, device_id: str) -> Dict[str, Any]:
        """Получить статистику устройства"""
        device_measurements = [m for m in self.measurements if m.device_id == device_id]
        
        if not device_measurements:
            return {
                "total_measurements": 0,
                "last_measurement": None,
                "average_quality": 0.0
            }

        total_measurements = len(device_measurements)
        last_measurement = max(device_measurements, key=lambda x: x.timestamp)
        quality_scores = [m.quality_score for m in device_measurements if m.quality_score is not None]
        average_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        return {
            "total_measurements": total_measurements,
            "last_measurement": last_measurement.timestamp,
            "average_quality": round(average_quality, 2),
            "measurements_today": len([m for m in device_measurements 
                                     if m.timestamp.date() == datetime.now().date()]),
            "measurements_this_week": len([m for m in device_measurements 
                                         if m.timestamp >= datetime.now() - timedelta(days=7)])
        }

    async def run_diagnostics(self, device_id: str) -> Dict[str, Any]:
        """Запустить диагностику устройства"""
        driver = self.devices.get(device_id)
        if not driver:
            return {"success": False, "error": "Устройство не найдено"}

        results = {
            "device_id": device_id,
            "timestamp": datetime.now(),
            "tests": {}
        }

        try:
            # Тест подключения
            connection_test = await driver.connect()
            results["tests"]["connection"] = {
                "passed": connection_test,
                "message": "Подключение успешно" if connection_test else "Ошибка подключения"
            }

            if connection_test:
                # Тест статуса
                status = await driver.get_status()
                results["tests"]["status"] = {
                    "passed": status == DeviceStatus.ONLINE,
                    "status": status.value,
                    "message": f"Статус: {status.value}"
                }

                # Тест измерения
                try:
                    measurement = await driver.take_measurement()
                    results["tests"]["measurement"] = {
                        "passed": measurement is not None,
                        "message": "Тестовое измерение выполнено" if measurement else "Ошибка измерения",
                        "data": asdict(measurement) if measurement else None
                    }
                except Exception as e:
                    results["tests"]["measurement"] = {
                        "passed": False,
                        "message": f"Ошибка измерения: {str(e)}"
                    }

            results["success"] = all(test["passed"] for test in results["tests"].values())
            
        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

        return results

    async def update_device_config(self, device_id: str, config: Dict[str, Any]) -> bool:
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
        device_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[str]:
        """Экспорт измерений"""
        measurements = await self.get_measurements(
            device_id=device_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        if not measurements:
            return None

        try:
            if format.lower() == "json":
                return json.dumps([asdict(m) for m in measurements], default=str, indent=2)
            elif format.lower() == "csv":
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Заголовки
                headers = ['device_id', 'device_type', 'timestamp', 'patient_id', 'measurements', 'quality_score']
                writer.writerow(headers)
                
                # Данные
                for m in measurements:
                    writer.writerow([
                        m.device_id,
                        m.device_type.value,
                        m.timestamp.isoformat(),
                        m.patient_id or '',
                        json.dumps(m.measurements),
                        m.quality_score or ''
                    ])
                
                return output.getvalue()
            else:
                return None
        except Exception as e:
            logger.error(f"Ошибка экспорта измерений: {e}")
            return None


def get_medical_equipment_service(db: Session) -> MedicalEquipmentService:
    """Получить экземпляр сервиса медицинского оборудования"""
    return MedicalEquipmentService(db)

