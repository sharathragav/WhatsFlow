document.addEventListener('DOMContentLoaded', () => {
    const whatsappConnector = {
        elements: {
            statusIndicator: document.getElementById('connectionStatus'),
            statusText: document.getElementById('statusText'),
            statusDescription: document.getElementById('statusDescription'),
            loadingSpinner: document.getElementById('loadingSpinner'),
            qrCodeArea: document.getElementById('qrCodeArea'),
            qrCodeImage: document.getElementById('qrCodeImage'),
            qrCodeText: document.getElementById('qrCodeText'),
            getQrBtn: document.getElementById('getQrBtn'),
            refreshBtn: document.getElementById('refreshBtn'),
            disconnectBtn: document.getElementById('disconnectBtn'),
            //historyTableBody: document.getElementById('connectionHistory').getElementsByTagName('tbody')[0]
            historyTableBody: document.getElementById('connectionHistory')

        },
        monitoringInterval: null,

        init() {
            this.bindEvents();
            this.checkStatus();
            //this.startMonitoring();
        },

        bindEvents() {
            console.log("this came before polling");
            this.elements.getQrBtn.addEventListener('click', () => this.getQRCode());
            this.elements.refreshBtn.addEventListener('click', () => this.checkStatus());
            this.elements.disconnectBtn.addEventListener('click', () => this.disconnect());
        },

        startMonitoring() {
            console.log("this came before binding ")
            if (this.monitoringInterval) clearInterval(this.monitoringInterval);
            this.monitoringInterval = setInterval(() => this.checkStatus(), 1000); // Poll every 10 seconds
        },
        async sleep(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        },
        async showToast(message, duration = 3000) {
            const toast = document.getElementById("toast");
            toast.textContent = message;
            toast.className = "show";

            setTimeout(() => {
                toast.className = toast.className.replace("show", "");
            }, duration);
        },

        async checkStatus() {
            this.showLoading(true);
            try {
                const response = await fetch('/api/whatsapp/status');
                const data = await response.json();
                console.log(data);
                this.updateUI(data);
            } catch (error) {
                console.error('Error which loding qr status:', error);
                this.updateUI({ status: 'error', message: 'Failed to connect to server.' });
            } finally {
                this.showLoading(false);
            }
        },

        async getQRCode() {
            this.showQrLoading(true);
            try {
                const response = await fetch('/api/whatsapp/qr');
                const data = await response.json();
                console.log("this work the qr code api");
                this.updateUI(data);
                if (data.success && data.qr_code) {
                    this.elements.qrCodeImage.src = data.qr_code;
                }
                await this.sleep(15000);

                const response_after_qr = await fetch('/api/whatsapp/status');
                const data_after_qr = await response_after_qr.json();
                console.log("this is the data after 2nd loop",data_after_qr);
                console.log(data_after_qr.connected);

                ///LOOP HAVING ISSUE NOT STOPING AT ANY POINT NOT SURE WHY!!!!!
                ///HAVE TO FIX THAT HAVE TRIES NORMAL BOOLEAN COMPARISION AND THEN TYPECONVERSTION

                // while (String(data_after_qr.connected).toLowerCase()!=="true"){
                //     this.showToast("not connected yet");
                //     await this.sleep(1000);
                //     const response_after_qr = await fetch('/api/whatsapp/status');
                //     const data_after_qr = await response_after_qr.json();
                //     console.log("this is the data after in loop",data_after_qr);
                //     console.log(typeof String(data_after_qr.connected).toLowerCase());
                //     console.log(String(data_after_qr.connected).toLowerCase());
                // }
                //this.updateUI(data);

            } catch (error) {
                console.error('Error getting QR code:', error);
                this.updateUI({ status: 'error', message: 'Failed to fetch QR code.' });
            } finally {
                this.showQrLoading(false);
            }
        },

        async disconnect() {
            this.showLoading(true);
            try {
                const response = await fetch('/api/whatsapp/disconnect', { method: 'POST' });
                const data = await response.json();
                showToast(data.message, data.success ? 'success' : 'error');
                // After disconnecting, immediately check status again
                this.checkStatus();
            } catch (error) {
                console.error('Error disconnecting:', error);
                showToast('Failed to disconnect.', 'error');
            } finally {
                this.showLoading(false);
            }
        },

        updateUI(data) {
            const { statusIndicator, statusText, statusDescription, qrCodeArea, qrCodeImage, qrCodeText, getQrBtn, disconnectBtn } = this.elements;

            // Update main status display
            statusIndicator.className = 'status-indicator'; // Reset
            statusText.textContent = (data.status || 'unknown').replace('_', ' ').toUpperCase();
            statusDescription.textContent = data.message;

            let statusClass = 'status-disconnected';
            let statusIcon = 'fa-exclamation-circle';

            if (data.connected) {
                statusClass = 'status-connected';
                statusIcon = 'fa-check-circle';
            } else if (data.status === 'error') {
                statusClass = 'status-error';
                statusIcon = 'fa-times-circle';
            } else if (data.status === 'qr_pending') {
                statusClass = 'status-pending';
                statusIcon = 'fa-qrcode';
            }
            console.log("data.conneted one done",statusClass,statusIcon);

            statusIndicator.classList.add(statusClass);
            statusIndicator.innerHTML = `<i class="fas ${statusIcon}"></i>`;
            console.log(data.qr_code,"\n\n\nqrcode data")
            //Update QR code display
            if (data.qr_code) {
                qrCodeArea.style.display = 'none';
                qrCodeImage.src = data.qr_code;
                qrCodeImage.style.display = 'block';
            } else {
                qrCodeArea.style.display = 'block';
                qrCodeImage.style.display = 'none';
                qrCodeArea.innerHTML = '<i class="fab fa-whatsapp fa-4x text-muted"></i>';
                qrCodeText.textContent = 'QR Code will appear here when scanning is needed';
            }
            
            if (data.already_connected) {
                 qrCodeArea.innerHTML = '<i class="fas fa-check-circle fa-4x text-success"></i>';
                 qrCodeText.textContent = data.message;
            }

            // Update button states
            getQrBtn.disabled = data.connected;
            disconnectBtn.disabled = !data.connected && data.status !== 'qr_pending';

            this.addHistoryEntry(data);
        },

        addHistoryEntry(data) {
            if (!data.timestamp) data.timestamp = new Date().toISOString();
            const { historyTableBody } = this.elements;
            const row = historyTableBody.insertRow(0);

            let statusBadge;
            if (data.connected) {
                statusBadge = `<span class="badge bg-success">Connected</span>`;
            } else if (data.status === 'error') {
                statusBadge = `<span class="badge bg-danger">Error</span>`;
            } else {
                statusBadge = `<span class="badge bg-warning text-dark">${(data.status || 'unknown').replace('_', ' ')}</span>`;
            }

            row.innerHTML = `
                <td>${statusBadge}</td>
                <td>${data.message || 'N/A'}</td>
                <td>${new Date(data.timestamp).toLocaleString()}</td>
            `;

            if (historyTableBody.rows.length > 10) {
                historyTableBody.deleteRow(10);
            }
        },

        showLoading(isLoading) {
            this.elements.loadingSpinner.style.display = isLoading ? 'block' : 'none';
            this.elements.refreshBtn.disabled = isLoading;
        },

        showQrLoading(isLoading) {
            const { qrCodeArea, qrCodeText } = this.elements;
            if (isLoading) {
                qrCodeArea.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
                qrCodeText.textContent = 'Retrieving QR code...';
            } 
            // The updateUI function will handle resetting the content
        }
    };

    whatsappConnector.init();
});
