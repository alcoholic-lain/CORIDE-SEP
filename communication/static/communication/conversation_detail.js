(() => {
    const list = document.getElementById("messages");
    const form = document.getElementById("send-form");
    const errorBox = document.getElementById("send-error");
    const status = document.getElementById("chat-status");
    const typingIndicator = document.getElementById("typing-indicator");
    const typingIndicatorLabel = document.getElementById("typing-indicator-label");
    const presenceLabel = document.getElementById("participant-presence");
    const presenceDot = document.getElementById("participant-presence-dot");
    const input = form.elements.content;
    const replyInput = form.elements.reply_to;
    const attachmentInput = form.elements.attachment;
    let selectedAttachment = null;
    const replyComposer = document.getElementById("reply-composer");
    const attachmentPreview = document.getElementById("attachment-preview");
    const searchPanel = document.getElementById("message-search");
    const searchInput = document.getElementById("message-search-input");
    const searchCount = document.getElementById("message-search-count");
    const pinnedPanel = document.getElementById("pinned-panel");
    const pinnedList = document.getElementById("pinned-list");
    const pinnedCount = document.getElementById("pinned-count");
    const olderStatus = document.getElementById("older-messages-status");
    let lastId = Number(list.dataset.nextId) || 0;
    let oldestId = Number(list.dataset.oldestId) || 0;
    let hasOlderMessages = list.dataset.hasOlder === "true";
    let loadingOlderMessages = false;
    let pinnedSignature = null;
    let polling = false;
    let typingActive = false;
    let typingTimer;
    let lastTypingSentAt = 0;
    let typingQueue = Promise.resolve();
    let loadedMessageCount = list.querySelectorAll(".message").length;
    let searchMatchCount = loadedMessageCount;
    const pinnedStates = new Map(
        [...list.querySelectorAll(".message")].map((article) => [
            article.dataset.messageId,
            article.dataset.pinned === "true"
        ])
    );
    const visibleMessageIds = new Set();
    const messageObserver = "IntersectionObserver" in window
        ? new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                const id = entry.target.dataset.messageId;
                if (entry.isIntersecting) visibleMessageIds.add(id);
                else visibleMessageIds.delete(id);
            });
        }, { root: list })
        : null;

    function observeMessage(article) {
        if (messageObserver) {
            article.dataset.observed = "true";
            messageObserver.observe(article);
        }
    }

    function getVisibleMessageIds() {
        if (messageObserver) return [...visibleMessageIds].slice(0, 50);
        return [...list.querySelectorAll(".message")]
            .slice(-50)
            .map((article) => article.dataset.messageId);
    }

    function renderAttachment(article, attachment) {
        if (!attachment) return;
        const wrapper = document.createElement("div");
        wrapper.className = "message-attachment";
        const link = document.createElement("a");
        link.href = attachment.url;

        if (attachment.content_type.startsWith("image/")) {
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            const image = document.createElement("img");
            image.className = "attachment-image";
            image.src = attachment.url;
            image.alt = attachment.name;
            image.loading = "lazy";
            link.append(image);
        } else {
            link.download = attachment.name;
            const card = document.createElement("span");
            card.className = "file-card";
            const icon = document.createElement("span");
            icon.className = "file-icon";
            icon.setAttribute("aria-hidden", "true");
            const name = document.createElement("strong");
            name.textContent = attachment.name;
            const size = document.createElement("small");
            size.textContent = `${Math.ceil(attachment.size / 1024)} KB`;
            card.append(icon, name, size);
            link.append(card);
        }
        wrapper.append(link);
        article.append(wrapper);
    }

    function renderReply(article, reply) {
        if (!reply) return;
        const quote = document.createElement("div");
        quote.className = "message-reply";
        quote.dataset.replyId = reply.id;
        const sender = document.createElement("strong");
        sender.textContent = reply.sender;
        const content = document.createElement("span");
        content.textContent = reply.content;
        quote.append(sender, content);
        article.append(quote);
    }

    function updateGrouping(article) {
        let previous = article.previousElementSibling;
        while (previous && !previous.classList.contains("message")) {
            previous = previous.previousElementSibling;
        }
        const currentTime = Date.parse(article.dataset.sentAt);
        const previousTime = previous ? Date.parse(previous.dataset.sentAt) : NaN;
        const sameSender = previous
            && previous.dataset.senderId === article.dataset.senderId;
        const closeTogether = Number.isFinite(currentTime)
            && Number.isFinite(previousTime)
            && currentTime >= previousTime
            && currentTime - previousTime < 5 * 60 * 1000;
        article.classList.toggle("message-grouped", Boolean(sameSender && closeTogether));
    }

    function applyGrouping(articles) {
        articles.forEach(updateGrouping);
    }

    function updateSearchCount(query) {
        searchCount.textContent = query
            ? `${searchMatchCount} of ${loadedMessageCount} loaded messages${
                searchMatchCount === 0 && hasOlderMessages
                    ? " · Scroll up to search older messages"
                    : ""
            }`
            : "";
    }

    function searchableText(article) {
        return [...article.querySelectorAll(
            ".message-meta strong, .message-content, .message-reply, .message-attachment"
        )].map((element) => element.textContent).join(" ").toLocaleLowerCase();
    }

    function applyMessageSearch() {
        const query = searchInput.value.trim().toLocaleLowerCase();
        const messages = [...list.querySelectorAll(".message")];
        loadedMessageCount = messages.length;
        searchMatchCount = 0;
        messages.forEach((article) => {
            const matched = !query || searchableText(article).includes(query);
            article.hidden = !matched;
            if (matched) searchMatchCount += 1;
        });
        updateSearchCount(query);
    }

    function updateMessageSearch(article, isNew = false) {
        if (!article) return;
        const query = searchInput.value.trim().toLocaleLowerCase();
        if (isNew) loadedMessageCount += 1;
        const wasMatched = !isNew && !article.hidden;
        const matched = !query || searchableText(article).includes(query);
        article.hidden = !matched;
        if (query) {
            if (wasMatched !== matched) searchMatchCount += matched ? 1 : -1;
        } else {
            searchMatchCount = loadedMessageCount;
        }
        updateSearchCount(query);
    }

    function renderPinnedMessages(ids, knownIds = null, forceUpdate = false) {
        const pinnedIds = new Set((ids || []).map(String));
        const known = knownIds
            ? new Set(knownIds.map(String))
            : new Set([...list.querySelectorAll(".message")].map(
                (article) => article.dataset.messageId
            ));
        if (!known.size && !forceUpdate) return;
        let changed = forceUpdate;
        known.forEach((id) => {
            const article = list.querySelector(`[data-message-id="${id}"]`);
            if (!article) return;
            const pinned = pinnedIds.has(id);
            const changedState = pinnedStates.get(id) !== pinned;
            if (!changedState) return;
            changed = true;
            pinnedStates.set(id, pinned);
            article.dataset.pinned = String(pinned);
            article.classList.toggle("message-pinned", pinned);
            const mark = article.querySelector(".pinned-mark");
            if (pinned && !mark) {
                const badge = document.createElement("span");
                badge.className = "pinned-mark";
                badge.textContent = "Pinned";
                article.querySelector(".message-meta").append(badge);
            } else if (!pinned && mark) {
                mark.remove();
            }
            const button = article.querySelector(".pin-message");
            if (button) button.textContent = pinned ? "Unpin message" : "Pin message";
        });
        if (!changed) return;

        const loadedMessages = [...list.querySelectorAll(".message")];
        const loadedIds = new Set(loadedMessages.map((article) => article.dataset.messageId));
        const unloadedPins = [...pinnedList.querySelectorAll(".pinned-jump")]
            .filter((button) => !loadedIds.has(button.dataset.jumpTo))
            .map((button) => ({
                id: button.dataset.jumpTo,
                element: button.closest("li")
            }));
        const pinned = loadedMessages
            .filter((article) => article.dataset.pinned === "true")
            .filter((article) => !article.classList.contains("message-deleted"));
        const loadedPins = pinned.map((article) => {
            const sender = article.querySelector(".message-meta strong").textContent;
            const content = article.querySelector(".message-content");
            const attachment = article.querySelector(".message-attachment");
            const snippet = content
                ? content.textContent
                : attachment
                    ? attachment.textContent
                    : "Attachment";
            const item = document.createElement("li");
            const button = document.createElement("button");
            button.className = "pinned-jump";
            button.type = "button";
            button.dataset.jumpTo = article.dataset.messageId;
            const name = document.createElement("strong");
            name.textContent = sender;
            const preview = document.createElement("span");
            preview.textContent = snippet;
            button.append(name, preview);
            item.append(button);
            return { id: article.dataset.messageId, element: item };
        });
        const entries = [...unloadedPins, ...loadedPins]
            .sort((left, right) => Number(left.id) - Number(right.id));
        const nextPinnedSignature = entries.map(({ element }) => {
            const button = element.querySelector(".pinned-jump");
            return `${button.dataset.jumpTo}:${button.textContent}`;
        }).join("|");
        if (nextPinnedSignature === pinnedSignature) return;
        pinnedSignature = nextPinnedSignature;

        if (!entries.length) {
            const empty = document.createElement("li");
            empty.className = "pinned-empty";
            empty.textContent = "No pinned messages yet.";
            pinnedList.replaceChildren(empty);
        } else {
            pinnedList.replaceChildren(...entries.map(({ element }) => element));
        }
        pinnedCount.textContent = String(entries.length);
    }

    function updateMessage(article, message) {
        if (!article) return false;
        const deleted = Boolean(message.deleted);
        const content = article.querySelector(".message-content");
        const nextContent = deleted ? "Message deleted" : message.content;
        const editedAt = message.edited_at || "";
        const contentChanged = nextContent !== undefined
            && (!content || content.textContent !== nextContent);
        const editedChanged = article.dataset.editedAt !== editedAt;
        const deletedChanged = article.dataset.deleted !== String(deleted);
        const pinnedChanged = typeof message.pinned === "boolean"
            && article.dataset.pinned !== String(message.pinned);
        if (!contentChanged && !editedChanged && !deletedChanged && !pinnedChanged) {
            return false;
        }

        if (contentChanged || deletedChanged) {
            const replyPreview = deleted
                ? "Message deleted"
                : message.content || "Attachment";
            list.querySelectorAll(
                `.message-reply[data-reply-id="${message.id}"] span`
            ).forEach((preview) => {
                preview.textContent = replyPreview;
            });
        }
        article.dataset.editedAt = editedAt;
        article.dataset.deleted = String(deleted);
        if (message.deleted) {
            if (content) {
                content.hidden = false;
                content.textContent = "Message deleted";
            } else {
                const deletedContent = document.createElement("p");
                deletedContent.className = "message-content";
                deletedContent.textContent = "Message deleted";
                article.append(deletedContent);
            }
            article.querySelector(".message-attachment")?.remove();
            article.querySelector(".message-reply")?.remove();
            article.querySelector(".message-toolbar")?.remove();
            article.dataset.pinned = "false";
            article.classList.add("message-deleted");
            renderReactions(article, []);
            return true;
        }

        if (typeof message.pinned === "boolean") {
            article.dataset.pinned = String(message.pinned);
        }
        if (content && message.content !== undefined) {
            content.hidden = !message.content;
            content.textContent = message.content;
        }
        let editedLabel = article.querySelector(".edited-label");
        if (message.edited_at) {
            if (!editedLabel) {
                editedLabel = document.createElement("span");
                editedLabel.className = "edited-label";
                article.querySelector(".message-meta").append(editedLabel);
            }
            editedLabel.hidden = false;
            editedLabel.textContent = "edited";
        }
        return true;
    }

    function setReply(article) {
        const content = article.querySelector(".message-content");
        const attachment = article.querySelector(".message-attachment");
        replyInput.value = article.dataset.messageId;
        document.getElementById("reply-composer-sender").textContent =
            article.querySelector(".message-meta strong").textContent;
        document.getElementById("reply-composer-content").textContent = content
            ? content.textContent.slice(0, 160)
            : attachment
                ? attachment.textContent.trim()
                : "Message deleted";
        replyComposer.hidden = false;
        input.focus();
    }

    function clearReply() {
        replyInput.value = "";
        replyComposer.hidden = true;
    }

    function startEditing(article) {
        const content = article.querySelector(".message-content");
        if (!content || article.querySelector(".message-editor")) return;
        content.hidden = true;
        const editor = document.createElement("form");
        editor.className = "message-editor";
        editor.style.gridArea = "content";
        const textarea = document.createElement("textarea");
        textarea.maxLength = 1000;
        textarea.value = content.textContent;
        const controls = document.createElement("div");
        controls.className = "editor-controls";
        const save = document.createElement("button");
        save.className = "button";
        save.type = "submit";
        save.textContent = "Save";
        const cancel = document.createElement("button");
        cancel.className = "text-button";
        cancel.type = "button";
        cancel.textContent = "Cancel";
        controls.append(save, cancel);
        editor.append(textarea, controls);
        content.after(editor);
        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);

        cancel.addEventListener("click", () => {
            content.hidden = false;
            editor.remove();
        });
        editor.addEventListener("submit", async (event) => {
            event.preventDefault();
            const body = new URLSearchParams({ content: textarea.value });
            try {
                const response = await fetch(article.dataset.editUrl, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": form.elements.csrfmiddlewaretoken.value,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json"
                    },
                    body
                });
                const data = await response.json();
                if (!response.ok) {
                    errorBox.textContent = data.error || "Message could not be edited.";
                    return;
                }
                content.textContent = data.content;
                content.hidden = false;
                editor.remove();
                updateMessage(article, data);
                updateMessageSearch(article);
            } catch {
                errorBox.textContent = "Message could not be edited. Please try again.";
            }
        });
    }

    function sendTypingStatus(isTyping) {
        const body = new URLSearchParams({
            is_typing: isTyping ? "true" : "false"
        });
        const token = form.elements.csrfmiddlewaretoken.value;
        typingQueue = typingQueue.then(async () => {
            const response = await fetch(form.dataset.typingUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": token,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                },
                body
            });
            if (!response.ok) throw new Error("Typing status update failed.");
        }).catch(() => {
            typingIndicator.hidden = false;
            typingIndicatorLabel.textContent = "Typing status unavailable.";
        });
    }

    function stopTyping() {
        window.clearTimeout(typingTimer);
        if (!typingActive) return;
        typingActive = false;
        sendTypingStatus(false);
    }

    function resizeComposer() {
        input.style.height = "42px";
        input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
    }

    function renderReactions(article, reactions) {
        const container = article.querySelector(".message-reactions");
        if (!container) return;
        const row = container.closest(".message-reaction-row");
        if (row) row.hidden = reactions.length === 0;
        const signature = reactions
            .map((reaction) => `${reaction.emoji}:${reaction.count}:${reaction.reacted}`)
            .join("|");
        if (container.dataset.signature === signature) return;
        container.dataset.signature = signature;
        container.replaceChildren();

        reactions.forEach((reaction) => {
            const button = document.createElement("button");
            button.className = `reaction-chip${reaction.reacted ? " reaction-mine" : ""}`;
            button.type = "button";
            button.dataset.reactionEmoji = reaction.emoji;
            button.textContent = `${reaction.emoji} ${reaction.count}`;
            button.setAttribute(
                "aria-label",
                `${reaction.count} ${reaction.emoji} reactions`
            );
            container.append(button);
        });
    }

    function handleTypingInput() {
        if (!input.value.trim()) {
            stopTyping();
            return;
        }
        if (!typingActive || Date.now() - lastTypingSentAt >= 2500) {
            typingActive = true;
            lastTypingSentAt = Date.now();
            sendTypingStatus(true);
        }
        window.clearTimeout(typingTimer);
        typingTimer = window.setTimeout(stopTyping, 3500);
    }

    function createMessage(message) {
        const article = document.createElement("article");
        article.className = `message${message.is_mine ? " message-mine" : ""}${
            message.deleted ? " message-deleted" : ""
        }`;
        article.dataset.messageId = message.id;
        article.dataset.senderId = message.sender_id;
        article.dataset.sentAt = message.sent_at;
        article.dataset.editedAt = message.edited_at || "";
        article.dataset.deleted = String(Boolean(message.deleted));
        article.dataset.pinned = String(message.pinned);
        if (message.reaction_url) article.dataset.reactionUrl = message.reaction_url;
        if (message.delete_url) article.dataset.deleteUrl = message.delete_url;
        if (message.edit_url) article.dataset.editUrl = message.edit_url;
        if (message.pin_url) article.dataset.pinUrl = message.pin_url;

        const avatar = document.createElement("span");
        avatar.className = "avatar message-avatar";
        avatar.setAttribute("aria-hidden", "true");
        const senderInitial = [...message.sender][0];
        avatar.textContent = senderInitial ? senderInitial.toLocaleUpperCase() : "?";

        const meta = document.createElement("div");
        meta.className = "message-meta";
        const sender = document.createElement("strong");
        sender.textContent = message.sender;
        const time = document.createElement("time");
        time.dateTime = message.sent_at;
        time.textContent = new Date(message.sent_at).toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit"
        });
        meta.append(sender, time);
        if (message.edited_at) {
            const edited = document.createElement("span");
            edited.className = "edited-label";
            edited.textContent = "edited";
            meta.append(edited);
        }
        if (message.pinned) {
            const pinned = document.createElement("span");
            pinned.className = "pinned-mark";
            pinned.textContent = "Pinned";
            meta.append(pinned);
        }
        if (message.is_mine) {
            const readStatus = document.createElement("span");
            readStatus.className = "read-status";
            readStatus.dataset.readStatusFor = message.id;
            readStatus.textContent = message.read ? "Seen" : "Sent";
            meta.append(readStatus);
        }

        const content = document.createElement("p");
        content.className = "message-content";
        content.textContent = message.deleted ? "Message deleted" : message.content;
        article.append(avatar, meta);
        renderReply(article, message.reply);
        if (message.content || message.deleted) article.append(content);
        renderAttachment(article, message.attachment);
        if (!message.deleted) {
            article.append(
                document.getElementById("message-controls-template").content.cloneNode(true)
            );
            renderReactions(article, message.reactions || []);
            const controls = article.querySelector(".message-toolbar");
            if (!message.edit_url) controls.querySelector(".edit-message").remove();
            if (!message.delete_url) controls.querySelector(".delete-message").remove();
            controls.querySelector(".pin-message").textContent = message.pinned
                ? "Unpin message"
                : "Pin message";
        }

        return article;
    }

    function appendMessages(messages) {
        if (!messages.length) return [];
        const wasAtBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 120;
        const empty = document.getElementById("empty-messages");
        if (empty) empty.remove();

        const existingIds = new Set(
            [...list.querySelectorAll(".message")]
                .map((article) => article.dataset.messageId)
        );
        const fragment = document.createDocumentFragment();
        const addedMessages = [];
        messages.forEach((message) => {
            const id = String(message.id);
            lastId = Math.max(lastId, Number(message.id));
            if (existingIds.has(id)) return;
            const article = createMessage(message);
            fragment.append(article);
            existingIds.add(id);
            addedMessages.push({ message, article });
        });
        if (!addedMessages.length) return [];

        list.append(fragment);
        const articles = addedMessages.map(({ article }) => article);
        articles.forEach(observeMessage);
        if (!oldestId) oldestId = Number(articles[0].dataset.messageId);
        applyGrouping(articles);
        addedMessages.forEach(({ article }) => updateMessageSearch(article, true));
        renderPinnedMessages(
            addedMessages.filter(({ message }) => message.pinned)
                .map(({ message }) => message.id),
            addedMessages.map(({ message }) => message.id)
        );
        if (wasAtBottom) list.scrollTop = list.scrollHeight;
        return articles;
    }

    function appendMessage(message) {
        return appendMessages([message])[0];
    }

    async function loadOlderMessages() {
        if (!hasOlderMessages || loadingOlderMessages || !oldestId) return false;
        loadingOlderMessages = true;
        olderStatus.hidden = false;
        olderStatus.textContent = "Loading older messages…";
        const previousHeight = list.scrollHeight;
        const previousTop = list.scrollTop;
        try {
            const url = new URL(list.dataset.olderUrl, window.location.href);
            url.searchParams.set("before", oldestId);
            const response = await fetch(url, {
                headers: { "Accept": "application/json" }
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Older messages could not be loaded.");
            }

            const empty = document.getElementById("empty-messages");
            if (empty) empty.remove();
            const fragment = document.createDocumentFragment();
            const addedMessages = [];
            data.messages.forEach((message) => {
                if (!list.querySelector(`[data-message-id="${message.id}"]`)) {
                    const article = createMessage(message);
                    fragment.append(article);
                    addedMessages.push({ message, article });
                }
            });
            const firstMessage = list.querySelector(".message");
            list.insertBefore(fragment, firstMessage || olderStatus.nextSibling);
            addedMessages.forEach(({ article }) => observeMessage(article));
            oldestId = Number(data.oldest_id) || oldestId;
            hasOlderMessages = data.has_older;
            list.dataset.oldestId = String(oldestId);
            list.dataset.hasOlder = String(hasOlderMessages);
            olderStatus.hidden = !hasOlderMessages;
            olderStatus.textContent = "Scroll up to load older messages";
            list.scrollTop = previousTop + list.scrollHeight - previousHeight;
            applyGrouping([
                ...addedMessages.map(({ article }) => article),
                ...(firstMessage ? [firstMessage] : [])
            ]);
            addedMessages.forEach(({ article }) => updateMessageSearch(article, true));
            renderPinnedMessages(
                data.messages.filter((message) => message.pinned).map((message) => message.id),
                data.messages.map((message) => message.id)
            );
            return data.messages.length > 0;
        } catch (error) {
            olderStatus.hidden = false;
            olderStatus.textContent = "Could not load older messages. Scroll up to retry.";
            errorBox.textContent = error.message || "Older messages could not be loaded.";
            return false;
        } finally {
            loadingOlderMessages = false;
        }
    }

    async function jumpToMessage(messageId) {
        let target = list.querySelector(`[data-message-id="${messageId}"]`);
        while (!target && hasOlderMessages) {
            if (!await loadOlderMessages()) break;
            target = list.querySelector(`[data-message-id="${messageId}"]`);
        }
        if (!target) return;
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("message-highlight");
        window.setTimeout(() => target.classList.remove("message-highlight"), 1400);
        pinnedPanel.hidden = true;
    }

    async function poll() {
        if (polling || document.visibilityState === "hidden") return;
        polling = true;
        try {
            const params = new URLSearchParams({
                after: String(lastId),
                visible: getVisibleMessageIds().join(",")
            });
            const response = await fetch(`${list.dataset.pollUrl}?${params}`, {
                headers: { "Accept": "application/json" }
            });
            if (!response.ok) return;
            const data = await response.json();
            appendMessages(data.messages);
            let updatedMessage = false;
            data.updated_messages.forEach((message) => {
                const article = list.querySelector(
                    `[data-message-id="${message.id}"]`
                );
                if (updateMessage(article, message)) {
                    updateMessageSearch(article);
                    updatedMessage = true;
                }
            });
            Object.entries(data.reactions).forEach(([id, reactions]) => {
                const article = list.querySelector(`[data-message-id="${id}"]`);
                if (article) renderReactions(article, reactions);
            });
            renderPinnedMessages(
                data.pinned_ids,
                data.synced_ids,
                updatedMessage
            );
            data.read_ids.forEach((id) => {
                const readStatus = list.querySelector(`[data-read-status-for="${id}"]`);
                if (readStatus) readStatus.textContent = "Seen";
            });
            const otherName = document.getElementById("other-participant-name");
            if (data.other_participant && otherName) {
                otherName.textContent = data.other_participant;
            }
            if (presenceLabel && presenceDot) {
                presenceLabel.textContent = data.other_participants_count > 1
                    ? `${data.other_online_count} online`
                    : data.other_online ? "Online" : "Offline";
                presenceDot.classList.toggle("presence-online", data.other_online);
            }
            typingIndicator.hidden = !data.typing;
            typingIndicatorLabel.textContent = data.typing
                ? `${data.typing} is typing...`
                : "";
            if (data.has_second_participant) {
                const invitePanel = document.getElementById("invite-panel");
                if (invitePanel) invitePanel.remove();
            }
            if (!data.is_open) {
                status.textContent = "Closed";
                status.className = "status status-closed";
                input.disabled = true;
                form.querySelector("button[type=submit]").disabled = true;
                stopTyping();
            }
            errorBox.textContent = "";
        } catch {
            errorBox.textContent = "Connection lost. Reconnecting…";
        } finally {
            polling = false;
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        stopTyping();
        errorBox.textContent = "";
        const body = new FormData(form);
        body.delete(attachmentInput.name);
        if (selectedAttachment) {
            body.append(attachmentInput.name, selectedAttachment, selectedAttachment.name);
        }
        try {
            const response = await fetch(form.dataset.sendUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": body.get("csrfmiddlewaretoken"),
                    "Accept": "application/json"
                },
                body
            });
            const data = await response.json();
            if (!response.ok) {
                errorBox.textContent = data.error || Object.values(data.errors || {})
                    .flatMap((errors) => errors.map((item) => item.message))
                    .join(" ");
                return;
            }
            form.reset();
            selectedAttachment = null;
            resizeComposer();
            clearReply();
            attachmentPreview.hidden = true;
            document.getElementById("attachment-preview-name").textContent = "";
            appendMessage(data);
        } catch {
            errorBox.textContent = "Message could not be sent. Please try again.";
        }
    });

    list.addEventListener("click", async (event) => {
        const jumpButton = event.target.closest("[data-jump-to]");
        if (jumpButton) {
            await jumpToMessage(jumpButton.dataset.jumpTo);
            return;
        }

        const reactionButton = event.target.closest("[data-reaction-emoji]");
        if (reactionButton) {
            const article = reactionButton.closest(".message");
            const body = new URLSearchParams({
                emoji: reactionButton.dataset.reactionEmoji
            });
            const token = form.elements.csrfmiddlewaretoken.value;
            try {
                const response = await fetch(article.dataset.reactionUrl, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": token,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json"
                    },
                    body
                });
                const data = await response.json();
                if (!response.ok) {
                    errorBox.textContent = data.error || "Reaction could not be saved.";
                    return;
                }
                renderReactions(article, data.reactions);
                const menu = reactionButton.closest(".react-menu");
                if (menu) menu.open = false;
            } catch {
                errorBox.textContent = "Reaction could not be saved. Please try again.";
            }
            return;
        }

        const replyButton = event.target.closest(".reply-message");
        if (replyButton) {
            setReply(replyButton.closest(".message"));
            return;
        }

        const editButton = event.target.closest(".edit-message");
        if (editButton) {
            startEditing(editButton.closest(".message"));
            return;
        }

        const pinButton = event.target.closest(".pin-message");
        if (pinButton) {
            const article = pinButton.closest(".message");
            try {
                const response = await fetch(article.dataset.pinUrl, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": form.elements.csrfmiddlewaretoken.value,
                        "Accept": "application/json"
                    }
                });
                const data = await response.json();
                if (!response.ok) {
                    errorBox.textContent = data.error || "Pin could not be updated.";
                    return;
                }
                renderPinnedMessages(data.pinned_ids, [data.id]);
                const menu = pinButton.closest(".message-more");
                if (menu) menu.open = false;
            } catch {
                errorBox.textContent = "Pin could not be updated. Please try again.";
            }
            return;
        }

        const button = event.target.closest(".delete-message");
        if (!button) return;
        const article = button.closest(".message");
        const token = form.elements.csrfmiddlewaretoken.value;
        try {
            const response = await fetch(article.dataset.deleteUrl, {
                method: "POST",
                headers: { "X-CSRFToken": token, "Accept": "application/json" }
            });
            if (!response.ok) {
                errorBox.textContent = "Message could not be deleted.";
                return;
            }
            updateMessage(article, { deleted: true });
            updateMessageSearch(article);
            renderPinnedMessages([], [article.dataset.messageId]);
        } catch {
            errorBox.textContent = "Message could not be deleted.";
        }
    });

    document.getElementById("reply-composer-close").addEventListener("click", clearReply);

    const attachmentName = document.getElementById("attachment-preview-name");
    const attachmentClear = document.getElementById("attachment-clear");
    function selectAttachment(file) {
        if (file.size > 8 * 1024 * 1024) {
            selectedAttachment = null;
            attachmentInput.value = "";
            attachmentPreview.hidden = true;
            attachmentName.textContent = "";
            errorBox.textContent = "Files must be 8 MB or smaller.";
        } else {
            selectedAttachment = file;
            attachmentInput.value = "";
            errorBox.textContent = "";
            attachmentName.textContent = file.name;
            attachmentPreview.hidden = false;
        }
    }
    attachmentInput.addEventListener("change", () => {
        const file = attachmentInput.files[0];
        if (file) selectAttachment(file);
    });
    document.getElementById("attachment-trigger").addEventListener("click", () => {
        attachmentInput.click();
    });
    input.addEventListener("paste", (event) => {
        const clipboardItems = [...(event.clipboardData?.items || [])];
        const imageItem = clipboardItems.find((item) => item.type.startsWith("image/"));
        if (!imageItem) return;

        const image = imageItem.getAsFile();
        if (!image) return;
        const extensions = {
            "image/gif": "gif",
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp"
        };
        const extension = extensions[image.type];
        if (!extension) {
            event.preventDefault();
            errorBox.textContent = "Paste a PNG, JPEG, GIF, or WebP image.";
            return;
        }
        event.preventDefault();
        selectAttachment(new File(
            [image],
            `pasted-image-${Date.now()}.${extension}`,
            { type: image.type }
        ));
    });
    attachmentClear.addEventListener("click", () => {
        selectedAttachment = null;
        attachmentInput.value = "";
        attachmentPreview.hidden = true;
        attachmentName.textContent = "";
    });

    document.getElementById("message-search-toggle").addEventListener("click", () => {
        searchPanel.hidden = !searchPanel.hidden;
        if (!searchPanel.hidden) searchInput.focus();
    });
    document.getElementById("message-search-close").addEventListener("click", () => {
        searchInput.value = "";
        applyMessageSearch();
        searchPanel.hidden = true;
    });
    searchPanel.addEventListener("submit", (event) => event.preventDefault());
    searchInput.addEventListener("input", applyMessageSearch);

    document.getElementById("pinned-toggle").addEventListener("click", () => {
        pinnedPanel.hidden = !pinnedPanel.hidden;
    });
    document.getElementById("pinned-close").addEventListener("click", () => {
        pinnedPanel.hidden = true;
    });
    pinnedList.addEventListener("click", async (event) => {
        const jumpButton = event.target.closest("[data-jump-to]");
        if (jumpButton) await jumpToMessage(jumpButton.dataset.jumpTo);
    });

    input.addEventListener("input", () => {
        resizeComposer();
        handleTypingInput();
    });
    input.addEventListener("keydown", (event) => {
        if (
            event.key !== "Enter"
            || event.shiftKey
            || event.isComposing
            || input.value.endsWith(" ")
        ) {
            return;
        }
        event.preventDefault();
        if (input.value.trim() || selectedAttachment) {
            form.requestSubmit();
        }
    });
    input.addEventListener("blur", stopTyping);
    form.addEventListener("click", (event) => {
        const emojiButton = event.target.closest("[data-compose-emoji]");
        if (!emojiButton) return;
        const start = input.selectionStart;
        const end = input.selectionEnd;
        input.setRangeText(emojiButton.dataset.composeEmoji, start, end, "end");
        input.focus();
        emojiButton.closest(".emoji-picker").open = false;
        resizeComposer();
        handleTypingInput();
    });

    const inviteButton = document.getElementById("copy-invite");
    if (inviteButton) {
        inviteButton.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(inviteButton.dataset.inviteUrl);
                document.getElementById("copy-status").textContent = "Invite link copied.";
            } catch {
                const copied = window.prompt(
                    "Copy this invite link",
                    inviteButton.dataset.inviteUrl
                ) !== null;
                document.getElementById("copy-status").textContent = copied
                    ? "Copy the link from the dialog."
                    : "The invite link was not copied.";
            }
        });
    }

    list.querySelectorAll(".message").forEach(observeMessage);
    applyGrouping([...list.querySelectorAll(".message")]);
    applyMessageSearch();
    list.addEventListener("scroll", () => {
        if (list.scrollTop < 80) loadOlderMessages();
    });
    list.scrollTop = list.scrollHeight;
    poll();
    window.setInterval(poll, 1000);
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") poll();
    });
})();
