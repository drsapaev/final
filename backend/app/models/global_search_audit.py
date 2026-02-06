"""
GlobalSearchAudit model for logging search queries and result access.
Required for compliance: any patient data access must be auditable.
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class GlobalSearchAudit(Base):
    """
    Audit log for Global Search feature.
    
    Logs:
    - Search queries (who searched what)
    - Result clicks (which patient/visit/lab was opened)
    
    Does NOT log:
    - Full response content
    - Patient names in plain text
    - Clinical data
    """
    __tablename__ = "global_search_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Who performed the search
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # What was searched
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # What types of results were returned (metadata only)
    result_types: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    
    # What was clicked/opened (null if just searched, didn't open)
    opened_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # patient|visit|lab
    opened_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow,
        index=True
    )
