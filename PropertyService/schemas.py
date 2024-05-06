from typing import Optional, Annotated
from pydantic import BaseModel, BeforeValidator, Field, EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber
from enum import Enum

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
PyObjectId = Annotated[str, BeforeValidator(str)]
TimeHourMinute = Annotated[str, Field(pattern=r'^(2[0-3]|[01][0-9]):([0-5][0-9])$')]
PhoneNumber.phone_format = 'E164'  # 'INTERNATIONAL'


class TimeSlot(BaseModel):
    begin_time: TimeHourMinute
    end_time: TimeHourMinute


class HouseRules(BaseModel):
    check_in: TimeSlot
    check_out: TimeSlot
    smoking: bool
    parties: bool
    rest_time: TimeSlot
    allow_pets: bool


class Amenity(str, Enum):
    FREE_WIFI = "free_wifi"
    PARKING_SPACE = "parking_space"
    AIR_CONDITIONER = "air_conditioner"
    POOL = "pool"
    KITCHEN = "kitchen"


class BathroomFixture(str, Enum):
    BATHTUB = "bathtub"
    SHOWER = "shower"
    BIDET = "bidet"
    TOILET = "toilet"


class Bathroom(BaseModel):
    fixtures: list[BathroomFixture]


class BedType(str, Enum):
    SINGLE = "single"
    QUEEN = "queen"
    KING = "king"


class Bed(BaseModel):
    number_beds: int
    type: BedType


class Bedroom(BaseModel):
    beds: list[Bed]


class Contact(BaseModel):
    name: str
    phone_number: PhoneNumber


class PropertyBase(BaseModel):
    pass


class Property(PropertyBase):
    # The primary key for the model, stored as a `str` on the instance.
    # This will be aliased to `_id` when sent to MongoDB,
    # but provided as `id` in the API requests and responses.
    id: Optional[int] = Field(alias="_id", default=None)
    user_email: EmailStr
    title: str
    address: str
    description: str
    price: float
    number_guests: int
    square_meters: int
    bedrooms: dict[str, Bedroom]
    bathrooms: dict[str, Bathroom]
    amenities: list[Amenity]
    # if False, price updates will be set to the value that was updated
    # if True, price updates will be set a bit higher to compensate for commission, so property owner 
    # gets the value he set whenever any reservation is made 
    after_commission: bool = False
    house_rules: HouseRules
    additional_info: str
    cancellation_policy: str
    contacts: list[Contact]
    recommended_price: Optional[float] = None
    update_price_automatically: Optional[bool] = False


class UpdateProperty(PropertyBase):
    title: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    number_guests: Optional[int] = None
    square_meters: Optional[int] = None
    bedrooms: Optional[dict[str, Bedroom]] = None
    bathrooms: Optional[dict[str, Bathroom]] = None
    amenities: Optional[list[Amenity]] = None
    after_commission: Optional[bool] = None
    house_rules: Optional[HouseRules] = None
    additional_info: Optional[str] = None
    cancellation_policy: Optional[str] = None
    contacts: Optional[list[Contact]] = None
    update_price_automatically: Optional[bool] = None

class PropertyForAnalytics(BaseModel):
    id: str
    latitude: float
    longitude: float
    bathrooms: int
    bedrooms: int
    beds: int
    number_of_guests: int
    num_amenities: int

