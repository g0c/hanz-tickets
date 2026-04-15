// v1.1.0
// Globalna varijabla za Bootstrap modal
let bsStatusModal;

document.addEventListener('DOMContentLoaded', () => {
    const modalEl = document.getElementById('statusModal');
    if (modalEl) {
        bsStatusModal = new bootstrap.Modal(modalEl);
    }

    // Inicijalizacija glavne forme ako postoji na stranici
    const reqForm = document.getElementById('requestForm');
    if (reqForm) {
        reqForm.addEventListener('submit', handleRequestSubmit);
    }
});

// Funkcija za otvaranje modala kod promjene statusa
function openStatusModal(id, status) {
    document.getElementById('modalTicketId').innerText = "#" + id;
    document.getElementById('modalNewStatus').innerText = status;
    document.getElementById('hiddenTicketId').value = id;
    document.getElementById('hiddenNewStatus').value = status;
    document.getElementById('adminFeedback').value = ""; // Očisti stari unos
    
    bsStatusModal.show();
}

// Slanje ažuriranog statusa i komentara na server
async function confirmStatusUpdate() {
    const id = document.getElementById('hiddenTicketId').value;
    const status = document.getElementById('hiddenNewStatus').value;
    const feedback = document.getElementById('adminFeedback').value;

    const formData = new FormData();
    formData.append('ticket_id', id);
    formData.append('new_status', status);
    formData.append('feedback', feedback);

    try {
        const response = await fetch('/update-status', { 
            method: 'POST', 
            body: formData 
        });

        if (response.ok) {
            bsStatusModal.hide();
            location.reload(); // Osvježi za prikaz promjena
        } else {
            alert("Greška pri ažuriranju statusa.");
        }
    } catch (error) {
        console.error("Greška:", error);
        alert("Veza sa serverom je prekinuta.");
    }
}

// Obrada slanja forme za korisničke zahtjeve
async function handleRequestSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const responseDiv = document.getElementById('responseMessage');
    const requestType = document.getElementById('request_type').value;

    const submitBtn = document.getElementById('submitBtn');
    const submitText = document.getElementById('submitText');
    const submitSpinner = document.getElementById('submitSpinner');

    submitBtn.disabled = true;
    submitText.innerText = "Molim pričekajte nekoliko trenutaka...";
    submitSpinner.classList.remove('d-none');

    if (requestType === 'Novi Korisnik') {
        const podnosi = document.getElementById('nk_podnosi').value;
        const ime = document.getElementById('nk_ime').value;
        const prezime = document.getElementById('nk_prezime').value;
        const spol = document.getElementById('nk_spol').value;
        const odjel = document.getElementById('nk_odjel').value;
        const lokacija = document.getElementById('nk_lokacija').value;
        const grad = document.getElementById('nk_grad').value;
        const pin = document.getElementById('nk_pin').value || 'Nije upisano';
        const datum = document.getElementById('nk_datum').value;
        const mobitel = document.getElementById('nk_mobitel').value || 'Nije upisano';
        const napomena = document.getElementById('nk_napomena').value || 'Nema napomene';

        const formatiraniOpis = `--- ZAHTJEV ZA NOVOG DJELATNIKA ---
Podnositelj: ${podnosi}
Kandidat: ${ime} ${prezime}
Spol: ${spol}
Odjel/Uloga: ${odjel}
Lokacija: ${lokacija}
Grad: ${grad}
Sistemski PIN: ${pin}
Datum dolaska: ${datum}
Mobitel: ${mobitel}

Napomena:
${napomena}`;

        formData.set('description', formatiraniOpis);
    }

    try {
        const response = await fetch('/submit-request', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            responseDiv.innerHTML = `<div class="alert alert-success shadow-sm mt-3">✅ Zahtjev zaprimljen. Status pratite u "Moji Zahtjevi".</div>`;
            e.target.reset();
            
            if(document.getElementById('pathInputContainer')) document.getElementById('pathInputContainer').style.display = 'none';
            if(document.getElementById('noviKorisnikContainer')) document.getElementById('noviKorisnikContainer').style.display = 'none';
            if(document.getElementById('descriptionContainer')) document.getElementById('descriptionContainer').style.display = 'block';
        } else {
            responseDiv.innerHTML = `<div class="alert alert-danger shadow-sm mt-3">❌ Greška pri spremanju.</div>`;
        }
    } catch (error) {
        responseDiv.innerHTML = `<div class="alert alert-danger shadow-sm mt-3">❌ Veza sa serverom je prekinuta.</div>`;
    } finally {
        submitBtn.disabled = false;
        submitText.innerText = "Pošalji IT-u";
        submitSpinner.classList.add('d-none');
    }
}

// Slanje ocjene zadovoljstva (Survey)
async function submitSurvey(id, rating) {
    const formData = new FormData();
    formData.append('ticket_id', id);
    formData.append('rating', rating);
    await fetch('/submit-survey', { method: 'POST', body: formData });
    location.reload();
}