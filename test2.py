from flask_openapi3 import OpenAPI, Info, Tag
from pydantic import BaseModel

info = Info(title="My API", version="1.0.0")
app = OpenAPI(__name__, info=info)

class ItemCreate(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

@app.post("/items")
def create_item(body: ItemCreate):
    """
    Creates a new item.
    """
    # Access validated data from the 'body' object
    print(f"Received item: {body.name}, {body.price}")
    return {"message": "Item created successfully", "data": body.dict()}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)