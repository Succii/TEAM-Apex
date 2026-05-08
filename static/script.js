const datosAyuda = {
    "Mano, hoy el tapón estaba brutal.": "El tráfico estaba extremadamente pesado y desesperante",
    "Dímelo, ¿qué es la que hay esta noche?": "Saludo preguntando qué planes hay esta noche",
    "Acho, me quedé dormío otra vez.": "Expresión de frustración por haberse dormido otra vez",
    "El corillo va pa' la playa mañana.": "El grupo de amigos va a la playa mañana",
    "Esa movie estuvo brutal de verdá'.": "La película estuvo muy buena o increíble"
};

const userInput = document.getElementById("user-input");
const displayArea = document.getElementById("display-area");

userInput.addEventListener("keypress", function (event) {
    if (event.key === "Enter" && this.value.trim() !== "") {
        const mensaje = this.value.trim();
        this.value = "";

        const userLine = document.createElement("p");
        userLine.className = "user-msg";
        userLine.innerHTML = `<span class="prompt">User:</span> ${mensaje}`;
        displayArea.appendChild(userLine);

        if (mensaje.toLowerCase() === "--help" || mensaje.toLowerCase() === "help") {
            ejecutarAyudaLocal();
        } else {
            const loadingLine = document.createElement("p");
            loadingLine.className = "system-msg";
            loadingLine.textContent = ">>> Procesando en nodo Inter_Aguadilla...";
            displayArea.appendChild(loadingLine);
            traducirMensaje(mensaje, loadingLine);
        }

        displayArea.scrollTop = displayArea.scrollHeight;
    }
});

function ejecutarAyudaLocal() {
    const mensajeIA = "¡Diantre macho! Aquí tienes los ejemplos que el sistema reconoce:";
    const ejemplos = Object.keys(datosAyuda);

    const iaLine = document.createElement("p");
    iaLine.className = "ia-msg-matrix";
    displayArea.appendChild(iaLine);

    let index = 0;

    function escribir() {
        if (index < mensajeIA.length) {
            iaLine.innerHTML += mensajeIA.charAt(index);
            index += 1;
            setTimeout(escribir, 25);
            displayArea.scrollTop = displayArea.scrollHeight;
        } else {
            const card = document.createElement("div");
            card.className = "flashcard-tecnica";

            let contenido = '<p class="card-title">>>> FRASES DISPONIBLES:</p>';
            ejemplos.forEach((frase) => {
                contenido += `<p class="card-item"><span class="cmd-blue">Ej:</span> "${frase}"</p>`;
            });

            card.innerHTML = contenido;
            displayArea.appendChild(card);
            displayArea.scrollTop = displayArea.scrollHeight;
        }
    }

    escribir();
}

async function traducirMensaje(mensaje, loadingLine) {
    try {
        const response = await fetch("/translate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ text: mensaje })
        });

        const payload = await response.json();
        loadingLine.remove();

        if (!response.ok) {
            throw new Error(payload.error || "No se pudo traducir el mensaje.");
        }

        const translatedLine = document.createElement("p");
        translatedLine.className = "boricua-reply";
        translatedLine.innerHTML = `<span class="prompt">AsíSeDice:</span> ${payload.translation}`;
        displayArea.appendChild(translatedLine);

        const metaLine = document.createElement("p");
        metaLine.className = "tech-card";
        metaLine.textContent = payload.note || "Traducción completada.";
        displayArea.appendChild(metaLine);
    } catch (error) {
        loadingLine.remove();

        const errorLine = document.createElement("p");
        errorLine.className = "system-msg";
        errorLine.textContent = `>>> Error: ${error.message}`;
        displayArea.appendChild(errorLine);
    } finally {
        displayArea.scrollTop = displayArea.scrollHeight;
    }
}
