"""
API endpoints для медицинского оборудования
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_current_user, require_roles
from app.core.roles import Roles
from app.models.user import User
from app.services.medical_equipment_service import (
    get_medical_equipment_service,
    MedicalEquipmentService,
    DeviceType,
    DeviceStatus,
    ConnectionType
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic Models for Requests and Responses
class DeviceInfoResponse(BaseModel):
    """Ответ с информацией об устройстве"""
    id: str
    name: str
    device_type: str
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str
    connection_type: str
    status: str
    location: str
    last_seen: Optional[datetime] = None
    last_measurement: Optional[datetime] = None
    calibration_date: Optional[datetime] = None
    maintenance_date: Optional[datetime] = None


class MeasurementRequest(BaseModel):
    """Запрос на измерение"""
    device_id: str = Field(..., description="ID устройства")
    patient_id: Optional[str] = Field(None, description="ID пациента")


class MeasurementResponse(BaseModel):
    """Ответ с данными измерения"""
    device_id: str
    device_type: str
    timestamp: datetime
    patient_id: Optional[str] = None
    measurements: Dict[str, Any]
    raw_data: Optional[str] = None
    quality_score: Optional[float] = None
    notes: Optional[str] = None


class DeviceConfigRequest(BaseModel):
    """Запрос на обновление конфигурации устройства"""
    name: Optional[str] = None
    location: Optional[str] = None
    connection_params: Optional[Dict[str, Any]] = None
    maintenance_date: Optional[datetime] = None


class DiagnosticsResponse(BaseModel):
    """Ответ с результатами диагностики"""
    device_id: str
    timestamp: datetime
    success: bool
    tests: Dict[str, Any]
    error: Optional[str] = None


class StatisticsResponse(BaseModel):
    """Ответ со статистикой устройства"""
    total_measurements: int
    last_measurement: Optional[datetime] = None
    average_quality: float
    measurements_today: int
    measurements_this_week: int


# ===================== УСТРОЙСТВА =====================

@router.get("/devices")
async def get_all_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Получить список всех медицинских устройств"""
    try:
        equipment_service = get_medical_equipment_service(db)
        devices = await equipment_service.get_all_devices()
        
        devices_response = []
        for device in devices:
            device_response = DeviceInfoResponse(
                id=device.id,
                name=device.name,
                device_type=device.device_type.value,
                manufacturer=device.manufacturer,
                model=device.model,
                serial_number=device.serial_number,
                firmware_version=device.firmware_version,
                connection_type=device.connection_type.value,
                status=device.status.value,
                location=device.location,
                last_seen=device.last_seen,
                last_measurement=device.last_measurement,
                calibration_date=device.calibration_date,
                maintenance_date=device.maintenance_date
            )
            devices_response.append(device_response)
        
        return {
            "success": True,
            "devices": devices_response,
            "total_count": len(devices_response)
        }
    except Exception as e:
        logger.error(f"Ошибка получения устройств: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{device_id}")
async def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Получить информацию о конкретном устройстве"""
    try:
        equipment_service = get_medical_equipment_service(db)
        device = await equipment_service.get_device(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail="Устройство не найдено")
        
        return {
            "success": True,
            "device": DeviceInfoResponse(
                id=device.id,
                name=device.name,
                device_type=device.device_type.value,
                manufacturer=device.manufacturer,
                model=device.model,
                serial_number=device.serial_number,
                firmware_version=device.firmware_version,
                connection_type=device.connection_type.value,
                status=device.status.value,
                location=device.location,
                last_seen=device.last_seen,
                last_measurement=device.last_measurement,
                calibration_date=device.calibration_date,
                maintenance_date=device.maintenance_date
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения устройства {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/type/{device_type}")
async def get_devices_by_type(
    device_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Получить устройства по типу"""
    try:
        # Проверяем валидность типа устройства
        try:
            device_type_enum = DeviceType(device_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Неверный тип устройства: {device_type}")
        
        equipment_service = get_medical_equipment_service(db)
        all_devices = await equipment_service.get_all_devices()
        
        filtered_devices = [d for d in all_devices if d.device_type == device_type_enum]
        
        devices_response = []
        for device in filtered_devices:
            device_response = DeviceInfoResponse(
                id=device.id,
                name=device.name,
                device_type=device.device_type.value,
                manufacturer=device.manufacturer,
                model=device.model,
                serial_number=device.serial_number,
                firmware_version=device.firmware_version,
                connection_type=device.connection_type.value,
                status=device.status.value,
                location=device.location,
                last_seen=device.last_seen,
                last_measurement=device.last_measurement,
                calibration_date=device.calibration_date,
                maintenance_date=device.maintenance_date
            )
            devices_response.append(device_response)
        
        return {
            "success": True,
            "device_type": device_type,
            "devices": devices_response,
            "count": len(devices_response)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения устройств типа {device_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== ПОДКЛЮЧЕНИЕ И УПРАВЛЕНИЕ =====================

@router.post("/devices/{device_id}/connect")
async def connect_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR]))
):
    """Подключиться к устройству"""
    try:
        equipment_service = get_medical_equipment_service(db)
        success = await equipment_service.connect_device(device_id)
        
        if success:
            logger.info(f"Пользователь {current_user.email} подключился к устройству {device_id}")
            return {
                "success": True,
                "message": "Устройство подключено",
                "device_id": device_id
            }
        else:
            return {
                "success": False,
                "message": "Не удалось подключиться к устройству",
                "device_id": device_id
            }
    except Exception as e:
        logger.error(f"Ошибка подключения к устройству {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/{device_id}/disconnect")
