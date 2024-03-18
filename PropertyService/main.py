from bson import ObjectId
from fastapi import FastAPI, HTTPException, status

from PropertyService.database import collection
from PropertyService.schemas import Item

app = FastAPI()


@app.post("/items/", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(item: Item):
    result = await collection.insert_one(item.model_dump(exclude={"id"}))
    return item


@app.get("/items/{item_id}", response_model=Item, response_model_by_alias=False)
async def create_item(item_id: str):
    if not ObjectId.is_valid(item_id) or (result := await collection.find_one({"_id": ObjectId(item_id)})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item {item_id} not found")
    print("Here2", result)
    return result


@app.get("/items", response_model=list[Item])
async def read_items():
    return await collection.find().to_list(1000)


"""
response_model_include & response_model_exclude can be helpfull for later
"""

