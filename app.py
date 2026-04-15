# v1.1.48
# Invisible Signature: Created by g0c - Hanza IT Infrastructure 2026

from fastapi import FastAPI, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import sqlite3
import os
import smtplib
import json
import urllib.request
import urllib.error
from email.utils import formatdate, make_msgid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from ldap3 import Server, Connection, ALL

app = FastAPI(title="hanz-tickets")

# --- KONFIGURACIJA ---
AD_SERVER = "ldaps://10.2.2.114:636" 
AD_DOMAIN = "hanzekovic.hr"

# Popis administratora s ovlastima za /zahtjevi-admin
ADMIN_USERS = ["a.gkonjic", "a.lkoscec", "a.lhancic"] 

SMTP_SERVER = "hanzekovic.mail.protection.outlook.com"
SMTP_PORT = 25
MAIL_SENDER = "support@hanzekovic.hr" 
MAIL_RECIPIENT_IT = "nadzor@hanzekovic.hr"

REDMINE_URL = "https://redmine.piopet.hr/issues"
REDMINE_API_KEY = "cfc12c1dfe57144d460e5440ad81ba69acd9d647" 
REDMINE_PROJECT_ID = 6  
REDMINE_TRACKER_ID = 4 

LOGO_PATH = "images/hanzekovic-logo.png" 

security = HTTPBasic()

# --- DEFINICIJE ZAHTJEVA, ODJELA I GRADOVA ---
VRSTE_ZAHTJEVA = {
    "Permissions": "Prava pristupa (Folderi/DFS)",
    "Hardware": "Problem s hardverom (PC, Printer)",
    "Software": "Instalacija softvera",
    "Novi Korisnik": "Zahtjev za novog djelatnika",
    "Backup/Restore": "Povrat podataka (Restore)",
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

# --- POMOĆNE FUNKCIJE ---

def get_status_class(status):
    mapping = {
        "Pending": "badge-pending",
        "U tijeku": "badge-progress",
        "Završeno": "badge-success",
        "Odbačeno": "badge-rejected"
    }
    return mapping.get(status, "bg-secondary")

# Slanje profesionalno formatiranog emaila s ispravljenom logikom statusa
def send_professional_email(subject, user_full_name, ticket_id, request_type, description, status, feedback="", user_email=None):
    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = f"IT Podrska <{MAIL_SENDER}>"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=AD_DOMAIN)
        msg["X-Mailer"] = "Hanza-IT-Portal-v1.1.48"
        
        recipients = [MAIL_RECIPIENT_IT]
        if user_email and "@" in str(user_email):
            recipients.append(user_email)
        msg["To"] = ", ".join(recipients)
        
        # LOGIKA ZA DINAMIČKI HEADER I TEKST
        if status == "Završeno":
            h_color, s_label, action_text = "#28a745", "RIJEŠEN", "je uspješno RIJEŠEN"
        elif status == "Odbačeno":
            h_color, s_label, action_text = "#dc3545", "ODBAČEN", "je ODBAČEN"
        elif status == "U tijeku":
            h_color, s_label, action_text = "#007bff", "U TIJEKU", "je trenutno U TIJEKU"
        else:
            h_color, s_label, action_text = "#1e3c72", "ZAPRIMLJEN", "je uspješno ZAPRIMLJEN"
            
        f_div = f"""
        <div style='background:#eef6ff;padding:15px;border-left:4px solid #3498db;margin-top:20px;'>
            <strong style='color:#1e3c72;'>IT Komentar / Uputa:</strong><br>
            <p style='margin:5px 0 0; color:#333;'>{feedback}</p>
        </div>""" if feedback else ""

        html = f"""
        <html><body style="font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f7f6;padding:20px;margin:0;">
            <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;border:1px solid #ddd;box-shadow:0 4px 10px rgba(0,0,0,0.05);">
                <div style="background:{h_color};padding:25px;text-align:center;">
                    <img src="cid:company_logo" alt="Logo" style="max-height:45px;"><br>
                    <span style="color:white;font-weight:bold;letter-spacing:1px;font-size:11px;text-transform:uppercase;">Status: {s_label}</span>
                </div>
                <div style="padding:35px;">
                    <p style="font-size:16px;">Poštovani/a <strong>{user_full_name}</strong>,</p>
                    <p style="color:#555;">Obavještavamo Vas da Vaš zahtjev <strong>#{ticket_id}</strong> {action_text}.</p>
                    <table style="width:100%;font-size:14px;margin-top:20px;border-collapse:collapse;color:#444;">
                        <tr><td style="padding:10px;border-bottom:1px solid #eee;color:#888;width:30%;">Kategorija:</td><td style="padding:10px;border-bottom:1px solid #eee;font-weight:bold;">{request_type}</td></tr>
                        <tr><td style="padding:10px;color:#888;vertical-align:top;">Opis zahtjeva:</td><td style="padding:10px;white-space:pre-wrap;background:#fcfcfc;border:1px solid #f0f0f0;">{description}</td></tr>
                    </table>
                    {f_div}
                    <div style="text-align: center; margin-top: 35px;">
                        <a href="https://it-podrska.hanzekovic.hr/moji-zahtjevi" style="background:#2a5298;color:#fff;padding:14px 28px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block;">Provjeri moje zahtjeve</a>
                    </div>
                </div>
                <div style="background:#f8f9fa;padding:15px;text-align:center;color:#999;font-size:10px;border-top:1px solid #eee;">
                    <p style="margin:0;">Ovo je automatizirana poruka sustava PIOPET 2026 | Hanza IT</p>
                </div>
            </div>
        </body></html>"""
        
        msg.attach(MIMEText(html, "html"))

        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-ID", "<company_logo>")
                img.add_header("Content-Disposition", "inline", filename="logo.png")
                msg.attach(img)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(MAIL_SENDER, recipients, msg.as_string())
    except Exception as e:
        print(f"SMTP Error: {e}")

