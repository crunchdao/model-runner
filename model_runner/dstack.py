from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dstack_sdk import AsyncTappdClient

app = FastAPI()

@app.get("/")
async def get_info():
    client = AsyncTappdClient()
    info = await client.info()
    return JSONResponse(content=info.model_dump())

@app.get("/tdx_quote")
async def tdx_quote(message: str):
    client = AsyncTappdClient()
    result = await client.tdx_quote(message)
    return result
