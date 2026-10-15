from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field, model_validator

from .models import OrganizationType, UserRole


# ---------- Auth / Users ----------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["admin", "passenger", "driver", "guardian"] = "passenger"
    organization_id: Optional[int] = None


class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    organization_id: Optional[int] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    license_expiry: Optional[date] = None
    organization_id: Optional[int] = None


class DriverProfileUpdate(BaseModel):
    phone: Optional[str] = None
    license_number: Optional[str] = None
    license_expiry: Optional[date] = None


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    vehicle_id: Optional[int] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    license_expiry: Optional[date] = None
    organization_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class GuardianLinkCreate(BaseModel):
    guardian_id: int
    relationship: str


class GuardianLinkOut(BaseModel):
    id: int
    guardian_id: int
    passenger_id: int
    relationship: str = Field(validation_alias="relationship_label")

    model_config = ConfigDict(from_attributes=True)


class GuardianPassengerOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    relationship: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OrganizationCreate(BaseModel):
    name: str
    type: OrganizationType
    contact_email: Optional[EmailStr] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[OrganizationType] = None
    contact_email: Optional[EmailStr] = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    type: OrganizationType
    contact_email: Optional[EmailStr]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Vehicles ----------

class VehicleCreate(BaseModel):
    plate_number: str
    model: str
    vehicle_type: str = "van"
    fuel_type: str = "petrol"
    ownership_type: str = "internal"
    capacity: int = 12
    odometer_km: int = 0
    insurance_expiry: Optional[date] = None
    fitness_expiry: Optional[date] = None
    permit_expiry: Optional[date] = None
    next_service_due: Optional[date] = None
    organization_id: Optional[int] = None


class VehicleUpdate(BaseModel):
    plate_number: Optional[str] = None
    model: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=1)
    ownership_type: Optional[Literal["internal", "external"]] = None
    organization_id: Optional[int] = None


class VehicleOut(BaseModel):
    id: int
    plate_number: str
    model: str
    vehicle_type: str
    fuel_type: str
    ownership_type: str
    capacity: int
    odometer_km: int
    insurance_expiry: Optional[date]
    fitness_expiry: Optional[date]
    permit_expiry: Optional[date]
    next_service_due: Optional[date]
    status: str
    compliance_status: str
    on_route: bool = False
    occupied_capacity: int = 0
    available_capacity: int = 0
    organization_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class FleetSummary(BaseModel):
    total_vehicles: int
    active_vehicles: int
    internal_vehicles: int
    external_vehicles: int
    blocked_vehicles: int
    attention_vehicles: int
    total_capacity: int
    on_route: int
    idle: int
    maintenance: int
    offline: int
    utilization_pct: float
    average_occupancy_pct: float
    occupied_capacity: int
    available_capacity: int


# ---------- Drivers (a User with role=driver, optionally linked to a vehicle) ----------

class DriverAssign(BaseModel):
    vehicle_id: Optional[int] = None

# ---------- Stops ----------

class StopCreate(BaseModel):
    name: str
    lat: float
    lng: float
    sequence: int = 0


class StopOut(BaseModel):
    id: int
    name: str
    lat: float
    lng: float
    sequence: int

    model_config = ConfigDict(from_attributes=True)

# ---------- Routes ----------

class RouteCreate(BaseModel):
    name: str
    stops: List[StopCreate] = []
    pickup_time: str = ""
    drop_time: str = ""
    vehicle_id: Optional[int] = None
    days_of_week: List[int] = Field(default_factory=list)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    organization_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_schedule_dates(self):
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must be on or before valid_to")
        if any(day not in range(7) for day in self.days_of_week):
            raise ValueError("days_of_week values must be between 0 (Monday) and 6 (Sunday)")
        return self


class RouteUpdate(BaseModel):
    name: Optional[str] = None
    stops: Optional[List[StopCreate]] = None
    pickup_time: Optional[str] = None
    drop_time: Optional[str] = None
    vehicle_id: Optional[int] = None
    days_of_week: Optional[List[int]] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    organization_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_schedule_dates(self):
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must be on or before valid_to")
        if self.days_of_week is not None and any(day not in range(7) for day in self.days_of_week):
            raise ValueError("days_of_week values must be between 0 (Monday) and 6 (Sunday)")
        return self


