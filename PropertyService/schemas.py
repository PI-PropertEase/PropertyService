from typing import Optional, Annotated
from pydantic import BaseModel, BeforeValidator, Field, AfterValidator
from pydantic_extra_types.phone_numbers import PhoneNumber
from enum import Enum

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
PyObjectId = Annotated[str, BeforeValidator(str)]
TimeHourMinute = Annotated[str, Field(pattern=r'^\d\d:\d\d$')]
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


class Property(BaseModel):
    # The primary key for the model, stored as a `str` on the instance.
    # This will be aliased to `_id` when sent to MongoDB,
    # but provided as `id` in the API requests and responses.
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: int
    title: str
    address: str
    description: str
    number_guests: int
    square_meters: int
    bedrooms: dict[str, Bedroom]
    bathrooms: dict[str, Bathroom]
    amenities: list[Amenity]
    house_rules: HouseRules
    additional_info: str
    cancellation_policy: str
    contacts: list[Contact]
