"""
ECG/DICOM Service
Сервис для парсинга и анализа DICOM файлов ЭКГ
"""
import os
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def check_pydicom_available() -> bool:
    """Проверяет доступность pydicom"""
    try:
        import pydicom
        return True
    except ImportError:
        logger.warning("pydicom not installed. DICOM parsing will not be available.")
        return False


def parse_dicom_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Парсит DICOM файл и извлекает метаданные и данные ЭКГ
    
    Args:
        file_path: Путь к DICOM файлу
        
    Returns:
        Словарь с метаданными и данными ЭКГ или None при ошибке
    """
    if not check_pydicom_available():
        return None
    
    try:
        import pydicom
        import numpy as np
        
        # Читаем DICOM файл
        ds = pydicom.dcmread(file_path)
        
        # Извлекаем базовые метаданные
        metadata = {
            "patient_name": str(ds.PatientName) if hasattr(ds, 'PatientName') else None,
            "patient_id": str(ds.PatientID) if hasattr(ds, 'PatientID') else None,
            "patient_birth_date": str(ds.PatientBirthDate) if hasattr(ds, 'PatientBirthDate') else None,
            "patient_sex": str(ds.PatientSex) if hasattr(ds, 'PatientSex') else None,
            "study_date": str(ds.StudyDate) if hasattr(ds, 'StudyDate') else None,
            "study_time": str(ds.StudyTime) if hasattr(ds, 'StudyTime') else None,
            "institution_name": str(ds.InstitutionName) if hasattr(ds, 'InstitutionName') else None,
            "manufacturer": str(ds.Manufacturer) if hasattr(ds, 'Manufacturer') else None,
            "modality": str(ds.Modality) if hasattr(ds, 'Modality') else None,
            "sop_class_uid": str(ds.SOPClassUID) if hasattr(ds, 'SOPClassUID') else None,
        }
        
        # Извлекаем параметры ЭКГ если доступны
        ecg_params = extract_ecg_parameters(ds)
        
        # Извлекаем данные кривых
        waveform_data = extract_waveform_data(ds)
        
        return {
            "metadata": metadata,
            "ecg_parameters": ecg_params,
            "waveform_data": waveform_data,
            "is_ecg": is_ecg_dicom(ds),
        }
        
    except Exception as e:
        logger.error(f"Error parsing DICOM file: {e}")
        return None


def extract_ecg_parameters(ds) -> Dict[str, Any]:
    """
    Извлекает параметры ЭКГ из DICOM датасета
    
    Args:
        ds: pydicom Dataset
        
    Returns:
        Словарь с параметрами ЭКГ
    """
    params = {}
    
    try:
        # Waveform Sequence (0x5400, 0x0100)
        if hasattr(ds, 'WaveformSequence'):
            wf_seq = ds.WaveformSequence[0] if ds.WaveformSequence else None
            
            if wf_seq:
                # Частота дискретизации
                if hasattr(wf_seq, 'SamplingFrequency'):
                    params['sampling_frequency'] = float(wf_seq.SamplingFrequency)
                
                # Количество отведений
                if hasattr(wf_seq, 'NumberOfWaveformChannels'):
                    params['num_channels'] = int(wf_seq.NumberOfWaveformChannels)
                
                # Количество сэмплов
                if hasattr(wf_seq, 'NumberOfWaveformSamples'):
                    params['num_samples'] = int(wf_seq.NumberOfWaveformSamples)
        
        # Измеренные параметры из DICOM
        # PR Interval
        if hasattr(ds, 'PRInterval'):
            params['pr_interval'] = float(ds.PRInterval)
        
        # QRS Duration
        if hasattr(ds, 'QRSDuration'):
            params['qrs_duration'] = float(ds.QRSDuration)
        
        # QT Interval
        if hasattr(ds, 'QTInterval'):
            params['qt_interval'] = float(ds.QTInterval)
        
        # Heart Rate
        if hasattr(ds, 'HeartRate'):
            params['heart_rate'] = float(ds.HeartRate)
            
    except Exception as e:
        logger.warning(f"Error extracting ECG parameters: {e}")
    
    return params


def extract_waveform_data(ds) -> Optional[Dict[str, List[float]]]:
    """
    Извлекает данные кривых ЭКГ из DICOM датасета
    
    Args:
        ds: pydicom Dataset
        
    Returns:
        Словарь с данными по каждому отведению
    """
    try:
        import numpy as np
        
        if not hasattr(ds, 'WaveformSequence') or not ds.WaveformSequence:
            return None
        
        waveforms = {}
        
        for wf_idx, wf_item in enumerate(ds.WaveformSequence):
            # Получаем данные
            if hasattr(wf_item, 'WaveformData'):
                # Получаем информацию о каналах
                channels = []
                if hasattr(wf_item, 'ChannelDefinitionSequence'):
                    for ch in wf_item.ChannelDefinitionSequence:
                        channel_name = "Unknown"
                        if hasattr(ch, 'ChannelSourceSequence'):
                            src = ch.ChannelSourceSequence[0]
                            if hasattr(src, 'CodeMeaning'):
                                channel_name = str(src.CodeMeaning)
                        channels.append(channel_name)
                
                # Декодируем данные waveform
                num_channels = int(wf_item.NumberOfWaveformChannels) if hasattr(wf_item, 'NumberOfWaveformChannels') else 1
                num_samples = int(wf_item.NumberOfWaveformSamples) if hasattr(wf_item, 'NumberOfWaveformSamples') else 0
                bits_allocated = int(wf_item.WaveformBitsAllocated) if hasattr(wf_item, 'WaveformBitsAllocated') else 16
                
                if num_samples > 0:
                    # Определяем тип данных
                    if bits_allocated == 8:
                        dtype = np.int8
                    elif bits_allocated == 16:
                        dtype = np.int16
                    else:
                        dtype = np.int32
                    
                    # Преобразуем в numpy array
                    raw_data = np.frombuffer(wf_item.WaveformData, dtype=dtype)
                    
                    # Reshape по каналам
                    if len(raw_data) >= num_channels * num_samples:
                        data_matrix = raw_data[:num_channels * num_samples].reshape(num_samples, num_channels)
                        
                        # Сохраняем каждый канал
                        for ch_idx in range(num_channels):
                            ch_name = channels[ch_idx] if ch_idx < len(channels) else f"Lead_{ch_idx+1}"
                            # Ограничиваем количество точек для JSON
                            max_points = 5000
                            ch_data = data_matrix[:, ch_idx]
                            if len(ch_data) > max_points:
                                # Downsampling
                                step = len(ch_data) // max_points
                                ch_data = ch_data[::step]
                            waveforms[ch_name] = ch_data.tolist()
        
        return waveforms if waveforms else None
        
    except Exception as e:
        logger.error(f"Error extracting waveform data: {e}")
        return None


def is_ecg_dicom(ds) -> bool:
    """
    Проверяет, является ли DICOM файл ЭКГ
    
    Args:
        ds: pydicom Dataset
        
    Returns:
        True если это ЭКГ DICOM
    """
    try:
        # Проверяем Modality
        if hasattr(ds, 'Modality'):
            modality = str(ds.Modality).upper()
            if modality in ('ECG', 'HD'):  # HD = Hemodynamic Waveform
                return True
        
        # Проверяем SOP Class UID для ЭКГ
        ecg_sop_classes = [
            '1.2.840.10008.5.1.4.1.1.9.1.1',  # 12-lead ECG Waveform
            '1.2.840.10008.5.1.4.1.1.9.1.2',  # General ECG Waveform
            '1.2.840.10008.5.1.4.1.1.9.1.3',  # Ambulatory ECG Waveform
            '1.2.840.10008.5.1.4.1.1.9.2.1',  # Hemodynamic Waveform
        ]
        
        if hasattr(ds, 'SOPClassUID'):
            if str(ds.SOPClassUID) in ecg_sop_classes:
                return True
        
        # Проверяем наличие Waveform Sequence
        if hasattr(ds, 'WaveformSequence') and ds.WaveformSequence:
            return True
            
        return False
        
    except Exception as e:
        logger.warning(f"Error checking ECG DICOM: {e}")
        return False


def analyze_ecg_waveforms(waveforms: Dict[str, List[float]], sampling_rate: float = 500.0) -> Dict[str, Any]:
    """
    Анализирует кривые ЭКГ и вычисляет параметры
    
    Args:
        waveforms: Словарь с данными отведений
        sampling_rate: Частота дискретизации в Гц
        
    Returns:
        Словарь с вычисленными параметрами
    """
    try:
        import numpy as np
        
        if not waveforms:
            return {}
        
        # Берем первое отведение для базового анализа
        lead_name = list(waveforms.keys())[0]
        signal = np.array(waveforms[lead_name])
        
        results = {}
        
        # Простой анализ - находим R-пики
        # (В реальном приложении использовать scipy.signal для точного анализа)
        
        # Вычисляем приблизительный ЧСС
        if len(signal) > sampling_rate:
            # Находим пики (упрощённо - локальные максимумы выше порога)
            threshold = np.mean(signal) + 2 * np.std(signal)
            peaks = []
            for i in range(1, len(signal) - 1):
                if signal[i] > threshold and signal[i] > signal[i-1] and signal[i] > signal[i+1]:
                    peaks.append(i)
            
            if len(peaks) > 1:
                # Средний RR интервал
                rr_intervals = np.diff(peaks) / sampling_rate * 1000  # в мс
                avg_rr = np.mean(rr_intervals)
                
                if avg_rr > 0:
                    heart_rate = 60000 / avg_rr  # BPM
                    results['heart_rate'] = round(heart_rate, 1)
                    results['rr_interval'] = round(avg_rr, 1)
        
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing ECG waveforms: {e}")
        return {}


def get_supported_dicom_formats() -> List[str]:
    """Возвращает список поддерживаемых форматов"""
    return ['.dcm', '.dicom', '.dic']


def validate_dicom_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует DICOM файл
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Tuple (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, "File not found"
    
    if not check_pydicom_available():
        return False, "pydicom not available"
    
    try:
        import pydicom
        ds = pydicom.dcmread(file_path)
        
        # Проверяем обязательные поля
        if not hasattr(ds, 'SOPClassUID'):
            return False, "Missing SOPClassUID"
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid DICOM file: {str(e)}"
