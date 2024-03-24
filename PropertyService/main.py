from bson import ObjectId
from fastapi import FastAPI, HTTPException, status

from PropertyService.database import collection
from PropertyService.schemas import Property

app = FastAPI()


@app.post("/properties", response_model=Property, status_code=status.HTTP_201_CREATED)
async def create_property(prop: Property):
    result = await collection.insert_one(prop.model_dump(exclude={"id"}))
    return prop


@app.get("/properties/{prop_id}", response_model=Property, response_model_by_alias=False)
async def read_property(prop_id: str):
    if not ObjectId.is_valid(prop_id) or (result := await collection.find_one({"_id": ObjectId(prop_id)})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")
    print("Here2", result)
    return result


@app.get("/properties", response_model=list[Property])
async def read_properties():
    return await collection.find().to_list(1000)


"""
response_model_include & response_model_exclude can be helpfull for later
"""

