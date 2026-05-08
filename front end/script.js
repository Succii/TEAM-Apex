// 1. Datos integrados directamente
const datosAyuda = {
    "Mano, hoy el tapón estaba brutal.": "El tráfico estaba extremadamente pesado y desesperante",
    "Dímelo, ¿qué es la que hay esta noche?": "Saludo preguntando qué planes hay esta noche",
    "Acho, me quedé dormío otra vez.": "Expresión de frustración por haberse dormido otra vez",
    "El corillo va pa' la playa mañana.": "El grupo de amigos va a la playa mañana",
    "Esa movie estuvo brutal de verdá'.": "La película estuvo muy buena o increíble"
};

const userInput = document.getElementById('user-input');
const displayArea = document.getElementById('display-area');

userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && this.value !== "") {
        const mensaje = this.value.trim();
        this.value = "";

        // Pintar línea del usuario
        const p = document.createElement('p');
        p.className = 'user-msg';
        p.innerHTML = `<span class="prompt">User:</span> ${mensaje}`;
        displayArea.appendChild(p);

        // Lógica de ayuda (Acepta help o --help)
        if (mensaje.toLowerCase() === "--help" || mensaje.toLowerCase() === "help") {
            ejecutarAyudaLocal();
        } else {
            displayArea.innerHTML += `<p class="system-msg">>>> Procesando...</p>`;
        }
        displayArea.scrollTop = displayArea.scrollHeight;
    }
});

function ejecutarAyudaLocal() {
    const mensajeIA = "Diantre, no sabes? Aquí estan los ejemplos!";
    const ejemplos = Object.keys(datosAyuda); // Extrae las frases de arriba

    const iaLine = document.createElement('p');
    iaLine.className = 'ia-msg-matrix';
    displayArea.appendChild(iaLine);

    let i = 0;
    function escribir() {
        if (i < mensajeIA.length) {
            iaLine.innerHTML += mensajeIA.charAt(i);
            i++;
            setTimeout(escribir, 25);
            displayArea.scrollTop = displayArea.scrollHeight;
        } else {
            // Crear el Flashcard
            const card = document.createElement('div');
            card.className = 'flashcard-tecnica';
            let contenido = `<p class="card-title">>>> FRASES DISPONIBLES:</p>`;
            
            ejemplos.forEach(frase => {
                contenido += `<p class="card-item"><span class="cmd-blue">Ej:</span> "${frase}"</p>`;
            });

            card.innerHTML = contenido;
            displayArea.appendChild(card);
            displayArea.scrollTop = displayArea.scrollHeight;
        }
    }
    escribir();
}