from fastapi import FastAPI
from .routers import auth, users, products, orders
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
origins = ["*"]

@app.get("/")
async def root():
    return {"message": "this is root endpoint"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(orders.router)
