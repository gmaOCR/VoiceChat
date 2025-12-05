const recordBtn = document.getElementById('record-btn');
const statusText = document.getElementById('status-text');
const chatHistory = document.getElementById('chat-history');
let mediaRecorder;
let audioChunks = [];
let currentSessionId; 

recordBtn.addEventListener('mousedown', startRecording);
recordBtn.addEventListener('mouseup', stopRecording);
recordBtn.addEventListener('touchstart', startRecording); // Mobile support
recordBtn.addEventListener('touchend', stopRecording);

const startBtn = document.getElementById('startBtn');
if (startBtn) {
    startBtn.addEventListener('click', startSession);
}

async function startSession() {
    statusText.textContent = "Starting session...";
    
    const selectedLang = document.querySelector('input[name="lang"]:checked').value;
    const sourceLang = selectedLang; 
    const targetLang = selectedLang === 'fr' ? 'ru' : 'fr';
    const level = document.getElementById('level-select').value;
    
    const formData = new FormData();
    formData.append("source_lang", sourceLang);
    formData.append("target_lang", targetLang);
    formData.append("level", level);
    
    try {
        const response = await fetch('/start', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error("Start failed");
        
        const data = await response.json();
        
        // Display AI message from segments with Smart UI
        if (data.response && data.response.segments) {
            const responseContainer = document.createElement('div');
            responseContainer.classList.add('message', 'ai');
            
            data.response.segments.forEach((segment) => {
                const langFlag = segment.lang === 'fr' ? '🇫🇷' : (segment.lang === 'ru' ? '🇷🇺' : '');
                const isNative = segment.lang === sourceLang;
                
                const segDiv = document.createElement('div');
                segDiv.classList.add('segment-block');
                
                if (isNative) {
                    const toggleBtn = document.createElement('button');
                    toggleBtn.classList.add('tip-toggle');
                    toggleBtn.innerHTML = `💡 Traduction (${langFlag})`;
                    toggleBtn.onclick = () => {
                        contentDiv.classList.toggle('visible');
                    };
                    
                    const contentDiv = document.createElement('div');
                    contentDiv.classList.add('hidden-content');
                    contentDiv.textContent = segment.text;
                    
                    segDiv.appendChild(toggleBtn);
                    segDiv.appendChild(contentDiv);
                } else {
                    segDiv.textContent = `${langFlag} ${segment.text}`;
                    segDiv.classList.add('target-lang-text');
                }
                
                responseContainer.appendChild(segDiv);
            });
            
            chatHistory.appendChild(responseContainer);
            chatHistory.scrollTop = chatHistory.scrollHeight;

        } else {
            addMessage("👋 (Welcome)", "ai"); 
        } 
        
        // Save session
        currentSessionId = data.session_id;
        
        // Disable controls
        document.getElementById('level-select').disabled = true;
        document.querySelectorAll('input[name="lang"]').forEach(el => el.disabled = true);
        startBtn.disabled = true;
        startBtn.classList.add('disabled');
        
        // Play audio
        if (data.audio_segments) {
            await playAudioSequentially(data.audio_segments);
        }
        
        statusText.textContent = "Your turn (Press Mic)";
        
    } catch (error) {
        console.error("Error starting:", error);
        statusText.textContent = "Error starting.";
    }
}

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
    // Ajouter la version API choisie (simple list côté web)
    const apiVersionSelect = document.getElementById('api-version-select');
    if (apiVersionSelect) {
        const apiVersion = apiVersionSelect.value || 'v1';
        formData.append('api_version', apiVersion);
    }
    
    // Determine level
    const levelSelect = document.getElementById('level-select');
    const level = levelSelect ? levelSelect.value : 'A1';
    formData.append('level', level);

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

        // Display pronunciation analysis if exists
        if (data.pronunciation) {
            displayPronunciationFeedback(data.pronunciation);
        }

        // Display Correction/Explanation
        if (data.user_analysis) {
            displayCorrection(data.user_analysis);
        }

        // Display AI Segments with Smart UI
        if (data.segments && data.segments.length > 0) {
            
            // Create container for AI response
            const responseContainer = document.createElement('div');
            responseContainer.classList.add('message', 'ai');
            
            data.segments.forEach((segment) => {
                const langFlag = segment.lang === 'fr' ? '🇫🇷' : (segment.lang === 'ru' ? '🇷🇺' : '');
                const isNative = segment.lang === sourceLang;
                
                const segDiv = document.createElement('div');
                segDiv.classList.add('segment-block');
                
                if (isNative) {
                    // Tip UI for Native Language
                    const toggleBtn = document.createElement('button');
                    toggleBtn.classList.add('tip-toggle');
                    toggleBtn.innerHTML = `💡 Traduction (${langFlag})`;
                    toggleBtn.onclick = () => {
                        contentDiv.classList.toggle('visible');
                    };
                    
                    const contentDiv = document.createElement('div');
                    contentDiv.classList.add('hidden-content');
                    contentDiv.textContent = segment.text;
                    
                    segDiv.appendChild(toggleBtn);
                    segDiv.appendChild(contentDiv);
                } else {
                    // Normal Text for Target Language
                    segDiv.textContent = `${langFlag} ${segment.text}`;
                    segDiv.classList.add('target-lang-text');
                }
                
                responseContainer.appendChild(segDiv);
            });
            
            chatHistory.appendChild(responseContainer);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        // Play Audio Segments Sequentially
        if (data.audio_segments && data.audio_segments.length > 0) {
            await playAudioSequentially(data.audio_segments);
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

async function playAudioSequentially(audioSegments) {
    for (const segment of audioSegments) {
        await new Promise((resolve, reject) => {
            const audio = new Audio(segment.audio_url);
            audio.onended = resolve;
            audio.onerror = reject;
            audio.play().catch(reject);
        });
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

function displayPronunciationFeedback(pronunciation) {
    const div = document.createElement('div');
    div.classList.add('pronunciation-panel');
    
    const score = pronunciation.score || 0;
    const scoreClass = score >= 80 ? 'excellent' : score >= 60 ? 'good' : 'needs-work';
    const scoreEmoji = score >= 80 ? '🎯' : score >= 60 ? '👍' : '🔄';
    
    let html = `
        <div class="pronunciation-header">
            <h4>${scoreEmoji} Prononciation: ${score.toFixed(1)}%</h4>
        </div>
        <div class="score-bar ${scoreClass}">
            <div class="score-fill" style="width: ${score}%"></div>
        </div>
    `;
    
    // Word-level feedback
    if (pronunciation.words && pronunciation.words.length > 0) {
        html += '<div class="words-analysis">';
        pronunciation.words.forEach(word => {
            const wordScore = word.score || 0;
            const wordClass = wordScore >= 80 ? 'word-good' : wordScore >= 60 ? 'word-ok' : 'word-bad';
            html += `<span class="word-badge ${wordClass}" title="Score: ${wordScore}%">${word.word}</span>`;
        });
        html += '</div>';
    }
    
    // Prosody metrics
    if (pronunciation.prosody) {
        const p = pronunciation.prosody;
        html += '<div class="prosody-metrics">';
        if (p.average_pitch_hz) {
            html += `<div class="metric">🎵 Pitch: ${p.average_pitch_hz.toFixed(0)} Hz</div>`;
        }
        if (p.speech_rate_wps) {
            html += `<div class="metric">⏱️ Vitesse: ${p.speech_rate_wps.toFixed(1)} mots/s</div>`;
        }
        if (p.duration_s) {
            html += `<div class="metric">⏳ Durée: ${p.duration_s.toFixed(1)}s</div>`;
        }
        html += '</div>';
    }
    
    // Feedback message
    if (pronunciation.feedback) {
        html += `<div class="feedback-message">${pronunciation.feedback}</div>`;
    }
    
    div.innerHTML = html;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function displayCorrection(analysis) {
    if (!analysis || (!analysis.corrected_text && !analysis.explanation)) return;

    const div = document.createElement('div');
    div.classList.add('correction-panel');
    
    let html = '';
    
    // Header based on correctness
    const isCorrect = analysis.is_correct;
    const icon = isCorrect ? '✨' : '💡';
    const title = isCorrect ? 'Parfait !' : 'Correction';
    const headerClass = isCorrect ? 'correct' : 'incorrect';
    
    html += `
        <div class="correction-header ${headerClass}">
            <span class="icon">${icon}</span>
            <span class="title">${title}</span>
        </div>
    `;
    
    // Correction body
    html += '<div class="correction-body">';
    
    if (!isCorrect && analysis.corrected_text) {
        html += `
            <div class="correction-text">
                <span class="label">Tu aurais dû dire :</span>
                <span class="text">"${analysis.corrected_text}"</span>
            </div>
        `;
    }
    
    if (analysis.explanation) {
        html += `
            <div class="correction-explanation">
                ${analysis.explanation}
            </div>
        `;
    }
    
    html += '</div>';
    
    div.innerHTML = html;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

