// v1.0.3
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
            responseDiv.innerHTML = `<div class="alert alert-success">✅ Vaš zahtjev je zaprimljen.</div>`;
            e.target.reset();
            // Sakrij path container ako je bio vidljiv nakon reseta
            if(document.getElementById('pathInputContainer')) {
                document.getElementById('pathInputContainer').style.display = 'none';
            }
        } else {
            responseDiv.innerHTML = `<div class="alert alert-danger">❌ Greška pri slanju.</div>`;
        }
    } catch (error) {
        responseDiv.innerHTML = `<div class="alert alert-danger">❌ Server nedostupan.</div>`;
    }
});