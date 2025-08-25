from flask import jsonify, Response
from pydantic import BaseModel
from flask_openapi3 import Info, Tag
from flask_openapi3 import OpenAPI
from flask_openapi3.blueprint import APIBlueprint

info = Info(title="Test API", version="0.1.0")
app = OpenAPI(__name__, info=info)
api = APIBlueprint('Test Blueprint', __name__, url_prefix='/api')


default_tag = Tag(name="default")

class TestQuery(BaseModel):
    text: str

"""
@app.post('/test/<string:text>', summary="Test endpoint", tags=[default_tag])
def post_test(path: TestModel) -> Response:
    return jsonify(path.text), 200
"""
    
@app.post('/test2', summary="Test endpoint", tags=[default_tag])
def post_test2(body: TestQuery) -> Response:
    return jsonify(body.text), 200

app.register_api(api)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