# --- REDMINE FUNKCIJE (ZAKOMENTIRANE) ---
def create_redmine_issue(subject, description): return 0
def update_redmine_issue(redmine_id, status_name, feedback): pass

# --- ACTIVE DIRECTORY AUTENTIFIKACIJA ---
def get_ad_user_info(username, password):
    try:
        server = Server(AD_SERVER, use_ssl=True, get_info=ALL)
        conn = Connection(server, user=f"{username}@{AD_DOMAIN}", password=password, auto_bind=True)
        if conn.bound:
            conn.search(f"dc=hanzekovic,dc=hr", f"(&(objectClass=user)(sAMAccountName={username}))", attributes=['mail', 'displayName'])
            if conn.entries:
                email = str(conn.entries[0].mail) if 'mail' in conn.entries[0] else None
                full_name = str(conn.entries[0].displayName) if 'displayName' in conn.entries[0] else username
                conn.unbind()
                return {"authenticated": True, "email": email, "full_name": full_name}
    except Exception: pass
    return {"authenticated": False, "email": None, "full_name": username}

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    user_info = get_ad_user_info(credentials.username, credentials.password)
    if not user_info["authenticated"]: raise HTTPException(status_code=401)
    return {"username": credentials.username, "email": user_info["email"], "full_name": user_info["full_name"]}

