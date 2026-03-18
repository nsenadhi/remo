class Chatbox {
    constructor(userRole) {
        this.args = {
            chatBox: document.querySelector('.chatbox__support'),
            sendButton: document.querySelector('.send__button'),
            resetButton: document.querySelector('.chatbox__reset-button'),
        }

        this.state = true;
        this.messages = [];
        this.userRole = userRole;
        this.pendingFallCheckId = null;
        this.storageKey = `remoni_chat_history_${this.userRole}`;
        this.scrollKey = `remoni_chat_scroll_${this.userRole}`;
        this.unreadKey = `remoni_unread_${this.userRole}`;
        this.lastSeenKey = `remoni_last_seen_${this.userRole}`;
        this.restoringHistory = false;
    }

    loadHistory() {
        try {
            const raw = localStorage.getItem(this.storageKey);
            if (!raw) return false;
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) {
                this.messages = parsed;
                return true;
            }
        } catch {}
        return false;
    }

    saveHistory() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.messages));
        } catch {}
    }

    saveScroll(chatmessage) {
        if (!chatmessage) return;
        try {
            localStorage.setItem(this.scrollKey, String(chatmessage.scrollTop || 0));
        } catch {}
    }

    getSavedScroll() {
        try {
            const raw = localStorage.getItem(this.scrollKey);
            if (!raw) return null;
            const val = parseInt(raw, 10);
            return Number.isFinite(val) ? val : null;
        } catch {}
        return null;
    }

    resetUnread() {
        try {
            localStorage.setItem(this.unreadKey, "0");
            localStorage.setItem(this.lastSeenKey, new Date().toISOString());
        } catch {}
    }

    resetChat(chatBox) {
        this.messages = [];
        this.pendingFallCheckId = null;
        this.forceNewChat = true;
        try {
            localStorage.removeItem(this.storageKey);
            localStorage.removeItem(this.scrollKey);
            localStorage.removeItem(this.unreadKey);
            localStorage.removeItem(this.lastSeenKey);
        } catch {}
        this.updateChatText(chatBox);
        if (this.userRole === 'doctor') {
            this.showDoctorWelcome();
        } else {
            this.showPatientWelcome();
        }
        this.resetUnread();
        fetch($SCRIPT_ROOT + '/api/clear_conversation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        }).catch(() => {});
    }

    incrementUnread(count = 1) {
        try {
            const raw = localStorage.getItem(this.unreadKey);
            const current = raw ? parseInt(raw, 10) : 0;
            const next = Number.isFinite(current) ? current + count : count;
            localStorage.setItem(this.unreadKey, String(next));
        } catch {}
    }

    formatMessage(text) {
        if (!text) return '';
        text = text.replace(/\r\n/g, '\n');
        text = text.replace(/\n{2,}/g, '\n');
        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/^[•\-]\s+(.+)$/gm, '<div class="bullet-item">• $1</div>');
        text = text.replace(/^(\d+)\.\s+(.+)$/gm, '<div class="numbered-item">$1. $2</div>');
        text = text.replace(/\n/g, '<br>');
        text = text.replace(/<\/div><br>/g, '</div>');
        text = text.replace(/<br><div/g, '<div');
        return text;
    }

    /**
     * ✅ UPDATED: STANDARDIZED EMERGENCY ALERT FORMATTER WITH RESPIRATORY RATE
     * Formats ALL emergency alerts including respiratory rate alerts
     */
    formatEmergencyAlert(alertData) {
        let lines = [];

        // ✅ LINE 1: Header (always same)
        lines.push('🚨 EMERGENCY ALERT!');
        lines.push(''); // Empty line

        // ✅ LINE 2: Patient + Alert Type
        const patientId = alertData.patient_id || '00001';
        let alertTitle = '';

        // Determine alert title based on type
        if (alertData.type === 'fall_detected' || alertData.type === 'no_response' || alertData.type === 'patient_needs_help') {
            alertTitle = 'Fall Detected';
        } else if (alertData.type === 'heart_rate_critical_high') {
            alertTitle = 'Heart Rate is High';
        } else if (alertData.type === 'heart_rate_critical_low') {
            alertTitle = 'Heart Rate is Low';
        } else if (alertData.type === 'temperature_critical_high') {
            alertTitle = 'Temperature is High';
        } else if (alertData.type === 'temperature_critical_low') {
            alertTitle = 'Temperature is Low';
        } else if (alertData.type === 'glucose_critical_high') {
            alertTitle = 'Glucose is High';
        } else if (alertData.type === 'glucose_critical_low') {
            alertTitle = 'Glucose is Low';
        } else if (alertData.type === 'spo2_critical') {
            alertTitle = 'Oxygen Saturation is Low';
        } else if (alertData.type === 'bp_critical') {
            alertTitle = 'Blood Pressure is High';
        } else if (alertData.type === 'respiratory_rate_critical_high') {  // ✅ NEW
            alertTitle = 'Respiratory Rate is High';
        } else if (alertData.type === 'respiratory_rate_critical_low') {  // ✅ NEW
            alertTitle = 'Respiratory Rate is Low';
        } else {
            alertTitle = alertData.alert_title || 'Critical Alert';
        }

        lines.push(`Patient ${patientId} - ${alertTitle}`);

        // ✅ LINE 3: Time
        const time = alertData.datetime || new Date().toLocaleString();
        lines.push(`Time: ${time}`);

        // ✅ LINE 4: Type-specific value
        if (alertData.type === 'fall_detected' || alertData.type === 'no_response' || alertData.type === 'patient_needs_help') {
            // Fall alerts show confidence
            if (alertData.confidence) {
                lines.push(`Confidence: ${alertData.confidence}%`);
            }
        } else if (alertData.value) {
            // Vitals alerts show the vital value
            let label = '';
            if (alertData.type.includes('heart_rate')) {
                label = 'Heart Rate';
            } else if (alertData.type.includes('temperature')) {
                label = 'Temperature';
            } else if (alertData.type.includes('glucose')) {
                label = 'Glucose';
            } else if (alertData.type.includes('spo2')) {
                label = 'SpO2';
            } else if (alertData.type.includes('bp')) {
                label = 'Blood Pressure';
            } else if (alertData.type.includes('respiratory')) {  // ✅ NEW
                label = 'Respiratory Rate';
            }
            lines.push(`${label}: ${alertData.value}`);
        }

        // ✅ LINE 5: Footer (always same)
        lines.push('');
        lines.push('Please check on the patient immediately.');

        // ✅ Join lines with proper spacing
        let text = lines.join('\n');

        // ✅ FIXED: Proper red/bold formatting
        text = text.replace(/(🚨 EMERGENCY ALERT!)/g, '<strong style="color: #dc3545; font-size: 1.05em;">$1</strong>');
        text = text.replace(/(Patient\s+\d+\s+-\s+[^\n]+)/g, '<strong style="color: #dc3545;">$1</strong>');
        text = text.replace(/(Time|Confidence|Heart Rate|Temperature|Glucose|SpO2|Blood Pressure|Respiratory Rate):/g, '<strong>$1:</strong>');  // ✅ Added Respiratory Rate

        // ✅ Convert newlines to <br>
        text = text.replace(/\n/g, '<br>');

        return text;
    }

    alertKey(alertData) {
        const id = alertData.alert_id || alertData.id || '';
        const type = alertData.type || alertData.alert_type || '';
        const dt = alertData.datetime || alertData.timestamp || '';
        return `${id}|${type}|${dt}`;
    }

    hasAlert(key) {
        return this.messages.some(m => m && m.alertKey === key);
    }

    async loadEmergencyAlerts(chatBox) {
        if (this.userRole !== 'doctor') {
            return;
        }
        try {
            const res = await fetch('/api/emergency_alerts');
            if (!res.ok) return;
            const data = await res.json();
            const alerts = data && data.alerts ? data.alerts : [];
            let added = false;
            alerts.forEach((alertData) => {
                const key = this.alertKey(alertData);
                if (!key || this.hasAlert(key)) return;
                const formattedMessage = this.formatEmergencyAlert(alertData);
                this.messages.push({
                    name: 'REMONI_EMERGENCY',
                    message: formattedMessage,
                    isEmergency: true,
                    alertKey: key
                });
                added = true;
            });
            if (added) {
                this.updateChatText(chatBox);
                if (document.hidden) {
                    this.incrementUnread(alerts.length);
                }
            }
        } catch {}
    }

    display() {
        const { chatBox, sendButton, resetButton } = this.args;

        sendButton.addEventListener('click', () => this.onSendButton(chatBox));
        if (resetButton) {
            resetButton.addEventListener('click', () => this.resetChat(chatBox));
        }

        const node = chatBox.querySelector('.text_input');
        node.addEventListener("keyup", ({ key }) => {
            if (key === "Enter") {
                this.onSendButton(chatBox);
            }
        });

        chatBox.classList.add('chatbox--active');

        if (this.userRole === 'doctor') {
            try {
                const clearedKey = `remoni_chat_cleared_v9_${this.userRole}`;
                if (!localStorage.getItem(clearedKey)) {
                    localStorage.removeItem(this.storageKey);
                    localStorage.removeItem(this.scrollKey);
                    localStorage.setItem(clearedKey, '1');
                }
            } catch {}
        }
        if (this.userRole === 'patient') {
            try {
                const clearedKey = `remoni_chat_cleared_v6_${this.userRole}`;
                if (!localStorage.getItem(clearedKey)) {
                    localStorage.removeItem(this.storageKey);
                    localStorage.removeItem(this.scrollKey);
                    localStorage.setItem(clearedKey, '1');
                }
            } catch {}
        }

        const hasHistory = this.loadHistory();
        if (hasHistory) {
            this.restoringHistory = true;
            this.updateChatText(chatBox);
        }

        // ✅ SHOW WELCOME MESSAGE
        if (!hasHistory && this.userRole === 'doctor') {
            this.showDoctorWelcome();
        } else if (!hasHistory && this.userRole === 'patient') {
            fetch('/api/setup_status')
                .then(r => r.json())
                .then(data => {
                    if (!data.setup_completed) {
                        this.showSetupWelcome();
                    } else {
                        this.showPatientWelcome();
                    }
                })
                .catch(() => {
                    this.showPatientWelcome();
                });
        }

        this.resetUnread();

        // ✅ Load recent emergency alerts so they appear even if chat was closed
        this.loadEmergencyAlerts(chatBox);

        // ✅ SOCKETIO EVENT HANDLERS
        const socket = io({
            transports: ['polling'],
            upgrade: false
        });

        // ✅ EMERGENCY ALERTS - STANDARDIZED FORMAT (via MQTT)
        socket.on('emergency_alert', (data) => {
            console.log('📨 Emergency alert received:', data);

            if (this.userRole !== 'doctor') {
                return;
            }

            if (data.for_role && data.for_role !== this.userRole) {
                return;
            }

            // ✅ Filter out moderate falls (70-95%) - they go through patient check first
            if (data.type === 'fall_detected') {
                const confidence = data.confidence || 0;
                if (confidence >= 70 && confidence < 99.6) {
                    console.log(`Filtered moderate fall (${confidence}%) - waiting for patient response`);
                    return;
                }
            }

            // ✅ Use standardized formatter
            const formattedMessage = this.formatEmergencyAlert(data);
            const key = this.alertKey(data);
            if (key && this.hasAlert(key)) {
                return;
            }

            this.messages.push({
                name: 'REMONI_EMERGENCY',
                message: formattedMessage,
                isEmergency: true,
                alertKey: key
            });

            this.updateChatText(chatBox);
            this.playNotificationSound();
            if (document.hidden) {
                this.incrementUnread();
            }

            if (data.severity === 'CRITICAL' || data.confidence >= 99.6) {
                setTimeout(() => this.playNotificationSound(), 1000);
                setTimeout(() => this.playNotificationSound(), 2000);
            }
        });

        // ✅ FALL ALERTS - STANDARDIZED FORMAT (via MQTT)
        socket.on('fall_alert', (data) => {
            console.log('📨 Fall alert received:', data);

            if (this.userRole !== 'doctor') {
                return;
            }

            // ✅ Use standardized formatter (handles all fall types)
            const formattedMessage = this.formatEmergencyAlert(data);
            const key = this.alertKey(data);
            if (key && this.hasAlert(key)) {
                return;
            }

            this.messages.push({
                name: 'REMONI_EMERGENCY',
                message: formattedMessage,
                isEmergency: true,
                alertKey: key
            });

            this.updateChatText(chatBox);
            this.playNotificationSound();
            if (document.hidden) {
                this.incrementUnread();
            }

            const confidence = data.confidence || 0;
            if (confidence >= 99.6 || data.type === 'no_response' || data.type === 'patient_needs_help') {
                setTimeout(() => this.playNotificationSound(), 1000);
                setTimeout(() => this.playNotificationSound(), 2000);
            }
        });

        // ✅ FALL CHECK (for patient)
        socket.on('fall_check', (data) => {
            if (this.userRole !== 'patient') {
                return;
            }

            if (data.for_role && data.for_role !== this.userRole) {
                return;
            }

            const alertId = data.alert_id;
            const confidence = data.confidence || 0;

            this.pendingFallCheckId = alertId;

            const checkMessage = `⚠️ FALL DETECTION ALERT\n\nI detected unusual movement (Confidence: ${confidence}%).\nAre you okay?\nType "yes" or "I'm okay" if you're fine\nType "help" if you need assistance\n\n⏰ You have 3 minutes to respond`;

            this.messages.push({
                name: 'REMONI_EMERGENCY',
                message: checkMessage,
                isEmergency: true
            });

            this.updateChatText(chatBox);
            this.playNotificationSound();
            if (document.hidden) {
                this.incrementUnread();
            }
            setTimeout(() => this.playNotificationSound(), 1000);
        });

        // ✅ Doctor request (patient prompt)
        socket.on('doctor_request', (data) => {
            if (this.userRole !== 'patient') {
                return;
            }
            const message = `📩 Doctor Message\n\n${data.message || 'Are you okay? Please respond.'}`;
            this.messages.push({
                name: 'Doctor',
                message: message
            });
            this.updateChatText(chatBox);
            this.playNotificationSound();
            if (document.hidden) {
                this.incrementUnread();
            }
        });

        // (Doctor reply handling removed by request)

        // WiFi changed
        socket.on('wifi_changed', (data) => {
            if (this.userRole !== 'patient') {
                return;
            }

            const message = `📡 WiFi Connection Changed!\n\nNew IP Address: ${data.ip_address}\nWiFi Network: ${data.ssid}\n\nYour Edge Device IP has been updated automatically.`;

            this.messages.push({
                name: 'REMONI_STATUS',
                message: message
            });

            this.updateChatText(chatBox);
            this.playNotificationSound();
            if (document.hidden) {
                this.incrementUnread();
            }

            if (typeof updateEdgeIPDisplay === 'function') {
                updateEdgeIPDisplay(data.ip_address, data.ssid, true);
            }
        });

        // Vitals update
        socket.on('vitals_update', (data) => {
            console.log('Vitals update received:', data);
        });

        const chatmessage = chatBox.querySelector('.chatbox__messages');
        if (chatmessage) {
            chatmessage.addEventListener('scroll', () => this.saveScroll(chatmessage));
        }
    }

    showDoctorWelcome() {
        const welcomeMessage = `Hello Doctor! I'm REMONI — ask me anything about your patients.`;

        this.messages.push({ name: "REMONI", message: welcomeMessage });
        this.updateChatText(this.args.chatBox);
    }

    showPatientWelcome() {
        const welcomeMessage = `Hello! I'm REMONI, your virtual nurse.\n\nI'm monitoring your health 24/7. Ask me about:\n• Current vitals and glucose\n• Health history\n• System status\n\nHow can I help you?`;

        this.messages.push({ name: "REMONI", message: welcomeMessage });
        this.updateChatText(this.args.chatBox);
    }

    showSetupWelcome() {
        const welcomeMessage = `Hello! I'm REMONI, your virtual nurse.\nI'll help you set up your health monitoring system.\nType 'start' to begin or 'skip' if already set up.`;

        this.messages.push({ name: "REMONI", message: welcomeMessage });
        this.updateChatText(this.args.chatBox);
    }

    playNotificationSound() {
        try {
            const audio = new Audio('/static/notification.mp3');
            audio.play().catch(e => console.log('Could not play sound:', e));
        } catch (e) {
            console.log('Notification sound not available');
        }
    }

    onSendButton(chatbox) {
        var textField = chatbox.querySelector('.text_input');
        let text1 = textField.value
        if (text1 === "") {
            return;
        }

        let msg1 = { name: "User", message: text1 }
        this.messages.push(msg1);
        this.updateChatText(chatbox);
        textField.value = '';

        // ✅ Check if patient is responding to fall check
        if (this.userRole === 'patient' && this.pendingFallCheckId) {
            const lowerText = text1.toLowerCase();

            // Patient says they're okay
            if (lowerText.includes('yes') || lowerText.includes('okay') || lowerText.includes('ok') ||
                lowerText.includes('fine') || lowerText.includes("i'm ok") || lowerText.includes("im ok") ||
                lowerText.includes("i am ok")) {

                fetch($SCRIPT_ROOT + '/patient_fall_response', {
                    method: 'POST',
                    body: JSON.stringify({
                        alert_id: this.pendingFallCheckId,
                        response: 'ok'
                    }),
                    mode: 'cors',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                }).then(r => r.json())
                  .then(r => {
                      let msg2 = { name: "REMONI", message: r.message || "Thank you for letting me know you're okay. " };
                      this.messages.push(msg2);
                      this.updateChatText(chatbox);
                      this.pendingFallCheckId = null;
                  }).catch((error) => {
                      let msg2 = { name: "REMONI", message: "Response recorded. Thank you!" };
                      this.messages.push(msg2);
                      this.updateChatText(chatbox);
                      this.pendingFallCheckId = null;
                  });

                return;
            }

            // Patient needs help
            if (lowerText.includes('help') || lowerText.includes('not ok') || lowerText.includes('emergency') ||
                lowerText.includes('need help') || lowerText.includes('hurt') || lowerText.includes('pain')) {

                fetch($SCRIPT_ROOT + '/patient_fall_response', {
                    method: 'POST',
                    body: JSON.stringify({
                        alert_id: this.pendingFallCheckId,
                        response: 'help'
                    }),
                    mode: 'cors',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                }).then(r => r.json())
                  .then(r => {
                      let msg2 = { name: "REMONI_EMERGENCY", message: r.message || "🚨 I've notified your doctor immediately. Help is coming. Please stay where you are if it's safe to do so.", isEmergency: true };
                      this.messages.push(msg2);
                      this.updateChatText(chatbox);
                      this.pendingFallCheckId = null;
                  }).catch((error) => {
                      let msg2 = { name: "REMONI_EMERGENCY", message: "🚨 Help is on the way! Your doctor has been notified.", isEmergency: true };
                      this.messages.push(msg2);
                      this.updateChatText(chatbox);
                      this.pendingFallCheckId = null;
                  });

                return;
            }
        }

        // Normal chat processing
        fetch($SCRIPT_ROOT + '/chat', {
            method: 'POST',
            body: JSON.stringify({
                message: text1,
                new_chat: this.forceNewChat === true
            }),
            mode: 'cors',
            headers: {
              'Content-Type': 'application/json'
            },
          })
          .then(r => r.json())
          .then(r => {
            this.forceNewChat = false;
            let msg2 = { name: "REMONI", message: r.answer };
            this.messages.push(msg2);
            this.updateChatText(chatbox);

            if ('plots' in r && r.plots && r.plots.length > 0) {
                let plotGroup = { name: "REMONI_Plot_Group", images: r.plots };
                this.messages.push(plotGroup);
                this.updateChatText(chatbox);
            }

            if ('images' in r && r.images && r.images.length > 0) {
                let imageGroup = { name: "REMONI_Setup_Image_Group", images: r.images };
                this.messages.push(imageGroup);
                this.updateChatText(chatbox);
            }
          }).catch((error) => {
            let msg2 = { name: "REMONI", message: "Sorry, system error. Please try again." };
            this.messages.push(msg2);
            console.error('Error:', error);
            this.updateChatText(chatbox);
          });
    }

    updateChatText(chatbox) {
        var html = '';

        this.messages.forEach((item) => {
            const formattedMessage = item.isEmergency
                ? item.message  // Already formatted from socket
                : this.formatMessage(item.message);

            if (item.name === "REMONI") {
                html += '<div class="messages__item messages__item--visitor">' + formattedMessage + '</div>'
            }
            else if (item.name === "REMONI_EMERGENCY") {
                html += '<div class="messages__item messages__item--emergency">' + formattedMessage + '</div>'
            }
            else if (item.name === "REMONI_VITALS") {
                html += '<div class="messages__item messages__item--vitals">' + formattedMessage + '</div>'
            }
            else if (item.name === "REMONI_STATUS") {
                html += '<div class="messages__item messages__item--status">' + formattedMessage + '</div>'
            }
            else if (item.name === "REMONI_Image") {
                html += '<div class="messages__item--image-container">' +
                        '<div class="messages__item--image-wrapper">' +
                        '<img src="' + item.message + '" class="messages__item--image--operator">' +
                        '</div>' +
                        '</div>'
            }
            else if (item.name === "REMONI_Plot_Group") {
                html += '<div class="messages__item--image-container">';
                item.images.forEach(imgPath => {
                    html += '<div class="messages__item--image-wrapper">' +
                            '<img src="' + imgPath + '" class="messages__item--image--operator">' +
                            '</div>';
                });
                html += '</div>';
            }
            else if (item.name === "REMONI_Setup_Image_Group") {
                html += '<div class="messages__item--image-container">';
                item.images.forEach(imgPath => {
                    html += '<div class="messages__item--image-wrapper">' +
                            '<img src="' + imgPath + '" class="messages__item--image--visitor">' +
                            '</div>';
                });
                html += '</div>';
            }
            else if (item.name === "REMONI_Image_Group") {
                html += '<div class="messages__item--image-container">';
                item.images.forEach(imgPath => {
                    html += '<div class="messages__item--image-wrapper">' +
                            '<img src="' + imgPath + '" class="messages__item--image--operator">' +
                            '</div>';
                });
                html += '</div>';
            }
            else {
                html += '<div class="messages__item messages__item--operator">' + formattedMessage + '</div>'
            }
        });

        const chatmessage = chatbox.querySelector('.chatbox__messages');
        const prevScrollTop = chatmessage.scrollTop;
        const distanceFromBottom = chatmessage.scrollHeight - chatmessage.scrollTop - chatmessage.clientHeight;
        const wasNearBottom = distanceFromBottom < 60;
        chatmessage.innerHTML = html;
        if (this.restoringHistory) {
            const saved = this.getSavedScroll();
            if (saved !== null) {
                const maxScroll = Math.max(0, chatmessage.scrollHeight - chatmessage.clientHeight);
                chatmessage.scrollTop = Math.min(saved, maxScroll);
            } else {
                chatmessage.scrollTop = chatmessage.scrollHeight;
            }
            this.restoringHistory = false;
        } else if (wasNearBottom) {
            chatmessage.scrollTop = chatmessage.scrollHeight;
        } else {
            chatmessage.scrollTop = prevScrollTop;
        }

        this.saveHistory();
    }
}

// ✅ INITIALIZE CHATBOX
const chatbox = new Chatbox(document.body.dataset.userRole);
chatbox.display();
