(() => {
    const notifications = document.getElementById("incoming-call-notifications");
    const list = document.getElementById("incoming-call-list");
    const errorBox = document.getElementById("incoming-call-error");
    if (!notifications || !list || !errorBox) return;

    const stateUrl = notifications.dataset.stateUrl;
    const currentChat = document.querySelector(".chat-shell[data-conversation-id]");
    const currentConversationId = currentChat?.dataset.conversationId;
    const callPanel = document.getElementById("voice-call-panel");
    const cards = new Map();
    const dismissedCallIds = new Set();
    const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
    let ringtoneContext = null;
    let ringtoneTimer = null;
    let ringtoneShouldPlay = false;
    let ringtoneResumePending = false;
    let ringtoneNeedsGesture = false;
    let polling = false;
    let currentCalls = [];

    function ringBurst() {
        if (!ringtoneShouldPlay || !ringtoneContext
            || ringtoneContext.state !== "running") return;
        const startAt = ringtoneContext.currentTime;
        [0, 0.8].forEach((offset) => {
            const gain = ringtoneContext.createGain();
            const toneStart = startAt + offset;
            gain.gain.setValueAtTime(0.0001, toneStart);
            gain.gain.exponentialRampToValueAtTime(0.045, toneStart + 0.05);
            gain.gain.setValueAtTime(0.045, toneStart + 0.55);
            gain.gain.exponentialRampToValueAtTime(0.0001, toneStart + 0.65);
            gain.connect(ringtoneContext.destination);
            [440, 480].forEach((frequency) => {
                const oscillator = ringtoneContext.createOscillator();
                oscillator.frequency.value = frequency;
                oscillator.connect(gain);
                oscillator.start(toneStart);
                oscillator.stop(toneStart + 0.66);
            });
        });
    }

    function updateRingtoneHint() {
        cards.forEach((card) => {
            card.hint.hidden = !ringtoneNeedsGesture;
            card.hint.textContent = AudioContextConstructor
                ? "Interact with this page to enable the ringtone."
                : "This browser does not support ringtone audio.";
        });
    }

    function beginRingtone() {
        if (!ringtoneShouldPlay || ringtoneTimer) return;
        ringtoneNeedsGesture = false;
        updateRingtoneHint();
        ringBurst();
        ringtoneTimer = window.setInterval(ringBurst, 4000);
    }

    function startRingtone() {
        ringtoneShouldPlay = true;
        if (!AudioContextConstructor) {
            ringtoneNeedsGesture = true;
            updateRingtoneHint();
            return;
        }
        if (!ringtoneContext) ringtoneContext = new AudioContextConstructor();
        if (ringtoneContext.state === "running") {
            beginRingtone();
            return;
        }
        ringtoneNeedsGesture = true;
        updateRingtoneHint();
        if (ringtoneResumePending) return;
        ringtoneResumePending = true;
        ringtoneContext.resume().then(() => {
            ringtoneResumePending = false;
            if (ringtoneShouldPlay) beginRingtone();
        }).catch(() => {
            ringtoneResumePending = false;
            ringtoneNeedsGesture = true;
            updateRingtoneHint();
        });
    }

    function stopRingtone() {
        ringtoneShouldPlay = false;
        ringtoneNeedsGesture = false;
        if (ringtoneTimer) window.clearInterval(ringtoneTimer);
        ringtoneTimer = null;
        updateRingtoneHint();
    }

    function unlockRingtone() {
        if (!AudioContextConstructor) return;
        if (!ringtoneContext) ringtoneContext = new AudioContextConstructor();
        if (ringtoneContext.state === "running" || ringtoneResumePending) return;
        ringtoneResumePending = true;
        ringtoneContext.resume().then(() => {
            ringtoneResumePending = false;
            ringtoneNeedsGesture = false;
            if (ringtoneShouldPlay) beginRingtone();
            else updateRingtoneHint();
        }).catch(() => {
            ringtoneResumePending = false;
            updateRingtoneHint();
        });
    }

    function createCallCard(call) {
        const card = document.createElement("section");
        card.className = "incoming-call-card";
        card.setAttribute("aria-label", `Incoming call from ${call.caller}`);

        const copy = document.createElement("div");
        copy.className = "incoming-call-copy";

        const title = document.createElement("strong");
        title.textContent = "Incoming call";
        const caller = document.createElement("p");
        caller.textContent = `From ${call.caller}`;
        const hint = document.createElement("p");
        hint.className = "incoming-call-hint";
        hint.hidden = true;
        copy.append(title, caller, hint);

        const actions = document.createElement("div");
        actions.className = "incoming-call-actions";

        const answer = document.createElement("a");
        answer.className = "incoming-call-answer";
        answer.textContent = "Answer";
        const answerUrl = new URL(call.conversation_url, window.location.origin);
        if (answerUrl.origin !== window.location.origin) {
            throw new Error("The incoming call link is not on this site.");
        }
        answerUrl.searchParams.set("answer_call", String(call.id));
        answer.href = answerUrl.href;

        const dismiss = document.createElement("button");
        dismiss.className = "incoming-call-dismiss";
        dismiss.type = "button";
        dismiss.textContent = "Dismiss";
        dismiss.setAttribute("aria-label", `Dismiss call from ${call.caller}`);
        dismiss.addEventListener("click", () => {
            dismissedCallIds.add(String(call.id));
            card.remove();
            cards.delete(String(call.id));
            updateCallNotifications(currentCalls);
        });

        actions.append(answer, dismiss);
        card.append(copy, actions);
        return { element: card, hint };
    }

    function updateCallNotifications(calls = []) {
        const visibleCalls = calls.filter((call) => !(
            currentConversationId
            && String(call.conversation_id) === currentConversationId
            && callPanel
            && !callPanel.hidden
        ));
        const activeIds = new Set(visibleCalls.map((call) => String(call.id)));
        dismissedCallIds.forEach((id) => {
            if (!activeIds.has(id)) dismissedCallIds.delete(id);
        });
        cards.forEach((card, id) => {
            if (!activeIds.has(id) || dismissedCallIds.has(id)) {
                card.element.remove();
                cards.delete(id);
            }
        });
        visibleCalls.forEach((call) => {
            const id = String(call.id);
            if (dismissedCallIds.has(id) || cards.has(id)) return;
            const card = createCallCard(call);
            cards.set(id, card);
            list.append(card.element);
        });

        if (cards.size) startRingtone();
        else stopRingtone();
        notifications.hidden = cards.size === 0 && errorBox.hidden;
    }

    window.addEventListener("coride:call-panel-visibility-change", () => {
        updateCallNotifications(currentCalls);
    });

    async function pollIncomingCalls() {
        if (polling) return;
        polling = true;
        try {
            const response = await fetch(stateUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" }
            });
            if (!response.ok) {
                throw new Error(`Call notification check failed (${response.status}).`);
            }
            const result = await response.json();
            if (!Array.isArray(result.calls)) {
                throw new Error("The call notification response was invalid.");
            }
            currentCalls = result.calls;
            errorBox.hidden = true;
            errorBox.textContent = "";
            updateCallNotifications(currentCalls);
        } catch (error) {
            errorBox.textContent = "Could not check for incoming calls. Refresh to retry.";
            errorBox.hidden = false;
            notifications.hidden = false;
            console.error(error);
        } finally {
            polling = false;
        }
    }

    document.addEventListener("pointerdown", unlockRingtone);
    document.addEventListener("keydown", unlockRingtone);
    window.addEventListener("pagehide", () => {
        stopRingtone();
        if (ringtoneContext) ringtoneContext.close();
    });

    pollIncomingCalls();
    window.setInterval(pollIncomingCalls, 3000);
})();
