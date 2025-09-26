'use strict';

window.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const loginBtn = document.getElementById("loginBtn");
    const callBtn = document.getElementById("callBtn");
    const answerBtn = document.getElementById("answerBtn");
    const endCallBtn = document.getElementById("endCallBtn");
    const loginInterface = document.getElementById("loginInterface");
    const callInterface = document.getElementById("callInterface");
    const localVideo = document.getElementById("localVideo");
    const remoteVideo = document.getElementById("remoteVideo");
    const callNameInput = document.getElementById("callName");
    const callingDisplay = document.getElementById("calling");

    // STATE VARIABLES
    let myName = null;
    let otherUser = null;
    let remoteRTCMessage = null;
    let iceCandidatesFromCaller = [];
    let iceCandidateQueue = [];
    let peerConnection = null;
    let localStream = null;
    let remoteStream = null;
    let callInProgress = false;
    let callSocket = null;

    const pcConfig = {
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
    };

    // ===== LOGIN =====
    loginBtn.addEventListener("click", () => {
        const nameInput = document.getElementById("loginName").value.trim();
        if (!nameInput) {
            alert("Please enter your name");
            return;
        }
        myName = nameInput;
        loginInterface.style.display = "none";
        callInterface.style.display = "block";

        connectSocket();
    });

    // ===== CALL =====
    callBtn.addEventListener("click", () => {
        otherUser = callNameInput.value.trim();
        if (!otherUser) {
            alert("Enter user to call");
            return;
        }
        callingDisplay.style.display = "block";

        beReady().then(() => processCall(otherUser))
                 .catch(e => {
                     console.error("Call setup error:", e);
                     callingDisplay.style.display = "none";
                 });
    });

    // ===== ANSWER =====
    answerBtn.addEventListener("click", () => {
        answerBtn.style.display = "none";
        beReady().then(() => processAccept())
                 .catch(e => console.error("Answer setup error:", e));
    });

    // ===== END CALL =====
    endCallBtn.addEventListener("click", () => stop());

    // ===================
    // WEBSOCKET
    // ===================
    function connectSocket() {
        if (!myName) return;

        const ws_scheme = window.location.protocol === "https:" ? "wss://" : "ws://";
        const ws_url = ws_scheme + window.location.host + "/ws/call/" + myName + "/";

        callSocket = new WebSocket(ws_url);

        callSocket.onopen = () => {
            console.log("WebSocket connected");
            // Send login message to server
            callSocket.send(JSON.stringify({
                type: 'login',
                data: { name: myName }
            }));

            iceCandidateQueue.forEach(data => sendICEcandidate(data));
            iceCandidateQueue = [];
        };

        callSocket.onmessage = (e) => {
            const response = JSON.parse(e.data);
            const type = response.type;

            switch (type) {
                case 'connection':
                    console.log(response.data.message);
                    break;
                case 'call_received':
                    onNewCall(response.data);
                    break;
                case 'call_answered':
                    onCallAnswered(response.data);
                    break;
                case 'ICEcandidate':
                    onICECandidate(response.data);
                    break;
                default:
                    console.warn("Unknown message type:", type);
            }
        };

        callSocket.onerror = (e) => console.error("WebSocket error:", e);
        callSocket.onclose = () => console.log("WebSocket closed");
    }

    // ===================
    // CALL HANDLERS
    // ===================
    function onNewCall(data) {
        if (callInProgress) {
            console.log(`Ignoring call from ${data.caller}, already in call.`);
            return;
        }

        otherUser = data.caller;
        remoteRTCMessage = data.rtcMessage;

        answerBtn.style.display = "block";
        document.getElementById("otherUserNameC").innerHTML = otherUser;
        document.getElementById("inCall").style.display = "block";

        console.log(`Incoming call from ${otherUser}`);
    }

    function onCallAnswered(data) {
        callingDisplay.style.display = "none";
        remoteRTCMessage = data.rtcMessage;

        peerConnection.setRemoteDescription(new RTCSessionDescription(remoteRTCMessage))
            .then(() => {
                iceCandidatesFromCaller.forEach(c => peerConnection.addIceCandidate(c));
                iceCandidatesFromCaller = [];
                callProgress();
            })
            .catch(e => console.error("Remote description error:", e));
    }

    function onICECandidate(data) {
        const message = data.rtcMessage;
        const candidate = new RTCIceCandidate({
            sdpMLineIndex: message.label,
            candidate: message.candidate,
            sdpMid: message.id
        });

        if (peerConnection && peerConnection.remoteDescription) {
            peerConnection.addIceCandidate(candidate).catch(e => console.error("ICE add error:", e));
        } else {
            iceCandidatesFromCaller.push(candidate);
        }
    }

    // ===================
    // SEND FUNCTIONS
    // ===================
    function sendCall(data) {
        if (!callSocket || callSocket.readyState !== WebSocket.OPEN) {
            console.warn("WebSocket not ready. Cannot send call.");
            callingDisplay.style.display = "none";
            return;
        }
        data.caller = myName;
        callSocket.send(JSON.stringify({ type: 'call', data }));
    }

    function answerCall(data) {
        if (!callSocket || callSocket.readyState !== WebSocket.OPEN) {
            console.warn("WebSocket not ready. Cannot send answer.");
            return;
        }
        callSocket.send(JSON.stringify({ type: 'answer_call', data }));
    }

    function sendICEcandidate(data) {
        if (!callSocket || callSocket.readyState !== WebSocket.OPEN) {
            iceCandidateQueue.push(data);
            return;
        }
        if (data.user) {
            callSocket.send(JSON.stringify({ type: 'ICEcandidate', data }));
        }
    }

    // ===================
    // MEDIA & PEER CONNECTION
    // ===================
    function beReady() {
        if (localStream && peerConnection) return Promise.resolve(true);

        return navigator.mediaDevices.getUserMedia({ audio: true, video: true })
            .then(stream => {
                localStream = stream;
                localVideo.srcObject = stream;
                createPeerConnection();
                addLocalTracks();
                return true;
            });
    }

    function addLocalTracks() {
        localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
    }

    function createPeerConnection() {
        if (peerConnection) peerConnection.close();

        peerConnection = new RTCPeerConnection(pcConfig);
        peerConnection.onicecandidate = handleIceCandidate;

        peerConnection.ontrack = event => {
            if (remoteVideo.srcObject !== event.streams[0]) {
                remoteStream = event.streams[0];
                remoteVideo.srcObject = remoteStream;
            }
        };

        peerConnection.onconnectionstatechange = () => {
            console.log('RTCPeerConnection state:', peerConnection.connectionState);
            if (['disconnected', 'failed'].includes(peerConnection.connectionState)) {
                if (callInProgress) stop();
            }
        };
    }

    function handleIceCandidate(event) {
        if (event.candidate && otherUser) {
            sendICEcandidate({
                user: otherUser,
                rtcMessage: {
                    label: event.candidate.sdpMLineIndex,
                    id: event.candidate.sdpMid,
                    candidate: event.candidate.candidate
                }
            });
        }
    }

    // ===================
    // OFFER / ANSWER
    // ===================
    function processCall(userName) {
        peerConnection.createOffer()
            .then(offer => peerConnection.setLocalDescription(offer))
            .then(() => sendCall({ name: userName, rtcMessage: peerConnection.localDescription }));
    }

    function processAccept() {
        peerConnection.setRemoteDescription(new RTCSessionDescription(remoteRTCMessage))
            .then(() => {
                iceCandidatesFromCaller.forEach(c => peerConnection.addIceCandidate(c));
                iceCandidatesFromCaller = [];
                return peerConnection.createAnswer();
            })
            .then(answer => peerConnection.setLocalDescription(answer))
            .then(() => {
                answerCall({ caller: otherUser, rtcMessage: peerConnection.localDescription });
                callProgress();
            });
    }

    // ===================
    // CALL UI
    // ===================
    function callProgress() {
        document.getElementById("videos").style.display = "block";
        document.getElementById("otherUserNameC").innerHTML = otherUser;
        document.getElementById("inCall").style.display = "block";
        callingDisplay.style.display = "none";
        answerBtn.style.display = "none";
        callInProgress = true;
    }

    function stop() {
        console.log("Stopping call");
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localStream = null;
        }
        if (peerConnection) {
            peerConnection.close();
            peerConnection = null;
        }

        callInProgress = false;
        otherUser = null;
        remoteRTCMessage = null;
        iceCandidatesFromCaller = [];
        iceCandidateQueue = [];

        localVideo.srcObject = null;
        remoteVideo.srcObject = null;

        answerBtn.style.display = "none";
        document.getElementById("inCall").style.display = "none";
        document.getElementById("videos").style.display = "none";
    }

    window.onbeforeunload = () => {
        if (callInProgress) stop();
        if (callSocket && callSocket.readyState === WebSocket.OPEN) {
            callSocket.close();
        }
    };

    loginInterface.style.display = "block";
    callInterface.style.display = "none";
});