# --- KONFIGURACIJA ---
app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, full_name TEXT, request_type TEXT, file_path TEXT, description TEXT, status TEXT DEFAULT 'Pending', rating TEXT, feedback TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, redmine_id INTEGER)''')
    cursor.execute("PRAGMA table_info(requests)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'full_name' not in cols: cursor.execute("ALTER TABLE requests ADD COLUMN full_name TEXT")
    if 'redmine_id' not in cols: cursor.execute("ALTER TABLE requests ADD COLUMN redmine_id INTEGER")
    conn.commit(); conn.close()

init_db()

# --- RUTE ---

@app.get("/", response_class=HTMLResponse)
async def root(user_data: dict = Depends(get_current_user)):
    path = os.path.join("templates", "index.html")
    with open(path, "r", encoding="utf-8") as f: html = f.read()
    
    req_options = "".join([f'<option value="{k}">{v}</option>' for k, v in VRSTE_ZAHTJEVA.items()])
    grad_options = "".join([f'<option value="{g}">{g}</option>' for g in GRADOVI])
    odj_options = "".join([f'<option value="{o}">{o}</option>' for o in ODJELI])
    spol_options = "".join([f'<option value="{k}">{v}</option>' for k, v in SPOLOVI.items()])
    
    html = html.replace("{{ request_options }}", req_options)
    html = html.replace("{{ gradovi_options }}", grad_options)
    html = html.replace("{{ odjeli_options }}", odj_options)
    html = html.replace("{{ spolovi_options }}", spol_options)
    html = html.replace("{{ username }}", user_data["full_name"])
    return HTMLResponse(content=html)

@app.get("/moji-zahtjevi", response_class=HTMLResponse)
async def my_requests(user_data: dict = Depends(get_current_user)):
    conn = sqlite3.connect("database.db"); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM requests WHERE username = ? ORDER BY id DESC", (user_data["username"],)).fetchall()
    conn.close()
    
    table_rows = ""
    for r in rows:
        status_cls = get_status_class(r['status'])
        survey_html = ""
        if r['status'] == 'Završeno' and not r['rating']:
            survey_html = f'''<div class="btn-group"><button onclick="submitSurvey({r['id']}, 'Pozitivno')" class="btn btn-sm btn-outline-success">😊</button><button onclick="submitSurvey({r['id']}, 'Neutralno')" class="btn btn-sm btn-outline-warning">😐</button><button onclick="submitSurvey({r['id']}, 'Negativno')" class="btn btn-sm btn-outline-danger">🙁</button></div>'''
        elif r['rating']:
            s_map = {"Pozitivno": "😊", "Neutralno": "😐", "Negativno": "🙁"}
            survey_html = f"<strong>{s_map.get(r['rating'], '')} {r['rating']}</strong>"
        else:
            survey_html = "<small class='text-muted'>U obradi...</small>"
        
        desc = f"{r['description']}"
        if r['feedback']: desc += f"<hr class='my-1'><small class='text-primary'><strong>IT Odgovor:</strong> {r['feedback']}</small>"
        
        table_rows += f"<tr><td data-sort='{r['id']}'>#{r['id']}</td><td><span class='badge {status_cls}'>{r['status']}</span></td><td>{r['request_type']}</td><td class='text-description'>{desc}</td><td>{survey_html}</td><td><small>{r['created_at']}</small></td></tr>"
    
    path = os.path.join("templates", "moji-zahtjevi.html")
    with open(path, "r", encoding="utf-8") as f: return HTMLResponse(content=f.read().replace("{{ table_rows }}", table_rows).replace("{{ username }}", user_data["full_name"]))

@app.get("/zahtjevi-admin", response_class=HTMLResponse)
async def admin_page(user_data: dict = Depends(get_current_user)):
    if user_data["username"] not in ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Pristup zabranjen.")

    conn = sqlite3.connect("database.db"); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    conn.close()
    
    table_rows = ""
    for r in rows:
        actions = f'''<select class="form-select form-select-sm" onchange="openStatusModal({r['id']}, this.value)">
                <option value="Pending" {"selected" if r['status']=="Pending" else ""}>Pending</option>
                <option value="U tijeku" {"selected" if r['status']=="U tijeku" else ""}>U tijeku</option>
                <option value="Završeno" {"selected" if r['status']=="Završeno" else ""}>Završeno</option>
                <option value="Odbačeno" {"selected" if r['status']=="Odbačeno" else ""}>Odbačeno</option></select>'''
        
        desc = f"{r['description']}"
        if r['feedback']: desc += f"<hr class='my-1'><small class='text-primary'><strong>Odgovor:</strong> {r['feedback']}</small>"
        
        table_rows += f"<tr><td data-sort='{r['id']}'><strong>#{r['id']}</strong></td><td>{r['full_name']}</td><td>{actions}</td><td>{r['request_type']}</td><td>#{r['redmine_id']}</td><td class='text-description'>{desc}</td><td>{r['rating'] if r['rating'] else '-'}</td><td><small>{r['created_at']}</small></td></tr>"
    
    path = os.path.join("templates", "admin.html")
    with open(path, "r", encoding="utf-8") as f: return HTMLResponse(content=f.read().replace("{{ table_rows }}", table_rows).replace("{{ username }}", user_data["full_name"]))

@app.post("/submit-request")
async def submit_request(request_type: str = Form(...), description: str = Form(...), user_data: dict = Depends(get_current_user)):
    r_id = create_redmine_issue(f"IT Zahtjev: {request_type} - {user_data['full_name']}", description)
    conn = sqlite3.connect("database.db"); cursor = conn.cursor()
    cursor.execute('INSERT INTO requests (username, full_name, request_type, description, redmine_id) VALUES (?, ?, ?, ?, ?)', 
                   (user_data["username"], user_data["full_name"], request_type, description, r_id))
    tid = cursor.lastrowid; conn.commit(); conn.close()
    
    send_professional_email(f"Zaprimljen IT zahtjev #{tid}", user_data["full_name"], tid, request_type, description, "Pending", "", user_data["email"])
    return {"status": "success"}

@app.post("/update-status")
async def update_status(ticket_id: int = Form(...), new_status: str = Form(...), feedback: str = Form(""), user_data: dict = Depends(get_current_user)):
    if user_data["username"] not in ADMIN_USERS: raise HTTPException(status_code=403)
    
    conn = sqlite3.connect("database.db"); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM requests WHERE id = ?", (ticket_id,)).fetchone()
    if row:
        conn.execute("UPDATE requests SET status = ?, feedback = ? WHERE id = ?", (new_status, feedback, ticket_id))
        conn.commit(); update_redmine_issue(row['redmine_id'], new_status, feedback)
        
        u_info = get_ad_user_info(row['username'], "bypass") 
        send_professional_email(f"Promjena statusa zahtjeva #{ticket_id}", row['full_name'], ticket_id, row['request_type'], row['description'], new_status, feedback, u_info["email"])
    conn.close(); return {"status": "ok"}

@app.post("/submit-survey")
async def submit_survey(ticket_id: int = Form(...), rating: str = Form(...), user_data: dict = Depends(get_current_user)):
    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE requests SET rating = ? WHERE id = ? AND username = ?", (rating, ticket_id, user_data['username']))
    conn.commit(); conn.close()
    return {"status": "ok"}