# v1.1.2
from fastapi import FastAPI, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import sqlite3
import re  # Za pametnije pretraživanje teksta
import os
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPBindError

app = FastAPI(title="zahtjevi-ticketing")

# AD Konfiguracija
AD_SERVER = "ldaps://10.2.2.114:636" 
AD_DOMAIN = "hanzekovic.hr"

security = HTTPBasic()

# Centralno mjesto za kategorije
VRSTE_ZAHTJEVA = {
    "Backup/Restore": "Povrat podataka (Backup)",
    "Permissions": "Prava pristupa (Folderi/DFS)",
    "Hardware": "Problem s hardverom (PC, Printer)",
    "Software": "Instalacija softvera",
    "Novi Korisnik": "Zahtjev za novog djelatnika",
    "Ostalo": "Ostalo"
}

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    try:
        server = Server(AD_SERVER, use_ssl=True, get_info=ALL)
        user_principal = f"{credentials.username}@{AD_DOMAIN}"
        conn = Connection(server, user=user_principal, password=credentials.password, auto_bind=True)
        conn.unbind()
        return credentials.username
    except LDAPBindError:
        raise HTTPException(status_code=401, detail="Neispravni podaci", headers={"WWW-Authenticate": "Basic"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AD Error: {str(e)}")

app.mount("/static", StaticFiles(directory="static"), name="static")

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
            is_path_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    connection.commit()
    connection.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def root(username: str = Depends(get_current_user)):
    # Putanja do predloška - provjeravamo točno templates mapu
    path = os.path.join("templates", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Generiranje HTML opcija
    options_html = "".join([f'<option value="{k}">{v}</option>' for k, v in VRSTE_ZAHTJEVA.items()])
    
    # Koristimo REGEX koji ignorira razmake unutar {{ }}
    html_content = re.sub(r"\{\{\s*request_options\s*\}\}", options_html, html_content)
    html_content = re.sub(r"\{\{\s*username\s*\}\}", username, html_content)
    
    return HTMLResponse(content=html_content)

@app.get("/zahtjevi-admin", response_class=HTMLResponse)
async def admin_page(username: str = Depends(get_current_user)):
    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM requests ORDER BY created_at DESC")
    rows = cursor.fetchall()
    connection.close()

    table_rows = ""
    for row in rows:
        status_class = "bg-pending" if row['status'] == 'Pending' else "bg-success-vibrant"
        table_rows += f"""
        <tr>
            <td><strong>#{row['id']}</strong></td>
            <td>{row['username']}</td>
            <td><span class="badge {status_class}">{row['status']}</span></td>
            <td><span class="text-primary fw-bold">{row['request_type']}</span></td>
            <td><code class="text-dark bg-light p-1 rounded">{row['file_path'] if row['file_path'] else '-'}</code></td>
            <td>{row['description']}</td>
            <td><small class="text-muted">{row['created_at']}</small></td>
        </tr>
        """

    path = os.path.join("templates", "admin.html")
    with open(path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    html_content = re.sub(r"\{\{\s*table_rows\s*\}\}", table_rows, html_content)
    html_content = re.sub(r"\{\{\s*username\s*\}\}", username, html_content)
    return HTMLResponse(content=html_content)

@app.post("/submit-request")
async def submit_request(
    request_type: str = Form(...),
    file_path: str = Form(None),
    description: str = Form(...),
    username: str = Depends(get_current_user)
):
    try:
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO requests (username, request_type, file_path, description)
            VALUES (?, ?, ?, ?)
        ''', (username, request_type, file_path, description))
        connection.commit()
        connection.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))