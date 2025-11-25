const recordBtn = document.getElementById('record-btn');
const statusText = document.getElementById('status-text');
const chatHistory = document.getElementById('chat-history');
let mediaRecorder;
let audioChunks = [];

recordBtn.addEventListener('mousedown', startRecording);
recordBtn.addEventListener('mouseup', stopRecording);
recordBtn.addEventListener('touchstart', startRecording); // Mobile support
recordBtn.addEventListener('touchend', stopRecording);

async function startRecording(e) {
    e.preventDefault(); // Prevent focus issues
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Votre navigateur ne supporte pas l'enregistrement audio.");
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = sendAudio;

        mediaRecorder.start();
        recordBtn.classList.add('recording');
        statusText.textContent = "Enregistrement...";
    } catch (err) {
        console.error("Erreur d'accès au micro:", err);
        alert("Impossible d'accéder au micro.");
    }
}

function stopRecording(e) {
    e.preventDefault();
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        recordBtn.classList.remove('recording');
        statusText.textContent = "Traitement...";
    }
}

async function sendAudio() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' }); // Or audio/mp3 depending on browser
    const formData = new FormData();
    
    // Determine languages
    const selectedLang = document.querySelector('input[name="lang"]:checked').value;
    const sourceLang = selectedLang; 
    const targetLang = selectedLang === 'fr' ? 'ru' : 'fr';

    formData.append("audio", audioBlob, "recording.webm");
    formData.append("source_lang", sourceLang);
    formData.append("target_lang", targetLang);

    // Add user message placeholder
    addMessage("...", "user", true);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Erreur serveur: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Remove placeholder
        const placeholder = document.querySelector('.message.user.placeholder');
        if (placeholder) placeholder.remove();

        // Display User Text
        addMessage(data.user_text, "user");

        // Display AI Response & Correction
        let aiContent = data.ai_response;
        if (data.correction && data.correction.toLowerCase() !== "aucune correction nécessaire") {
            aiContent += `<span class="correction">${data.correction}</span>`;
        }
        addMessage(aiContent, "ai", false, true); // true for HTML content

        // Play Audio
        if (data.audio_url) {
            const audio = new Audio(data.audio_url);
            audio.play();
        }

        statusText.textContent = "Prêt";

    } catch (error) {
        console.error(error);
        statusText.textContent = "Erreur";
        addMessage("Erreur lors du traitement.", "system");
        
        const placeholder = document.querySelector('.message.user.placeholder');
        if (placeholder) placeholder.remove();
    }
}

function addMessage(text, sender, isPlaceholder = false, isHtml = false) {
    const div = document.createElement('div');
    div.classList.add('message', sender);
    if (isPlaceholder) div.classList.add('placeholder');
    
    if (isHtml) {
        div.innerHTML = text;
    } else {
        div.textContent = text;
    }
    
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}
