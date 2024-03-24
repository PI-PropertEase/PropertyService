from bson import ObjectId
from fastapi import FastAPI, HTTPException, status

from PropertyService.database import collection
from PropertyService.schemas import Property

app = FastAPI()


@app.get("/properties", response_model=list[Property])
async def read_properties(user_id: int = None):
    return await collection.find({} if user_id is None else {'user_id': user_id}).to_list(1000)


@app.get("/properties/{prop_id}", response_model=Property, response_model_by_alias=False)
async def read_property(prop_id: str):
    if not ObjectId.is_valid(prop_id) or (result := await collection.find_one({"_id": ObjectId(prop_id)})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")
    return result


@app.post("/properties", response_model=Property, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_property(prop: Property):
    property_dict = prop.model_dump(exclude={"id"})
    created_property = await collection.insert_one(property_dict)
    # property_dict automatically gets id after insertion
    return property_dict
