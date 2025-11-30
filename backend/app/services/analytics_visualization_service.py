"""
Сервис для визуализации аналитических данных
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ChartData:
    """Структура данных для графика"""

    labels: List[str]
    datasets: List[Dict[str, Any]]
    title: str
    chart_type: str


class AnalyticsVisualizationService:
    """Сервис для создания графиков и диаграмм"""

    def __init__(self):
        self.chart_colors = [
            "#3B82F6",
            "#EF4444",
            "#10B981",
            "#F59E0B",
            "#8B5CF6",
            "#06B6D4",
            "#84CC16",
            "#F97316",
            "#EC4899",
            "#6B7280",
        ]

    def create_line_chart(
        self,
        data: Dict[str, Any],
        title: str,
        x_label: str = "Дата",
        y_label: str = "Значение",
    ) -> ChartData:
        """Создать линейный график"""
        labels = []
        values = []

        if "trends" in data:
            for trend in data["trends"]:
                labels.append(trend.get("date", ""))
                values.append(trend.get("count", 0))

        return ChartData(
            labels=labels,
            datasets=[
                {
                    "label": y_label,
                    "data": values,
                    "borderColor": self.chart_colors[0],
                    "backgroundColor": f"{self.chart_colors[0]}20",
                    "tension": 0.4,
                    "fill": True,
                }
            ],
            title=title,
            chart_type="line",
        )

    def create_bar_chart(
        self,
        data: Dict[str, Any],
        title: str,
        x_label: str = "Категория",
        y_label: str = "Количество",
    ) -> ChartData:
        """Создать столбчатую диаграмму"""
        labels = []
        values = []

        if "by_department" in data:
            for dept, stats in data["by_department"].items():
                labels.append(dept)
                values.append(stats.get("total_entries", 0))
        elif "payment_methods" in data:
            for method in data["payment_methods"]:
                labels.append(method.get("method", ""))
                values.append(method.get("revenue", 0))

        return ChartData(
            labels=labels,
            datasets=[
                {
                    "label": y_label,
                    "data": values,
                    "backgroundColor": self.chart_colors[: len(values)],
                    "borderColor": self.chart_colors[: len(values)],
                    "borderWidth": 1,
                }
            ],
            title=title,
            chart_type="bar",
        )

    def create_pie_chart(self, data: Dict[str, Any], title: str) -> ChartData:
        """Создать круговую диаграмму"""
        labels = []
        values = []

        if "gender_distribution" in data:
            for gender, count in data["gender_distribution"].items():
                labels.append(gender)
                values.append(count)
        elif "age_distribution" in data:
            for age_group, count in data["age_distribution"].items():
                labels.append(age_group)
                values.append(count)

        return ChartData(
            labels=labels,
            datasets=[
                {
                    "label": "Распределение",
                    "data": values,
                    "backgroundColor": self.chart_colors[: len(values)],
                    "borderColor": "#ffffff",
                    "borderWidth": 2,
                }
            ],
            title=title,
            chart_type="doughnut",
        )

    def create_radar_chart(self, data: Dict[str, Any], title: str) -> ChartData:
        """Создать радиальную диаграмму для KPI"""
        labels = [
            "Завершенность",
            "Доходность",
            "Эффективность",
            "Удовлетворенность",
            "Надежность",
        ]

        kpi = data.get("kpi_metrics", {})
        values = [
            kpi.get("completion_rate_percent", 0),
            min(kpi.get("avg_revenue_per_visit", 0) / 1000, 100),  # Нормализуем
            kpi.get("schedule_utilization_percent", 0),
            kpi.get("repeat_visit_rate_percent", 0),
            100 - kpi.get("cancellation_rate_percent", 0),  # Инвертируем отмены
        ]

        return ChartData(
            labels=labels,
            datasets=[
                {
                    "label": "KPI Показатели",
                    "data": values,
                    "backgroundColor": f"{self.chart_colors[0]}30",
                    "borderColor": self.chart_colors[0],
                    "borderWidth": 2,
                    "pointBackgroundColor": self.chart_colors[0],
                    "pointBorderColor": "#ffffff",
                    "pointHoverBackgroundColor": "#ffffff",
                    "pointHoverBorderColor": self.chart_colors[0],
                }
            ],
            title=title,
            chart_type="radar",
        )

    def create_dashboard_charts(
        self, dashboard_data: Dict[str, Any]
    ) -> Dict[str, ChartData]:
        """Создать набор графиков для дашборда"""
        charts = {}

        # График визитов по дням
        if "today" in dashboard_data and "visits" in dashboard_data["today"]:
            charts["visits_trend"] = self.create_line_chart(
                dashboard_data["today"]["visits"],
                "Тренд визитов",
                "Дата",
                "Количество визитов",
            )

        # График доходов по дням
        if "today" in dashboard_data and "revenue" in dashboard_data["today"]:
            charts["revenue_trend"] = self.create_line_chart(
                dashboard_data["today"]["revenue"],
                "Тренд доходов",
                "Дата",
                "Доход (руб.)",
            )

        # Распределение по отделениям
        if "today" in dashboard_data and "visits" in dashboard_data["today"]:
            charts["departments"] = self.create_bar_chart(
                dashboard_data["today"]["visits"],
                "Распределение по отделениям",
                "Отделение",
                "Количество визитов",
            )

        return charts

    def create_kpi_charts(self, kpi_data: Dict[str, Any]) -> Dict[str, ChartData]:
        """Создать графики для KPI"""
        charts = {}

        # Радиальная диаграмма KPI
        charts["kpi_radar"] = self.create_radar_chart(kpi_data, "KPI Показатели")

        # График эффективности по времени
        if "performance_indicators" in kpi_data:
            charts["performance"] = self.create_bar_chart(
                kpi_data, "Показатели эффективности", "Метрика", "Процент"
            )

        return charts

    def create_doctor_performance_charts(
        self, doctor_data: Dict[str, Any]
    ) -> Dict[str, ChartData]:
        """Создать графики для эффективности врачей"""
        charts = {}

        doctors = doctor_data.get("doctor_performance", [])
        if doctors:
            # Топ врачей по эффективности
            top_doctors = sorted(
                doctors, key=lambda x: x.get("performance_score", 0), reverse=True
            )[:5]

            charts["top_doctors"] = ChartData(
                labels=[doc.get("doctor_name", "") for doc in top_doctors],
                datasets=[
                    {
                        "label": "Оценка эффективности",
                        "data": [
                            doc.get("performance_score", 0) for doc in top_doctors
                        ],
                        "backgroundColor": self.chart_colors[: len(top_doctors)],
                        "borderColor": self.chart_colors[: len(top_doctors)],
                        "borderWidth": 1,
                    }
                ],
                title="Топ-5 врачей по эффективности",
                chart_type="bar",
            )

            # Процент завершения по врачам
            charts["completion_rates"] = ChartData(
                labels=[doc.get("doctor_name", "") for doc in top_doctors],
                datasets=[
                    {
                        "label": "Процент завершения",
                        "data": [
                            doc.get("completion_rate_percent", 0) for doc in top_doctors
                        ],
                        "backgroundColor": f"{self.chart_colors[0]}50",
                        "borderColor": self.chart_colors[0],
                        "borderWidth": 2,
                    }
                ],
                title="Процент завершения по врачам",
                chart_type="line",
            )

        return charts

    def create_patient_analytics_charts(
        self, patient_data: Dict[str, Any]
    ) -> Dict[str, ChartData]:
        """Создать графики для аналитики пациентов"""
        charts = {}

        # Распределение по полу
        if "gender_distribution" in patient_data:
            charts["gender_distribution"] = self.create_pie_chart(
                patient_data, "Распределение пациентов по полу"
            )

        # Распределение по возрастным группам
        if "age_distribution" in patient_data:
            charts["age_distribution"] = self.create_bar_chart(
                patient_data,
                "Распределение по возрастным группам",
                "Возрастная группа",
                "Количество пациентов",
            )

        # Топ диагнозов
        if "top_diagnoses" in patient_data:
            diagnoses = patient_data["top_diagnoses"][:5]  # Топ-5
            charts["top_diagnoses"] = ChartData(
                labels=[diag.get("icd10", "") for diag in diagnoses],
                datasets=[
                    {
                        "label": "Количество случаев",
                        "data": [diag.get("count", 0) for diag in diagnoses],
                        "backgroundColor": self.chart_colors[: len(diagnoses)],
                        "borderColor": self.chart_colors[: len(diagnoses)],
                        "borderWidth": 1,
                    }
                ],
                title="Топ-5 диагнозов",
                chart_type="bar",
            )

        return charts

    def create_revenue_charts(
        self, revenue_data: Dict[str, Any]
    ) -> Dict[str, ChartData]:
        """Создать графики для аналитики доходов"""
        charts = {}

        # Доход по дням недели
        if "daily_revenue" in revenue_data:
            daily_revenue = revenue_data["daily_revenue"]
            days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            values = [daily_revenue.get(str(i), 0) for i in range(7)]

            charts["daily_revenue"] = ChartData(
                labels=days,
                datasets=[
                    {
                        "label": "Доход (руб.)",
                        "data": values,
                        "backgroundColor": f"{self.chart_colors[0]}50",
                        "borderColor": self.chart_colors[0],
                        "borderWidth": 2,
                        "tension": 0.4,
                    }
                ],
                title="Доход по дням недели",
                chart_type="line",
            )

        # Доход по методам оплаты
        if "payment_methods" in revenue_data:
            charts["payment_methods"] = self.create_pie_chart(
                revenue_data, "Доход по методам оплаты"
            )

        return charts

    def create_comprehensive_visualization(
        self, comprehensive_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Создать полную визуализацию для комплексного отчета"""
        visualization = {
            "charts": {},
            "summary": {
                "total_charts": 0,
                "chart_types": [],
                "generated_at": datetime.utcnow().isoformat(),
            },
        }

        # KPI графики
        if "kpi_metrics" in comprehensive_data:
            kpi_charts = self.create_kpi_charts(comprehensive_data["kpi_metrics"])
            visualization["charts"]["kpi"] = kpi_charts

        # Графики врачей
        if "doctor_performance" in comprehensive_data:
            doctor_charts = self.create_doctor_performance_charts(
                comprehensive_data["doctor_performance"]
            )
            visualization["charts"]["doctors"] = doctor_charts

        # Графики пациентов
        if "patient_analytics" in comprehensive_data:
            patient_charts = self.create_patient_analytics_charts(
                comprehensive_data["patient_analytics"]
            )
            visualization["charts"]["patients"] = patient_charts

        # Графики доходов
        if "revenue_analytics" in comprehensive_data:
            revenue_charts = self.create_revenue_charts(
                comprehensive_data["revenue_analytics"]
            )
            visualization["charts"]["revenue"] = revenue_charts

        # Подсчитываем общую статистику
        total_charts = sum(len(charts) for charts in visualization["charts"].values())
        chart_types = set()
        for charts in visualization["charts"].values():
            for chart in charts.values():
                chart_types.add(chart.chart_type)

        visualization["summary"]["total_charts"] = total_charts
        visualization["summary"]["chart_types"] = list(chart_types)

        return visualization

    def get_chart_config(self, chart_data: ChartData) -> Dict[str, Any]:
        """Получить конфигурацию для Chart.js"""
        base_config = {
            "type": chart_data.chart_type,
            "data": {"labels": chart_data.labels, "datasets": chart_data.datasets},
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": chart_data.title,
                        "font": {"size": 16, "weight": "bold"},
                    },
                    "legend": {"display": True, "position": "top"},
                },
            },
        }

        # Специфичные настройки для разных типов графиков
        if chart_data.chart_type == "line":
            base_config["options"]["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Значение"},
                },
                "x": {"title": {"display": True, "text": "Дата"}},
            }
        elif chart_data.chart_type == "bar":
            base_config["options"]["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Количество"},
                }
            }
        elif chart_data.chart_type == "radar":
            base_config["options"]["scales"] = {
                "r": {
                    "beginAtZero": True,
                    "max": 100,
                    "title": {"display": True, "text": "Процент"},
                }
            }

        return base_config


# Глобальный экземпляр сервиса
analytics_visualization_service = AnalyticsVisualizationService()


def get_analytics_visualization_service() -> AnalyticsVisualizationService:
    """Получить экземпляр сервиса визуализации"""
    return analytics_visualization_service
