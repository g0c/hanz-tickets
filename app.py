# v1.0.2

from fastapi import FastAPI, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os
import sqlite3
from datetime import datetime
from ldap3 import Server, Connection, ALL, exceptions

app = FastAPI(title="hanz-back")

# Postavke za Active Directory - Zamijeni s točnim podacima
AD_SERVER = "ldap://10.X.X.X" 
AD_DOMAIN = "interna-domena.hr"

security = HTTPBasic()

# Funkcija za provjeru korisnika u Active Directoryju
def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    try:
        server = Server(AD_SERVER, get_info=ALL)
        user_principal = f"{credentials.username}@{AD_DOMAIN}"
        # Pokušaj spajanja na AD s unesenim korisničkim imenom i lozinkom
        conn = Connection(server, user=user_principal, password=credentials.password, auto_bind=True)
        conn.unbind()
        return credentials.username
    except exceptions.LDAPBindError:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AD Connection error: {str(e)}")

# Montiranje statičnih datoteka kako bi preglednik mogao dohvatiti CSS i JS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Funkcija koja kreira SQLite bazu i tablicu zahtjeva ukoliko već ne postoje
def init_db():
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            request_type TEXT,
            file_path TEXT,
            description TEXT,
            status TEXT DEFAULT 'Pending',
            is_path_verified BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    connection.commit()
    connection.close()

init_db()

# Glavna ruta koja čita i prikazuje HTML sučelje, zaštićena AD prijavom
@app.get("/", response_class=HTMLResponse)
async def root(username: str = Depends(get_current_user)):
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

# Ruta koja prima podatke iz frontend forme, provjerava putanju i sprema zahtjev sa stvarnim AD korisnikom
@app.post("/submit-request")
async def submit_request(
    request_type: str = Form(...),
    file_path: str = Form(...),
    description: str = Form(...),
    username: str = Depends(get_current_user)
):
    path_exists = os.path.exists(file_path)
    
    try:
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO requests (username, request_type, file_path, description, is_path_verified)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, request_type, file_path, description, path_exists))
        connection.commit()
        connection.close()
        
        return {"status": "success", "path_verified": path_exists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))