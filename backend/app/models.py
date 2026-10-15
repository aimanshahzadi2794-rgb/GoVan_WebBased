"""
ORM models for the GoVan MVP.

Kept intentionally small: enough entities to make every dashboard feature
actually work end-to-end, without dragging in every entity from the full
SRS (billing, CCTV, etc. are documented as later phases, not MVP).
"""
import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Enum, Text, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    driver = "driver"
    passenger = "passenger"
    guardian = "guardian"


class OrganizationType(str, enum.Enum):
    school = "school"
    university = "university"
    company = "company"
    fleet_owner = "fleet_owner"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(Enum(OrganizationType), nullable=False)
    contact_email = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="organization")
    vehicles = relationship("Vehicle", back_populates="organization")
    routes = relationship("Route", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.passenger)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    license_number = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    license_expiry = Column(Date, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    organization = relationship("Organization", back_populates="users")
    guardian_links = relationship(
        "GuardianLink",
        foreign_keys="GuardianLink.guardian_id",
        back_populates="guardian",
        cascade="all, delete-orphan",
    )
    passenger_links = relationship(
        "GuardianLink",
        foreign_keys="GuardianLink.passenger_id",
        back_populates="passenger",
        cascade="all, delete-orphan",
    )

    # A driver profile links back to the driver's own vehicle assignment.
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    vehicle = relationship("Vehicle", back_populates="driver_user", foreign_keys=[vehicle_id])
    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="password_reset_tokens")


class GuardianLink(Base):
    __tablename__ = "guardian_links"
    __table_args__ = (
        # A guardian should only be linked once to a given passenger.
        UniqueConstraint("guardian_id", "passenger_id", name="uq_guardian_passenger"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guardian_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_label = Column("relationship", String, nullable=False)

    guardian = relationship("User", foreign_keys=[guardian_id], back_populates="guardian_links")
    passenger = relationship("User", foreign_keys=[passenger_id], back_populates="passenger_links")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, nullable=False)
    model = Column(String, nullable=False)
    vehicle_type = Column(String, nullable=False, default="van")  # van | bus | car | truck
    fuel_type = Column(String, nullable=False, default="petrol")  # petrol | diesel | hybrid | electric
    ownership_type = Column(String, nullable=False, default="internal")  # internal | external
    capacity = Column(Integer, nullable=False, default=12)
    odometer_km = Column(Integer, nullable=False, default=0)
    insurance_expiry = Column(Date, nullable=True)
    fitness_expiry = Column(Date, nullable=True)
    permit_expiry = Column(Date, nullable=True)
    next_service_due = Column(Date, nullable=True)
    status = Column(String, default="active")  # active | inactive
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    organization = relationship("Organization", back_populates="vehicles")

    driver_user = relationship("User", back_populates="vehicle", foreign_keys="User.vehicle_id", uselist=False)
    routes = relationship("Route", back_populates="vehicle")
    maintenance_records = relationship("MaintenanceRecord", back_populates="vehicle")

    @staticmethod
    def _as_date(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).split("T")[0])
        except ValueError:
            return None

    @property
    def compliance_status(self) -> str:
        """Fleet-ready status computed from fuel policy and critical dates."""
        today = datetime.now(timezone.utc).date()
        critical_dates = [self.insurance_expiry, self.fitness_expiry, self.permit_expiry]

        if (self.fuel_type or "").lower() == "cng":
            return "blocked"
        if any(d and d < today for d in (self._as_date(v) for v in critical_dates)):
            return "blocked"

        service_due = self._as_date(self.next_service_due)
        if service_due and service_due <= today:
            return "service_due"

        warning_dates = [self._as_date(v) for v in critical_dates]
        if any(d and 0 <= (d - today).days <= 30 for d in warning_dates):
            return "attention"
        if service_due and 0 <= (service_due - today).days <= 14:
            return "attention"

        return "compliant"


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    stops = relationship("Stop", back_populates="route", order_by="Stop.sequence", cascade="all, delete-orphan")
    pickup_time = Column(String, default="")
    drop_time = Column(String, default="")
    days_of_week = Column(JSON, nullable=False, default=list)
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    organization = relationship("Organization", back_populates="routes")

    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    vehicle = relationship("Vehicle", back_populates="routes")

    trips = relationship("Trip", back_populates="route")
    bookings = relationship("Booking", back_populates="route")

class Stop(Base):
    __tablename__ = "stops"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    sequence = Column(Integer, nullable=False, default=0)  # order of the stop along the route

    route = relationship("Route", back_populates="stops")

class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="scheduled")  # scheduled | active | completed
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    last_lat = Column(Float, nullable=True)
    last_lng = Column(Float, nullable=True)
    last_accuracy = Column(Float, nullable=True)
    last_location_at = Column(DateTime, nullable=True)

    route = relationship("Route", back_populates="trips")
    driver = relationship("User")
    locations = relationship("TripLocation", back_populates="trip", cascade="all, delete-orphan")
    stop_events = relationship("TripStopEvent", back_populates="trip", cascade="all, delete-orphan")


class TripLocation(Base):
    __tablename__ = "trip_locations"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    trip = relationship("Trip", back_populates="locations")


class TripStopEvent(Base):
    __tablename__ = "trip_stop_events"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    stop_id = Column(Integer, ForeignKey("stops.id", ondelete="SET NULL"), nullable=True, index=True)
    arrived_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    departed_at = Column(DateTime, nullable=True)

    trip = relationship("Trip", back_populates="stop_events")
    stop = relationship("Stop")

    @property
    def dwell_seconds(self):
        if self.departed_at is None:
            return None
        return int((self.departed_at - self.arrived_at).total_seconds())

    @property
    def long_stop(self):
        dwell_seconds = self.dwell_seconds
        return dwell_seconds is not None and dwell_seconds > 300


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    boarding_stop_id = Column(Integer, ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    dropoff_stop_id = Column(Integer, ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="confirmed")  # confirmed | cancelled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    passenger = relationship("User")
    route = relationship("Route", back_populates="bookings")
    boarding_stop = relationship("Stop", foreign_keys=[boarding_stop_id])
    dropoff_stop = relationship("Stop", foreign_keys=[dropoff_stop_id])


class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"

    id = Column(Integer, primary_key=True, index=True)
    raised_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    status = Column(String, default="open")  # open | resolved
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    raised_by = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("event_key", name="uq_notification_event_key"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    event_type = Column(String, nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="SET NULL"), nullable=True)
    alert_id = Column(Integer, ForeignKey("emergency_alerts.id", ondelete="SET NULL"), nullable=True)
    event_key = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime, nullable=True)


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, default="service")  # service | inspection | defect | fuel
    status = Column(String, default="open")  # open | completed
    due_at = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    odometer_km = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    vehicle = relationship("Vehicle", back_populates="maintenance_records")
