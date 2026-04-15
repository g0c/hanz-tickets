# v1.1.19
from fastapi import FastAPI, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import sqlite3
import re
import os
import smtplib
import json
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPBindError

app = FastAPI(title="hanz-tickets")

# AD, SMTP i REDMINE Konfiguracija
AD_SERVER = "ldaps://10.2.2.114:636" 
AD_DOMAIN = "hanzekovic.hr"

SMTP_SERVER = "hanzekovic.mail.protection.outlook.com"
SMTP_PORT = 25
MAIL_SENDER = "it-zahtjevi@hanzekovic.hr"
MAIL_RECIPIENT_IT = "support@hanzekovic.hr"

REDMINE_URL = "https://redmine.piopet.hr/issues.json"
# GOC REDMINE_API_KEY = "b581de11949223f96441f16e5e47403c57b07515"
REDMINE_API_KEY = "cfc12c1dfe57144d460e5440ad81ba69acd9d647" # LUC 
REDMINE_PROJECT_ID = 6  

security = HTTPBasic()

VRSTE_ZAHTJEVA = {
    "Backup/Restore": "Povrat podataka (Backup)",
    "Permissions": "Prava pristupa (Folderi/DFS)",
    "Hardware": "Problem s hardverom (PC, Printer)",
    "Software": "Instalacija softvera",
    "Novi Korisnik": "Zahtjev za novog djelatnika",
    "Ostalo": "Ostalo"
}

ODJELI = [
    "Administracija", "Arhiva", "Financije i računovodstvo", "Informatika",
    "Odjel ljudskih potencijala", "Odvjetnici", "Odvjetnički vježbenici",
    "Odvjetnički vježbenici s pravosudnim", "Ostali", "Partneri", "Pisarnica",
    "Porta", "Prevoditelji", "Voditeljica održavanja i sigurnosti"
]

GRADOVI = ["Zagreb", "Split", "Osijek"]

SPOLOVI = {"M": "Muški (M)", "Ž": "Ženski (Ž)"}

# Funkcija za određivanje CSS klase ovisno o statusu zahtjeva
def get_status_class(status):
    mapping = {
        "Pending": "badge-pending",
        "U tijeku": "badge-progress",
        "Završeno": "badge-success",
        "Odbačeno": "badge-rejected"
    }
    return mapping.get(status, "bg-secondary")

# Slanje email obavijesti IT-u i korisniku
def send_it_email(subject, body_content, user_email=None):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = MAIL_SENDER
        recipients = [MAIL_RECIPIENT_IT]
        if user_email:
            recipients.append(user_email)
        msg["To"] = ", ".join(recipients)

        html_template = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="background-color: #2a5298; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">Novi IT Zahtjev</h1>
            </div>
            <div style="padding: 20px; border: 1px solid #ddd; border-top: none;">
                <p style="white-space: pre-wrap;">{body_content}</p>
                <hr style="border: none; border-top: 1px solid #eee;">
                <p style="font-size: 0.8rem; color: #777;">
                    Ovaj email je generiran automatski putem zahtjeva za sustav.<br>
                    Developed by PIOPET 2026.
                </p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_template, "html"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(MAIL_SENDER, recipients, msg.as_string())
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

# Kreiranje tiketa direktno u Redmine sustavu
def create_redmine_issue(subject, description):
    data = {
        "issue": {
            "project_id": REDMINE_PROJECT_ID,
            "subject": subject,
            "description": description
        }
    }
    
    url_with_key = f"{REDMINE_URL}?key={REDMINE_API_KEY}"
    req = urllib.request.Request(url_with_key)
    
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    req.add_header('Content-Type', 'application/json')
    
    jsondata = json.dumps(data).encode('utf-8')
    try:
        response = urllib.request.urlopen(req, jsondata, timeout=10)
        print(f"--- REDMINE USPJEH: {response.getcode()} ---")
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        print(f"--- REDMINE ODBIO! Kod: {e.code}, Razlog: {error_msg} ---")
    except Exception as e:
        print(f"--- REDMINE GENERALNA GREŠKA: {e} ---")

# Autentifikacija korisnika putem Active Directoryja
def get_ad_user_info(username, password):
    try:
        server = Server(AD_SERVER, use_ssl=True, get_info=ALL)
        user_principal = f"{username}@{AD_DOMAIN}"
        conn = Connection(server, user=user_principal, password=password, auto_bind=True)
        conn.search(f"dc=hanzekovic,dc=hr", f"(&(objectClass=user)(sAMAccountName={username}))", attributes=['mail'])
        email = None
        if conn.entries:
            email = str(conn.entries[0].mail) if 'mail' in conn.entries[0] else None
        conn.unbind()
        return {"authenticated": True, "email": email}
    except Exception:
        return {"authenticated": False, "email": None}

# Provjera trenutnog korisnika pomoću Basic Auth-a
def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    user_info = get_ad_user_info(credentials.username, credentials.password)
    if not user_info["authenticated"]:
        raise HTTPException(status_code=401, detail="Neispravni podaci", headers={"WWW-Authenticate": "Basic"})
    return {"username": credentials.username, "email": user_info["email"]}

# Montiranje mape za slike (favicon i ostali vizuali)
app.mount("/images", StaticFiles(directory="images"), name="images")
# Montiranje mape za statičke datoteke (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inicijalizacija SQLite baze podataka
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