async def disconnect_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR]))
):
    """Отключиться от устройства"""
    try:
        equipment_service = get_medical_equipment_service(db)
        success = await equipment_service.disconnect_device(device_id)
        
        if success:
            logger.info(f"Пользователь {current_user.email} отключился от устройства {device_id}")
            return {
                "success": True,
                "message": "Устройство отключено",
                "device_id": device_id
            }
        else:
            return {
                "success": False,
                "message": "Не удалось отключиться от устройства",
                "device_id": device_id
            }
    except Exception as e:
        logger.error(f"Ошибка отключения от устройства {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{device_id}/status")
async def get_device_status(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Получить статус устройства"""
    try:
        equipment_service = get_medical_equipment_service(db)
        status = await equipment_service.get_device_status(device_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="Устройство не найдено")
        
        return {
            "success": True,
            "device_id": device_id,
            "status": status.value,
            "timestamp": datetime.now()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статуса устройства {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== ИЗМЕРЕНИЯ =====================

@router.post("/measurements", response_model=MeasurementResponse)
async def take_measurement(
    request: MeasurementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Выполнить измерение"""
    try:
        equipment_service = get_medical_equipment_service(db)
        measurement = await equipment_service.take_measurement(
            device_id=request.device_id,
            patient_id=request.patient_id
        )
        
        if measurement:
            logger.info(f"Пользователь {current_user.email} выполнил измерение на устройстве {request.device_id}")
            return MeasurementResponse(
                device_id=measurement.device_id,
                device_type=measurement.device_type.value,
                timestamp=measurement.timestamp,
                patient_id=measurement.patient_id,
                measurements=measurement.measurements,
                raw_data=measurement.raw_data,
                quality_score=measurement.quality_score,
                notes=measurement.notes
            )
        else:
            raise HTTPException(status_code=400, detail="Не удалось выполнить измерение")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка выполнения измерения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/measurements")
async def get_measurements(
    device_id: Optional[str] = Query(None, description="ID устройства"),
    patient_id: Optional[str] = Query(None, description="ID пациента"),
    device_type: Optional[str] = Query(None, description="Тип устройства"),
    start_date: Optional[date] = Query(None, description="Начальная дата"),
    end_date: Optional[date] = Query(None, description="Конечная дата"),
    limit: int = Query(100, ge=1, le=1000, description="Количество записей"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Получить измерения с фильтрацией"""
    try:
        equipment_service = get_medical_equipment_service(db)
        
        # Преобразуем даты в datetime
        start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
        
        # Преобразуем тип устройства
        device_type_enum = None
        if device_type:
            try:
                device_type_enum = DeviceType(device_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Неверный тип устройства: {device_type}")
        
        measurements = await equipment_service.get_measurements(
            device_id=device_id,
            patient_id=patient_id,
            device_type=device_type_enum,
            start_date=start_datetime,
            end_date=end_datetime,
            limit=limit
        )
        
        measurements_response = []
        for measurement in measurements:
            measurement_response = MeasurementResponse(
                device_id=measurement.device_id,
                device_type=measurement.device_type.value,
                timestamp=measurement.timestamp,
                patient_id=measurement.patient_id,
                measurements=measurement.measurements,
                raw_data=measurement.raw_data,
                quality_score=measurement.quality_score,
                notes=measurement.notes
            )
            measurements_response.append(measurement_response)
        
        return {
            "success": True,
            "measurements": measurements_response,
            "total_count": len(measurements_response),
            "filters": {
                "device_id": device_id,
                "patient_id": patient_id,
                "device_type": device_type,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения измерений: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== КАЛИБРОВКА И ДИАГНОСТИКА =====================

@router.post("/devices/{device_id}/calibrate")
async def calibrate_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR]))
):
    """Калибровать устройство"""
    try:
        equipment_service = get_medical_equipment_service(db)
        success = await equipment_service.calibrate_device(device_id)
        
        if success:
            logger.info(f"Пользователь {current_user.email} откалибровал устройство {device_id}")
            return {
                "success": True,
                "message": "Калибровка завершена успешно",
                "device_id": device_id,
                "calibration_date": datetime.now()
            }
        else:
            return {
                "success": False,
                "message": "Не удалось выполнить калибровку",
                "device_id": device_id
            }
    except Exception as e:
        logger.error(f"Ошибка калибровки устройства {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/{device_id}/diagnostics", response_model=DiagnosticsResponse)
async def run_device_diagnostics(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR]))
):
    """Запустить диагностику устройства"""
    try:
        equipment_service = get_medical_equipment_service(db)
        results = await equipment_service.run_diagnostics(device_id)
        
        logger.info(f"Пользователь {current_user.email} запустил диагностику устройства {device_id}")
        
        return DiagnosticsResponse(
            device_id=results["device_id"],
            timestamp=results["timestamp"],
            success=results["success"],
            tests=results["tests"],
            error=results.get("error")
        )
    except Exception as e:
        logger.error(f"Ошибка диагностики устройства {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== КОНФИГУРАЦИЯ =====================

@router.put("/devices/{device_id}/config")
async def update_device_config(
    device_id: str,
    request: DeviceConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN]))
):
    """Обновить конфигурацию устройства"""
    try:
        equipment_service = get_medical_equipment_service(db)
        
        # Подготавливаем данные для обновления
        config_data = {}
        if request.name is not None:
            config_data['name'] = request.name
        if request.location is not None:
            config_data['location'] = request.location
        if request.connection_params is not None:
            config_data['connection_params'] = request.connection_params
        if request.maintenance_date is not None:
            config_data['maintenance_date'] = request.maintenance_date
        
        success = await equipment_service.update_device_config(device_id, config_data)
        
        if success:
            logger.info(f"Пользователь {current_user.email} обновил конфигурацию устройства {device_id}")
            return {
                "success": True,
                "message": "Конфигурация устройства обновлена",
                "device_id": device_id
            }
        else:
            return {
                "success": False,
                "message": "Не удалось обновить конфигурацию устройства",
                "device_id": device_id
            }
    except Exception as e:
        logger.error(f"Ошибка обновления конфигурации устройства {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== СТАТИСТИКА =====================

@router.get("/devices/{device_id}/statistics", response_model=StatisticsResponse)
async def get_device_statistics(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Получить статистику устройства"""
    try:
        equipment_service = get_medical_equipment_service(db)
        stats = await equipment_service.get_device_statistics(device_id)
        
        return StatisticsResponse(
            total_measurements=stats["total_measurements"],
            last_measurement=stats["last_measurement"],
            average_quality=stats["average_quality"],
            measurements_today=stats["measurements_today"],
            measurements_this_week=stats["measurements_this_week"]
        )
    except Exception as e:
        logger.error(f"Ошибка получения статистики устройства {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/overview")
async def get_equipment_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """Получить общую статистику оборудования"""
    try:
        equipment_service = get_medical_equipment_service(db)
        devices = await equipment_service.get_all_devices()
        
        # Подсчет статистики
        total_devices = len(devices)
        online_devices = len([d for d in devices if d.status == DeviceStatus.ONLINE])
        offline_devices = len([d for d in devices if d.status == DeviceStatus.OFFLINE])
        error_devices = len([d for d in devices if d.status == DeviceStatus.ERROR])
        
        # Статистика по типам устройств
        device_types = {}
        for device in devices:
            device_type = device.device_type.value
            if device_type not in device_types:
                device_types[device_type] = {"total": 0, "online": 0}
            device_types[device_type]["total"] += 1
            if device.status == DeviceStatus.ONLINE:
                device_types[device_type]["online"] += 1
        
        # Статистика измерений
        all_measurements = await equipment_service.get_measurements(limit=10000)
        total_measurements = len(all_measurements)
        measurements_today = len([m for m in all_measurements if m.timestamp.date() == datetime.now().date()])
        
        return {
            "success": True,
            "overview": {
                "total_devices": total_devices,
                "online_devices": online_devices,
                "offline_devices": offline_devices,
                "error_devices": error_devices,
                "device_types": device_types,
                "total_measurements": total_measurements,
                "measurements_today": measurements_today
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения общей статистики оборудования: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== ЭКСПОРТ =====================

@router.get("/measurements/export")
async def export_measurements(
    format: str = Query("json", pattern="^(json|csv)$", description="Формат экспорта"),
    device_id: Optional[str] = Query(None, description="ID устройства"),
    start_date: Optional[date] = Query(None, description="Начальная дата"),
    end_date: Optional[date] = Query(None, description="Конечная дата"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR]))
):
    """Экспорт измерений"""
    try:
        equipment_service = get_medical_equipment_service(db)
        
        # Преобразуем даты в datetime
        start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
        
        export_data = await equipment_service.export_measurements(
            format=format,
            device_id=device_id,
            start_date=start_datetime,
            end_date=end_datetime
        )
        
        if export_data is None:
            raise HTTPException(status_code=404, detail="Данные для экспорта не найдены")
        
        logger.info(f"Пользователь {current_user.email} экспортировал измерения в формате {format}")
        
        # Определяем content type
        content_type = "application/json" if format == "json" else "text/csv"
        filename = f"measurements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        from fastapi.responses import Response
        return Response(
            content=export_data,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка экспорта измерений: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================

@router.post("/quick-measurement/{device_type}")
async def quick_measurement(
    device_type: str,
    patient_id: Optional[str] = Query(None, description="ID пациента"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Быстрое измерение на первом доступном устройстве указанного типа"""
    try:
        # Проверяем валидность типа устройства
        try:
            device_type_enum = DeviceType(device_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Неверный тип устройства: {device_type}")
        
        equipment_service = get_medical_equipment_service(db)
        devices = await equipment_service.get_all_devices()
        
        # Ищем первое доступное устройство указанного типа
        available_device = None
        for device in devices:
            if (device.device_type == device_type_enum and 
                device.status in [DeviceStatus.ONLINE, DeviceStatus.OFFLINE]):
                available_device = device
                break
        
        if not available_device:
            raise HTTPException(
                status_code=404, 
                detail=f"Нет доступных устройств типа {device_type}"
            )
        
        # Выполняем измерение
        measurement = await equipment_service.take_measurement(
            device_id=available_device.id,
            patient_id=patient_id
        )
        
        if measurement:
            logger.info(f"Быстрое измерение выполнено на устройстве {available_device.id}")
            return {
                "success": True,
                "measurement": MeasurementResponse(
                    device_id=measurement.device_id,
                    device_type=measurement.device_type.value,
                    timestamp=measurement.timestamp,
                    patient_id=measurement.patient_id,
                    measurements=measurement.measurements,
                    raw_data=measurement.raw_data,
                    quality_score=measurement.quality_score,
                    notes=measurement.notes
                ),
                "device_used": {
                    "id": available_device.id,
                    "name": available_device.name,
                    "location": available_device.location
                }
            }
        else:
            raise HTTPException(status_code=400, detail="Не удалось выполнить измерение")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка быстрого измерения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== ИНФОРМАЦИЯ О СИСТЕМЕ =====================

@router.get("/device-types")
async def get_device_types(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.DOCTOR, Roles.REGISTRAR]))
):
    """Получить список поддерживаемых типов устройств"""
    return {
        "success": True,
        "device_types": [
            {
                "value": device_type.value,
                "name": device_type.value.replace('_', ' ').title(),
                "description": _get_device_type_description(device_type)
            }
            for device_type in DeviceType
        ]
    }


@router.get("/connection-types")
async def get_connection_types(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN]))
):
    """Получить список поддерживаемых типов подключения"""
    return {
        "success": True,
        "connection_types": [
            {
                "value": conn_type.value,
                "name": conn_type.value.upper(),
                "description": _get_connection_type_description(conn_type)
            }
            for conn_type in ConnectionType
        ]
    }


def _get_device_type_description(device_type: DeviceType) -> str:
    """Получить описание типа устройства"""
    descriptions = {
        DeviceType.ECG: "Электрокардиограф для записи ЭКГ",
        DeviceType.BLOOD_PRESSURE: "Тонометр для измерения артериального давления",
        DeviceType.PULSE_OXIMETER: "Пульсоксиметр для измерения сатурации кислорода",
        DeviceType.GLUCOMETER: "Глюкометр для измерения уровня глюкозы в крови",
        DeviceType.THERMOMETER: "Термометр для измерения температуры тела",
        DeviceType.SPIROMETER: "Спирометр для исследования функции внешнего дыхания",
        DeviceType.ULTRASOUND: "УЗИ аппарат для ультразвукового исследования",
        DeviceType.XRAY: "Рентгеновский аппарат",
        DeviceType.ANALYZER: "Биохимический анализатор",
        DeviceType.SCALE: "Медицинские весы",
        DeviceType.HEIGHT_METER: "Ростомер для измерения роста"
    }
    return descriptions.get(device_type, "Медицинское устройство")


def _get_connection_type_description(conn_type: ConnectionType) -> str:
    """Получить описание типа подключения"""
    descriptions = {
        ConnectionType.SERIAL: "Последовательное подключение (COM порт)",
        ConnectionType.TCP: "TCP/IP сетевое подключение",
        ConnectionType.UDP: "UDP сетевое подключение",
        ConnectionType.HTTP: "HTTP API подключение",
        ConnectionType.BLUETOOTH: "Bluetooth беспроводное подключение",
        ConnectionType.USB: "USB подключение",
        ConnectionType.MOCK: "Тестовое подключение для демонстрации"
    }
    return descriptions.get(conn_type, "Тип подключения")

