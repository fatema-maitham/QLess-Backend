# models/audit_log.py
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class AuditLogModel(BaseModel):
    __tablename__ = "admin_audit_logs"

    admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)  # e.g. approve_business, deactivate_user
    entity_type = Column(String, nullable=False)  # e.g. business, user, branch
    entity_id = Column(Integer, nullable=True)
    description = Column(String)

    admin = relationship("UserModel")