class RouteOut(BaseModel):
    id: int
    name: str
    stops: List[StopOut] = []
    pickup_time: str
    drop_time: str
    vehicle_id: Optional[int]
    days_of_week: List[int] = Field(default_factory=list)
    valid_from: Optional[date]
    valid_to: Optional[date]
    organization_id: Optional[int] = None
    vehicle_capacity: Optional[int] = None
    confirmed_bookings: int = 0
    seats_left: Optional[int] = None
    distance_km: Optional[float] = None
    estimated_duration_min: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# ---------- Trips ----------

class TripCreate(BaseModel):
    route_id: int
    driver_id: int


class LocationUpdate(BaseModel):
    lat: float
    lng: float
    accuracy: Optional[float] = None     


class TripOut(BaseModel):
    id: int
    route_id: int
    driver_id: int
    status: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    last_lat: Optional[float]
    last_lng: Optional[float]
    last_accuracy: Optional[float] = None
    last_location_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ReportTripsPerDay(BaseModel):
    date: date
    trips: int


class ReportBookingsPerRoute(BaseModel):
    route_id: int
    route_name: str
    passengers_booked: int


class ReportTripHistoryItem(BaseModel):
    trip_id: int
    route_id: int
    route_name: str
    vehicle_id: Optional[int]
    vehicle_plate: Optional[str]
    driver_id: int
    driver_name: str
    status: str
    created_at: Optional[datetime]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_minutes: Optional[float]
    delay_minutes: Optional[float]
    passengers_booked: int


class ReportSummaryOut(BaseModel):
    trips_per_day: List[ReportTripsPerDay]
    completed_vs_cancelled: dict[str, int]
    on_time_vs_delayed: dict[str, int]
    average_duration_minutes: Optional[float]
    average_delay_minutes: Optional[float]
    passengers_booked_per_route: List[ReportBookingsPerRoute]
    sos_count: int
    trip_history: List[ReportTripHistoryItem]


class TripLocationOut(BaseModel):
    lat: float
    lng: float
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TripStopEventOut(BaseModel):
    id: int
    trip_id: int
    stop_id: Optional[int]
    arrived_at: datetime
    departed_at: Optional[datetime]
    stop_name: Optional[str] = None
    dwell_seconds: Optional[int]
    long_stop: bool

    model_config = ConfigDict(from_attributes=True)


# ---------- Bookings ----------

class BookingCreate(BaseModel):
    route_id: int
    boarding_stop_id: Optional[int] = None
    dropoff_stop_id: Optional[int] = None


class BookingOut(BaseModel):
    id: int
    passenger_id: int
    route_id: int
    route_name: Optional[str] = None
    boarding_stop_id: Optional[int] = None
    boarding_stop_name: Optional[str] = None
    dropoff_stop_id: Optional[int] = None
    dropoff_stop_name: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActiveTripForPassengerOut(BaseModel):
    id: int
    route_id: int
    route_name: str
    driver_id: int
    driver_name: str
    vehicle_plate: Optional[str]
    passenger_id: int
    passenger_name: str
    status: str
    last_lat: Optional[float]
    last_lng: Optional[float]
    last_location_at: Optional[datetime]
    boarding_stop_id: Optional[int]
    boarding_stop_name: Optional[str]
    next_stop_name: Optional[str]
    eta_minutes: Optional[int]
    stops: List[StopOut]

    model_config = ConfigDict(from_attributes=True)


# ---------- Emergency alerts ----------

class AlertCreate(BaseModel):
    trip_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class AlertOut(BaseModel):
    id: int
    raised_by_id: int
    trip_id: Optional[int]
    lat: Optional[float]
    lng: Optional[float]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    event_type: str
    trip_id: Optional[int]
    alert_id: Optional[int]
    created_at: datetime
    read_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ---------- Maintenance ----------

class MaintenanceRecordCreate(BaseModel):
    vehicle_id: int
    title: str
    category: str = "service"
    due_at: Optional[date] = None
    odometer_km: Optional[int] = None
    cost: Optional[float] = None
    notes: str = ""


class MaintenanceComplete(BaseModel):
    notes: str = ""


class MaintenanceRecordOut(BaseModel):
    id: int
    vehicle_id: int
    title: str
    category: str
    status: str
    due_at: Optional[date]
    completed_at: Optional[datetime]
    odometer_km: Optional[int]
    cost: Optional[float]
    notes: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
