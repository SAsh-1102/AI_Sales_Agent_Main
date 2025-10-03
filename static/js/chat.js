// Send message to backend
let currentAudio = null;

async function sendMessageToBackend(messageData) {
  addMessage('bot', 'Sales Agent is processing...');
  try {
    const res = await fetch("/agent/chat/", { 
      method: 'POST', 
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(messageData)
    });
    const data = await res.json();

    // remove typing bubble
    const msgs = chatEl.querySelectorAll('.message.bot');
    if (msgs.length) {
      const last = msgs[msgs.length-1];
      if (last.textContent === 'Sales Agent is processing...') last.remove();
    }

    addMessage('bot', data.reply);
    setLeadStage(data.lead_stage);
    setEmotion(data.emotion);
    debugEl.textContent = JSON.stringify(data.debug_info, null, 2); // Changed from data.memory

    if (data.audio) {
      const audio = new Audio("data:audio/mp3;base64," + data.audio);
      audio.play();
    }
  } catch (err) {
    console.error(err);
    addMessage('bot', 'Error contacting server.');
  }
}
const sendBtn = document.getElementById('sendBtn');
const inputEl = document.getElementById('chatInput');
const chatEl = document.getElementById('chatMessages');
const debugEl = document.getElementById('debug');
const micBtn = document.getElementById('micBtn');

// Text send - CHANGED TO SEND JSON
sendBtn.addEventListener('click', () => {
  const text = inputEl.value.trim();
  if (!text) return;
  addMessage('user', text);

  const messageData = {
    session_id: sessionId,
    message: text
  };

  sendMessageToBackend(messageData);
  inputEl.value = '';
});

// Mic → record audio → send to backend - NEEDS DIFFERENT HANDLING
let mediaRecorder, audioChunks = [], recordTimeout;

micBtn.addEventListener('click', async () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    clearTimeout(recordTimeout);
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert("Microphone not supported. Use Chrome.");
    return;
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  audioChunks = [];

  mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

  mediaRecorder.onstop = async () => {
    clearTimeout(recordTimeout);
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    
    // For audio, we still need FormData
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('audio', audioBlob, 'user_audio.wav');

    addMessage('user', '🎤 You spoke...');
    
    // Send audio to different endpoint
    try {
      const res = await fetch("/agent/voice/?action=stt", { 
        method: 'POST', 
        body: formData 
      });
      const data = await res.json();
      
      if (data.text) {
        // Now send the transcribed text as a regular message
        const messageData = {
          session_id: sessionId,
          message: data.text
        };
        sendMessageToBackend(messageData);
      }
    } catch (err) {
      console.error(err);
      addMessage('bot', 'Error processing audio.');
    }
  }

  mediaRecorder.start();
  addMessage('user', '🎤 Recording...');

  recordTimeout = setTimeout(() => {
    if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
  }, 5000);
});