# v1.1.9
from fastapi import FastAPI, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import sqlite3
import re
import os
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPBindError

app = FastAPI(title="hanz-tickets")

# AD Konfiguracija
AD_SERVER = "ldaps://10.2.2.114:636" 
AD_DOMAIN = "hanzekovic.hr"

security = HTTPBasic()

# Parametrizacija kategorija
VRSTE_ZAHTJEVA = {
    "Backup/Restore": "Povrat podataka (Backup)",
    "Permissions": "Prava pristupa (Folderi/DFS)",
    "Hardware": "Problem s hardverom (PC, Printer)",
    "Software": "Instalacija softvera",
    "Novi Korisnik": "Zahtjev za novog djelatnika",
    "Ostalo": "Ostalo"
}

# Boje statusa
def get_status_class(status):
    mapping = {
        "Pending": "badge-pending",
        "U tijeku": "badge-progress",
        "Završeno": "badge-success",
        "Odbačeno": "badge-rejected"
    }
    return mapping.get(status, "bg-secondary")

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
            rating TEXT,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    connection.commit()
    connection.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def root(username: str = Depends(get_current_user)):
    path = os.path.join("templates", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        html_content = f.read()
    options_html = "".join([f'<option value="{k}">{v}</option>' for k, v in VRSTE_ZAHTJEVA.items()])
    html_content = re.sub(r"\{\{\s*request_options\s*\}\}", options_html, html_content)
    html_content = re.sub(r"\{\{\s*username\s*\}\}", username, html_content)
    return HTMLResponse(content=html_content)

@app.get("/moji-zahtjevi", response_class=HTMLResponse)
async def my_requests(username: str = Depends(get_current_user)):
    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM requests WHERE username = ? ORDER BY created_at DESC", (username,))
    rows = cursor.fetchall()
    connection.close()

    table_rows = ""
    for row in rows:
        status_cls = get_status_class(row['status'])
        survey_html = ""
        if row['status'] == 'Završeno' and not row['rating']:
            survey_html = f'''
                <div class="btn-group">
                    <button onclick="submitSurvey({row['id']}, 'Pozitivno')" class="btn btn-sm btn-outline-success btn-sentiment">😊</button>
                    <button onclick="submitSurvey({row['id']}, 'Neutralno')" class="btn btn-sm btn-outline-warning btn-sentiment">😐</button>
                    <button onclick="submitSurvey({row['id']}, 'Negativno')" class="btn btn-sm btn-outline-danger btn-sentiment">🙁</button>
                </div>
            '''
        elif row['rating']:
            sentiment_map = {"Pozitivno": "😊", "Neutralno": "😐", "Negativno": "🙁"}
            icon = sentiment_map.get(row['rating'], "")
            survey_html = f"<strong>{icon} {row['rating']}</strong>"
        else:
            survey_html = "<small class='text-muted'>U obradi...</small>"

        table_rows += f"""
        <tr>
            <td>#{row['id']}</td>
            <td><span class="badge {status_cls}">{row['status']}</span></td>
            <td>{row['request_type']}</td>
            <td class="text-description">{row['description']}</td>
            <td>{survey_html}</td>
            <td><small>{row['created_at']}</small></td>
        </tr>"""

    path = os.path.join("templates", "moji-zahtjevi.html")
    with open(path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    html_content = re.sub(r"\{\{\s*table_rows\s*\}\}", table_rows, html_content)
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
        status = row['status']
        status_cls = get_status_class(status)
        actions = f'''
            <select class="form-select form-select-sm border-2" onchange="updateStatus({row['id']}, this.value)">
                <option value="Pending" {"selected" if status=="Pending" else ""}>Pending</option>
                <option value="U tijeku" {"selected" if status=="U tijeku" else ""}>U tijeku</option>
                <option value="Završeno" {"selected" if status=="Završeno" else ""}>Završeno</option>
                <option value="Odbačeno" {"selected" if status=="Odbačeno" else ""}>Odbačeno</option>
            </select>
        '''
        rating_val = row['rating'] if row['rating'] else "-"
        table_rows += f"""
        <tr>
            <td><strong>#{row['id']}</strong></td>
            <td>{row['username']}</td>
            <td><div class="d-flex align-items-center"><span class="badge {status_cls} me-2">&nbsp;</span> {actions}</div></td>
            <td>{row['request_type']}</td>
            <td class="text-description">{row['description']}</td>
            <td>{rating_val}</td>
            <td><small>{row['created_at']}</small></td>
        </tr>"""

    path = os.path.join("templates", "admin.html")
    with open(path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content.replace("{{table_rows}}", table_rows).replace("{{username}}", username))

@app.post("/submit-request")
async def submit_request(request_type: str = Form(...), file_path: str = Form(None), description: str = Form(...), username: str = Depends(get_current_user)):
    conn = sqlite3.connect("database.db")
    conn.execute('INSERT INTO requests (username, request_type, file_path, description) VALUES (?, ?, ?, ?)', (username, request_type, file_path, description))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/update-status")
async def update_status(ticket_id: int = Form(...), new_status: str = Form(...), username: str = Depends(get_current_user)):
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE requests SET status = ? WHERE id = ?", (new_status, ticket_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/submit-survey")
async def submit_survey(ticket_id: int = Form(...), rating: str = Form(...), username: str = Depends(get_current_user)):
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE requests SET rating = ? WHERE id = ? AND username = ?", (rating, ticket_id, username))
    conn.commit()
    conn.close()
    return {"status": "ok"}