# Glavna stranica za predaju zahtjeva
@app.get("/", response_class=HTMLResponse)
async def root(user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
    path = os.path.join("templates", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    options_html = "".join([f'<option value="{k}">{v}</option>' for k, v in VRSTE_ZAHTJEVA.items()])
    odjeli_html = "".join([f'<option value="{o}">{o}</option>' for o in ODJELI])
    gradovi_html = "".join([f'<option value="{g}">{g}</option>' for g in GRADOVI])
    spolovi_html = "".join([f'<option value="{k}">{v}</option>' for k, v in SPOLOVI.items()])
    
    html_content = html_content.replace("{{ request_options }}", options_html)
    html_content = html_content.replace("{{ odjeli_options }}", odjeli_html)
    html_content = html_content.replace("{{ gradovi_options }}", gradovi_html)
    html_content = html_content.replace("{{ spolovi_options }}", spolovi_html)
    html_content = html_content.replace("{{ username }}", username)
    return HTMLResponse(content=html_content)

# Pregled vlastitih zahtjeva korisnika
@app.get("/moji-zahtjevi", response_class=HTMLResponse)
async def my_requests(user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
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
        elif row['status'] == 'Odbačeno' and not row['rating']:
             survey_html = "<small class='text-danger fw-bold'>Zahtjev odbijen</small>"
        elif row['rating']:
            sentiment_map = {"Pozitivno": "😊", "Neutralno": "😐", "Negativno": "🙁"}
            icon = sentiment_map.get(row['rating'], "")
            survey_html = f"<strong>{icon} {row['rating']}</strong>"
        else:
            survey_html = "<small class='text-muted'>U obradi...</small>"

        desc_html = f"{row['description']}"
        if row['feedback']:
            desc_html += f"<hr class='my-1'><small class='text-primary'><strong>IT Komentar:</strong> {row['feedback']}</small>"

        table_rows += f"<tr><td data-sort='{row['id']}'>#{row['id']}</td><td><span class='badge {status_cls}'>{row['status']}</span></td><td>{row['request_type']}</td><td class='text-description'>{desc_html}</td><td>{survey_html}</td><td><small>{row['created_at']}</small></td></tr>"

    path = os.path.join("templates", "moji-zahtjevi.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read().replace("{{ table_rows }}", table_rows).replace("{{ username }}", username)
    return HTMLResponse(content=html)

# Administratorska stranica za upravljanje zahtjevima
@app.get("/zahtjevi-admin", response_class=HTMLResponse)
async def admin_page(user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
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
            <select class="form-select form-select-sm border-2" onchange="openStatusModal({row['id']}, this.value)">
                <option value="Pending" {"selected" if status=="Pending" else ""}>Pending</option>
                <option value="U tijeku" {"selected" if status=="U tijeku" else ""}>U tijeku</option>
                <option value="Završeno" {"selected" if status=="Završeno" else ""}>Završeno</option>
                <option value="Odbačeno" {"selected" if status=="Odbačeno" else ""}>Odbačeno</option>
            </select>
        '''
        rating_val = row['rating'] if row['rating'] else "-"
        
        desc_html = f"{row['description']}"
        if row['feedback']:
            desc_html += f"<hr class='my-1'><small class='text-primary'><strong>Naš odgovor:</strong> {row['feedback']}</small>"

        table_rows += f"""
        <tr>
            <td data-sort='{row['id']}'><strong>#{row['id']}</strong></td>
            <td>{row['username']}</td>
            <td><div class="d-flex align-items-center"><span class="badge {status_cls} me-2">&nbsp;</span> {actions}</div></td>
            <td>{row['request_type']}</td>
            <td><small>{row['file_path'] if row['file_path'] else '-'}</small></td>
            <td class="text-description">{desc_html}</td>
            <td>{rating_val}</td>
            <td><small>{row['created_at']}</small></td>
        </tr>"""

    path = os.path.join("templates", "admin.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read().replace("{{ table_rows }}", table_rows).replace("{{ username }}", username)
    return HTMLResponse(content=html)

# Ruta za spremanje novog zahtjeva u bazu i slanje obavijesti
@app.post("/submit-request")
async def submit_request(request_type: str = Form(...), file_path: str = Form(None), description: str = Form(...), user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
    user_email = user_data["email"]
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('INSERT INTO requests (username, request_type, file_path, description) VALUES (?, ?, ?, ?)', (username, request_type, file_path, description))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    subject = f"IT Zahtjev #{ticket_id}: {request_type} - {username}"
    email_body = f"Korisnik: {username}\nTip: {request_type}\nPutanja: {file_path if file_path else '-'}\n\nOpis:\n{description}"
    send_it_email(subject, email_body, user_email)
    
    redmine_description = f"**Korisnik:** {username}\n**Putanja:** {file_path if file_path else '-'}\n\n**Opis:**\n{description}"
    create_redmine_issue(subject, redmine_description)
    
    return {"status": "success"}

# Ruta za ažuriranje statusa zahtjeva od strane admina
@app.post("/update-status")
async def update_status(
    ticket_id: int = Form(...), 
    new_status: str = Form(...), 
    feedback: str = Form(""), 
    user_data: dict = Depends(get_current_user)
):
    conn = sqlite3.connect("database.db")
    if feedback:
        conn.execute("UPDATE requests SET status = ?, feedback = ? WHERE id = ?", (new_status, feedback, ticket_id))
    else:
        conn.execute("UPDATE requests SET status = ? WHERE id = ?", (new_status, ticket_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

# Ruta za spremanje ocjene zadovoljstva korisnika
@app.post("/submit-survey")
async def submit_survey(ticket_id: int = Form(...), rating: str = Form(...), user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE requests SET rating = ? WHERE id = ? AND username = ?", (rating, ticket_id, username))
    conn.commit()
    conn.close()
    return {"status": "ok"}