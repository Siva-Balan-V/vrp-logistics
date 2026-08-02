"""
SQLAlchemy ORM models for RouteForge.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    plan = Column(String(50), nullable=False, default="free")
    stripe_customer_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="company")
    api_keys = relationship("ApiKey", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    role = Column(String(50), nullable=False, default="member")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="users")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    prefix = Column(String(12), nullable=False)
    permissions = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="api_keys")

    __table_args__ = (Index("idx_api_keys_company", "company_id"),)


class OptimizationJob(Base):
    __tablename__ = "optimization_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), nullable=False, default="pending")
    n_locations = Column(Integer, nullable=False)
    n_vehicles = Column(Integer, nullable=False)
    routing_backend = Column(String(20), nullable=False, default="haversine")
    solver_time_s = Column(Float)
    total_distance_km = Column(Float)
    total_time_min = Column(Float)
    assigned_count = Column(Integer)
    unassigned_count = Column(Integer)
    request_json = Column(JSONB)
    response_json = Column(JSONB)

    __table_args__ = (
        Index("idx_jobs_created", "created_at", postgresql_using="btree"),
        Index("idx_jobs_status", "status"),
    )


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="offline")
    current_lat = Column(Float, nullable=True)
    current_lon = Column(Float, nullable=True)
    last_ping_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_drivers_company", "company_id"),)


class VehicleRoute(Base):
    __tablename__ = "vehicle_routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("optimization_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id = Column(Integer, nullable=False)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True)
    route_json = Column(JSONB, nullable=False)
    distance_km = Column(Float, nullable=False)
    time_minutes = Column(Float, nullable=False)
    packages = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_routes_job", "job_id"),)


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("optimization_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    demand = Column(Integer, nullable=False, default=1)
    label = Column(String(200))
    is_depot = Column(Boolean, nullable=False, default=False)
    assigned = Column(Boolean, nullable=False, default=False)
    vehicle_id = Column(Integer)

    __table_args__ = (
        Index("idx_locations_job", "job_id"),
        Index("idx_locations_assigned", "job_id", "assigned"),
    )


class NotificationConfig(Base):
    __tablename__ = "notification_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, unique=True)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    email_enabled = Column(Boolean, nullable=False, default=False)
    twilio_account_sid = Column(String(255))
    twilio_auth_token = Column(String(255))
    twilio_from_number = Column(String(20))
    smtp_host = Column(String(255))
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(255))
    smtp_password = Column(String(255))
    smtp_from_email = Column(String(255))
    triggers = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True)
    channel = Column(String(20), nullable=False)
    recipient = Column(String(255), nullable=False)
    trigger = Column(String(50), nullable=False)
    message = Column(String(1000), nullable=False)
    status = Column(String(20), nullable=False, default="sent")
    error = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
