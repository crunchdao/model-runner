import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dstack_sdk import AsyncTappdClient
import uvicorn

PORT = 8001

app = FastAPI(debug=False)

log = logging.getLogger(__name__)
log.info(f'Starting DStack api server on port {PORT}')

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

def run_fastapi():
    uvicorn.run("model_runner.dstack:app", host="0.0.0.0", port=PORT, reload=False)

if __name__ == "__main__":
    run_fastapi()
