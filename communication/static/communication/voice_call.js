(() => {
    const panel = document.getElementById("voice-call-panel");
    const toggle = document.getElementById("voice-call-toggle");
    const actionButton = document.getElementById("voice-call-action");
    const muteButton = document.getElementById("voice-call-mute");
    const leaveButton = document.getElementById("voice-call-leave");
    const status = document.getElementById("voice-call-status");
    const participantsLabel = document.getElementById("voice-call-participants");
    const errorBox = document.getElementById("voice-call-error");
    const audioContainer = document.getElementById("voice-call-audio");
    if (!panel || !toggle || !actionButton) return;

    const callUrl = panel.dataset.callUrl;
    const stateUrl = panel.dataset.stateUrl;
    const participantId = Number(panel.dataset.participantId);
    const callEnabled = panel.dataset.callEnabled === "true";
    const groupChat = panel.dataset.groupChat === "true";
    const csrfToken = document.querySelector(
        "#send-form input[name=csrfmiddlewaretoken]"
    )?.value;
    const iceServers = JSON.parse(
        document.getElementById("voice-call-ice-servers").textContent
    );
    const peers = new Map();
    const startedOffers = new Set();
    let call = null;
    let joined = false;
    let localStream = null;
    let signalCursor = 0;
    let busy = false;

    async function request(url, method = "GET", data = null, keepalive = false) {
        const headers = {};
        const options = { method, headers, credentials: "same-origin", keepalive };
        if (data !== null) {
            headers["Content-Type"] = "application/json";
            headers["X-CSRFToken"] = csrfToken;
            options.body = JSON.stringify(data);
        }
        const response = await fetch(url, options);
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "The call request failed.");
        }
        return result;
    }

    function showError(message = "") {
        errorBox.textContent = message;
    }

    function updateInterface() {
        const isJoined = joined && Boolean(call);
        const callActive = Boolean(call);
        const names = call
            ? call.participants.map((member) => (
                member.id === participantId ? "You" : member.name
            ))
            : [];
        participantsLabel.textContent = names.join(" · ");
        actionButton.hidden = isJoined;
        actionButton.disabled = busy || !callEnabled;
        actionButton.textContent = callActive ? "Join call" : "Start call";
        muteButton.hidden = !isJoined;
        leaveButton.hidden = !isJoined;
        toggle.setAttribute("aria-expanded", String(!panel.hidden));
        if (!callEnabled && !isJoined) {
            status.textContent = groupChat
                ? "Voice calls are available in private two-person chats."
                : "Calls are unavailable in a closed chat.";
        } else if (isJoined) {
            status.textContent = "Connected to the voice call.";
        } else if (callActive) {
            status.textContent = "A voice call is in progress.";
        } else {
            status.textContent = "Start a voice call with this chat.";
        }
    }

    function closePeer(participant) {
        const peer = peers.get(participant);
        if (!peer) return;
        peer.connection.close();
        peers.delete(participant);
        startedOffers.delete(participant);
        const audio = document.getElementById(`voice-call-audio-${participant}`);
        if (audio) audio.remove();
    }

    function sendSignal(recipient, type, payload) {
        return request(callUrl, "POST", {
            action: "signal",
            recipient,
            type,
            payload
        });
    }

    function createPeer(participant) {
        const existing = peers.get(participant);
        if (existing) return existing;
        const connection = new RTCPeerConnection({ iceServers });
        const peer = { connection, pendingCandidates: [] };
        peers.set(participant, peer);
        localStream.getTracks().forEach((track) => {
            connection.addTrack(track, localStream);
        });
        connection.onicecandidate = (event) => {
            if (event.candidate) {
                sendSignal(participant, "ice", event.candidate.toJSON())
                    .catch((error) => showError(error.message));
            }
        };
        connection.ontrack = (event) => {
            let audio = document.getElementById(`voice-call-audio-${participant}`);
            if (!audio) {
                audio = document.createElement("audio");
                audio.id = `voice-call-audio-${participant}`;
                audio.autoplay = true;
                audio.playsInline = true;
                audioContainer.append(audio);
            }
            audio.srcObject = event.streams[0];
            audio.play().catch(() => {
                showError("Allow audio playback in your browser to hear the call.");
            });
        };
        connection.onconnectionstatechange = () => {
            if (connection.connectionState === "failed") {
                showError("Could not connect to a caller. Check your network or ICE server settings.");
            }
        };
        return peer;
    }

    async function applyPendingCandidates(peer) {
        const candidates = peer.pendingCandidates.splice(0);
        for (const candidate of candidates) {
            await peer.connection.addIceCandidate(new RTCIceCandidate(candidate));
        }
    }

    async function handleSignal(signal) {
        const peer = createPeer(signal.sender);
        const connection = peer.connection;
        if (signal.type === "offer") {
            await connection.setRemoteDescription(
                new RTCSessionDescription(signal.payload)
            );
            await applyPendingCandidates(peer);
            const answer = await connection.createAnswer();
            await connection.setLocalDescription(answer);
            await sendSignal(signal.sender, "answer", connection.localDescription);
        } else if (signal.type === "answer") {
            await connection.setRemoteDescription(
                new RTCSessionDescription(signal.payload)
            );
            await applyPendingCandidates(peer);
        } else if (signal.type === "ice") {
            if (connection.remoteDescription) {
                await connection.addIceCandidate(
                    new RTCIceCandidate(signal.payload)
                );
            } else {
                peer.pendingCandidates.push(signal.payload);
            }
        }
    }

    async function updatePeers(members) {
        const memberIds = new Set(
            members
                .map((member) => member.id)
                .filter((id) => id !== participantId)
        );
        for (const id of peers.keys()) {
            if (!memberIds.has(id)) closePeer(id);
        }
        for (const id of memberIds) {
            const peer = createPeer(id);
            if (participantId < id && !startedOffers.has(id)) {
                startedOffers.add(id);
                const offer = await peer.connection.createOffer();
                await peer.connection.setLocalDescription(offer);
                await sendSignal(id, "offer", peer.connection.localDescription);
            }
        }
    }

    async function syncCall() {
        const result = await request(callUrl, "POST", {
            action: "sync",
            after: signalCursor
        });
        call = result.call;
        await updatePeers(call.participants);
        for (const signal of result.signals) {
            signalCursor = signal.id;
            await handleSignal(signal);
        }
        updateInterface();
    }

    async function refreshCallState() {
        if (joined || busy) return;
        try {
            const result = await request(stateUrl);
            call = result.call;
            updateInterface();
        } catch (error) {
            showError(error.message);
        }
    }

    async function joinOrStartCall() {
        if (busy) return;
        busy = true;
        showError();
        updateInterface();
        try {
            if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
                throw new Error("Voice calls are not supported by this browser.");
            }
            status.textContent = "Waiting for microphone permission…";
            localStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: false
            });
            const result = await request(
                callUrl,
                "POST",
                { action: call ? "join" : "start" }
            );
            call = result.call;
            joined = true;
            signalCursor = 0;
            updateInterface();
            await syncCall();
        } catch (error) {
            if (localStream) {
                localStream.getTracks().forEach((track) => track.stop());
                localStream = null;
            }
            joined = false;
            showError(error.message);
            await refreshCallState();
        } finally {
            busy = false;
            updateInterface();
        }
    }

    function stopLocalCall() {
        for (const id of [...peers.keys()]) closePeer(id);
        if (localStream) {
            localStream.getTracks().forEach((track) => track.stop());
            localStream = null;
        }
        joined = false;
        muteButton.textContent = "Mute";
        updateInterface();
    }

    async function leaveCall() {
        if (!joined || busy) return;
        busy = true;
        try {
            await request(callUrl, "POST", { action: "leave" });
        } catch (error) {
            showError(error.message);
        } finally {
            stopLocalCall();
            busy = false;
            await refreshCallState();
        }
    }

    toggle.addEventListener("click", async () => {
        panel.hidden = !panel.hidden;
        updateInterface();
        if (!panel.hidden) await refreshCallState();
    });
    actionButton.addEventListener("click", joinOrStartCall);
    muteButton.addEventListener("click", () => {
        if (!localStream) return;
        const shouldMute = localStream.getAudioTracks().some((track) => track.enabled);
        localStream.getAudioTracks().forEach((track) => {
            track.enabled = !shouldMute;
        });
        muteButton.textContent = shouldMute ? "Unmute" : "Mute";
    });
    leaveButton.addEventListener("click", leaveCall);

    window.setInterval(() => {
        if (!joined || busy) return;
        syncCall().catch((error) => {
            showError(error.message);
            stopLocalCall();
        });
    }, 1000);
    window.setInterval(refreshCallState, 3000);
    window.addEventListener("pagehide", () => {
        if (!joined) return;
        fetch(callUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            body: JSON.stringify({ action: "leave" }),
            credentials: "same-origin",
            keepalive: true
        });
    });
    updateInterface();
    refreshCallState();
})();
