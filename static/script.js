+// v1.0.4
document.getElementById('requestForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const responseDiv = document.getElementById('responseMessage');

    try {
        const response = await fetch('/submit-request', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            responseDiv.innerHTML = `<div class="alert alert-success shadow-sm">✅ Zahtjev zaprimljen. Status pratite u "Moji Zahtjevi".</div>`;
            e.target.reset();
            if(document.getElementById('pathInputContainer')) {
                document.getElementById('pathInputContainer').style.display = 'none';
            }
        } else {
            responseDiv.innerHTML = `<div class="alert alert-danger shadow-sm">❌ Greška pri spremanju.</div>`;
        }
    } catch (error) {
        responseDiv.innerHTML = `<div class="alert alert-danger shadow-sm">❌ Veza sa serverom je prekinuta.</div>`;
    }
});