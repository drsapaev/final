"""Response contract for the Admin public-site analytics report."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt


class PublicSiteAnalyticsDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_day: date
    site_views: NonNegativeInt
    phone_clicks: NonNegativeInt
    booking_form_opens: NonNegativeInt
    booking_requests_submitted: NonNegativeInt


class PublicSiteAnalyticsReportOut(BaseModel):
    enabled: bool = Field(description="Whether new browser events are accepted.")
    days: list[PublicSiteAnalyticsDayOut] = Field(
        description="Daily totals for the latest 30 Tashkent calendar days, oldest first."
    )
