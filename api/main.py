from fastapi import FastAPI, Request
import uvicorn
from mongo import DbOps
import os
from dotenv import load_dotenv
from pydantic import ValidationError
from schema import CreateUser, Device, ClipboardLog, Shared
from database.mysql import MySQLOps
load_dotenv()

user_collection = DbOps(os.getenv("MONGO_URI"), "users")    
mysql_ops = MySQLOps(
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASS", "admin"),
    database=os.getenv("MYSQL_DB", "clipscape"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
)
app = FastAPI()

@app.get("/")
def root():
    return "running"

@app.post("/user")
async def create_user(request: Request):
    try:
        payload = await request.json()
        user = CreateUser.model_validate(payload)  # validates username and email

        if user_collection.collection.find_one({"username": user.username}):
            return {"error": "username already exists"}

        if user_collection.collection.find_one({"email": user.email}):
            return {"error": "email is linked to another account"}


        result = user_collection.insert(
            username=user.username, 
            email=user.email,
            userId=user.userId,
            created_at=user.created_at,
        )
        if isinstance(result, Exception):
            return {"error": str(result)}
        return {"ok": True}
    except ValidationError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)} 

@app.post("/add_device")
async def add_device(request: Request):
    try:
        payload = await request.json()
        data = Device.model_validate(payload) # validate the device name userId
    
    except ValidationError as e:
        return {"error": str(e)}

@app.post("/clipboard_logs")
async def create_clipboard_log(request: Request):
    try:
        payload = await request.json()
        if "status" not in payload:
            payload["status"] = 0
        model = ClipboardLog.model_validate(payload)
        mysql_ops.insert_clipboard_log(model)
        return {"ok": True, "itemId": model.itemId}
    except ValidationError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

@app.post("/share_logs")
async def create_share_log(request: Request):
    try:
        payload = await request.json()
        model = Shared.model_validate(payload)
        mysql_ops.insert_share_log(model)
        return {"ok": True}
    except ValidationError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}        

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)