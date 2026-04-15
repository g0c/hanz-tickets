# Hanza IT Support Portal v1.1.48
**Razvio: g0c | PIOPET 2026**

Lagan i brz IT ticketing sustav izgrađen pomoću **FastAPI** okvira. Sadrži **Active Directory** autentifikaciju, **SQLite** bazu podataka te automatizirane **Outlook/SMTP** obavijesti.

## 🚀 Mogućnosti
* **AD Autentifikacija:** Prijava pomoću domenskih podataka putem LDAPS protokola.
* **Prepoznavanje identiteta:** Automatski dohvaća `displayName` (Ime i Prezime) i email adresu iz AD-a.
* **Upravljanje zahtjevima:** Korisnici podnose zahtjeve s kategorijama (Prava, Hardver, Softver...).
* **Admin sučelje:** Pristup ograničen samo na `ADMIN_USERS` listu za upravljanje tiketima.
* **Automatske obavijesti:** Profi HTML mailovi s bojama (Zelena, Crvena, Plava) ovisno o statusu.
* **Outlook kompatibilnost:** Optimizirana zaglavlja i PNG logo kako bi se izbjegao Junk folder.
* **Anketa zadovoljstva:** Korisnici ocjenjuju riješene zahtjeve (😊, 😐, 🙁).

## 🛠️ Preduvjeti
* Python 3.9+
* SQLite3
* Pristup AD poslužitelju (LDAPS)
* Pristup SMTP Relay poslužitelju (Outlook)

## 📦 Instalacija
1. Instaliraj biblioteke:
   `pip install fastapi uvicorn ldap3 sqlite3`
2. Potrebna struktura mapa:
   - `/images` (mora sadržavati `hanzekovic-logo.png`)
   - `/templates` (index.html, admin.html, moji-zahtjevi.html)
   - `/static` (style.css, script.js)

## ⚙️ Konfiguracija
Uredi `app.py`:
* `ADMIN_USERS`: Korisnička imena administratora.
* `AD_SERVER`: LDAPS URL.
* `MAIL_SENDER`: Službena adresa pošiljatelja.

## 🏃 Pokretanje
```bash
uvicorn app:app --host 127.0.0.1 --port 9001 --reload