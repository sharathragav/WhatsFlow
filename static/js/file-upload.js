/**
 * WhatsApp File Upload Handler
 * Manages file uploads, validation, and drag-and-drop functionality
 */

class FileUploadHandler {
    constructor(options = {}) {
        this.options = {
            maxFileSize: 16 * 1024 * 1024, // 16MB
            allowedRecipientTypes: ['xlsx', 'xls'],
            allowedAttachmentTypes: ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'txt'],
            dragDropEnabled: true,
            validateOnSelect: true,
            ...options
        };
        
        this.uploadedFiles = {
            recipients: null,
            attachment: null
        };
        
        this.init();
    }

    init() {
        this.setupFileInputs();
        this.setupDragAndDrop();
        this.bindEvents();
        console.log('File Upload Handler initialized');
    }

    setupFileInputs() {
        // Find file input elements
        this.elements = {
            recipientsFile: document.getElementById('recipientsFile'),
            attachmentFile: document.getElementById('attachmentFile'),
            excelFile: document.getElementById('excelFile'), // For modals
            campaignImage: document.getElementById('campaignImage'),
            importFile: document.getElementById('importFile')
        };

        // Add file input event listeners
        Object.entries(this.elements).forEach(([key, element]) => {
            if (element) {
                element.addEventListener('change', (e) => {
                    this.handleFileSelect(e, key);
                });
            }
        });
    }

    setupDragAndDrop() {
        if (!this.options.dragDropEnabled) return;

        // Create drag and drop zones
        this.createDropZones();
        
        // Prevent default drag behaviors on document
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight drop zones on drag enter/over
        ['dragenter', 'dragover'].forEach(eventName => {
            document.addEventListener(eventName, this.highlight.bind(this), false);
        });

        // Remove highlight on drag leave/drop
        ['dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, this.unhighlight.bind(this), false);
        });

        // Handle dropped files
        document.addEventListener('drop', this.handleDrop.bind(this), false);
    }

    createDropZones() {
        const fileInputs = document.querySelectorAll('input[type="file"]');
        
        fileInputs.forEach(input => {
            if (input.closest('.file-upload-area')) return; // Already has drop zone
            
            const wrapper = document.createElement('div');
            wrapper.className = 'file-upload-area';
            wrapper.innerHTML = `
                <div class="upload-icon">
                    <i class="fas fa-cloud-upload-alt fa-3x text-muted"></i>
                </div>
                <div class="upload-text">
                    <p class="mb-1"><strong>Drag and drop files here</strong></p>
                    <p class="text-muted small">or click to browse</p>
                </div>
            `;
            
            // Insert wrapper and move input inside
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
            
            // Make wrapper clickable
            wrapper.addEventListener('click', (e) => {
                if (e.target !== input) {
                    input.click();
                }
            });
        });
    }

    bindEvents() {
        // Clear file buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-clear-file]')) {
                const inputId = e.target.getAttribute('data-clear-file');
                this.clearFile(inputId);
            }
        });

        // File preview buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-preview-file]')) {
                const inputId = e.target.getAttribute('data-preview-file');
                this.previewFile(inputId);
            }
        });
    }

    handleFileSelect(event, inputType) {
        const file = event.target.files[0];
        if (!file) return;

        console.log(`File selected for ${inputType}:`, file.name);

        // Validate file
        const validation = this.validateFile(file, inputType);
        if (!validation.valid) {
            this.showError(validation.error);
            event.target.value = ''; // Clear invalid file
            return;
        }

        // Store file reference
        this.uploadedFiles[inputType] = file;

        // Update UI
        this.updateFileDisplay(event.target, file);
        
        // Show success message
        this.showSuccess(`${file.name} selected successfully`);

        // Trigger file analysis for recipients file
        if (inputType === 'recipientsFile' || inputType === 'excelFile') {
            this.analyzeRecipientsFile(file);
        }
    }

    validateFile(file, inputType) {
        // Check file size
        if (file.size > this.options.maxFileSize) {
            return {
                valid: false,
                error: `File size exceeds ${this.formatFileSize(this.options.maxFileSize)} limit`
            };
        }

        // Check file type
        const extension = file.name.split('.').pop().toLowerCase();
        let allowedTypes = [];

        switch (inputType) {
            case 'recipientsFile':
            case 'excelFile':
                allowedTypes = this.options.allowedRecipientTypes;
                break;
            case 'attachmentFile':
            case 'campaignImage':
                allowedTypes = this.options.allowedAttachmentTypes;
                break;
            case 'importFile':
                allowedTypes = ['json'];
                break;
            default:
                allowedTypes = [...this.options.allowedRecipientTypes, ...this.options.allowedAttachmentTypes];
        }

        if (!allowedTypes.includes(extension)) {
            return {
                valid: false,
                error: `Invalid file type. Allowed: ${allowedTypes.join(', ')}`
            };
        }

        return { valid: true };
    }

    updateFileDisplay(input, file) {
        const wrapper = input.closest('.file-upload-area') || input.parentElement;
        
        // Update display text
        const uploadText = wrapper.querySelector('.upload-text');
        if (uploadText) {
            uploadText.innerHTML = `
                <p class="mb-1 text-success"><strong><i class="fas fa-check-circle me-1"></i>${file.name}</strong></p>
                <p class="text-muted small">${this.formatFileSize(file.size)} • ${file.type || 'Unknown type'}</p>
                <div class="mt-2">
                    <button type="button" class="btn btn-sm btn-outline-secondary me-1" data-preview-file="${input.id}">
                        <i class="fas fa-eye me-1"></i>Preview
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger" data-clear-file="${input.id}">
                        <i class="fas fa-times me-1"></i>Remove
                    </button>
                </div>
            `;
        }

        // Update icon
        const uploadIcon = wrapper.querySelector('.upload-icon');
        if (uploadIcon) {
            const iconClass = this.getFileIcon(file);
            uploadIcon.innerHTML = `<i class="${iconClass} fa-3x text-success"></i>`;
        }
    }

    getFileIcon(file) {
        const extension = file.name.split('.').pop().toLowerCase();
        const iconMap = {
            'xlsx': 'fas fa-file-excel',
            'xls': 'fas fa-file-excel',
            'pdf': 'fas fa-file-pdf',
            'doc': 'fas fa-file-word',
            'docx': 'fas fa-file-word',
            'jpg': 'fas fa-file-image',
            'jpeg': 'fas fa-file-image',
            'png': 'fas fa-file-image',
            'gif': 'fas fa-file-image',
            'txt': 'fas fa-file-alt',
            'json': 'fas fa-file-code'
        };
        
        return iconMap[extension] || 'fas fa-file';
    }

    clearFile(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;

        // Clear input value
        input.value = '';
        
        // Reset display
        const wrapper = input.closest('.file-upload-area') || input.parentElement;
        const uploadText = wrapper.querySelector('.upload-text');
        const uploadIcon = wrapper.querySelector('.upload-icon');
        
        if (uploadText) {
            uploadText.innerHTML = `
                <p class="mb-1"><strong>Drag and drop files here</strong></p>
                <p class="text-muted small">or click to browse</p>
            `;
        }
        
        if (uploadIcon) {
            uploadIcon.innerHTML = '<i class="fas fa-cloud-upload-alt fa-3x text-muted"></i>';
        }

        // Clear stored file reference
        const inputType = this.getInputType(inputId);
        if (inputType) {
            this.uploadedFiles[inputType] = null;
        }

        this.showSuccess('File removed');
    }

    getInputType(inputId) {
        const typeMap = {
            'recipientsFile': 'recipients',
            'attachmentFile': 'attachment',
            'excelFile': 'recipients',
            'campaignImage': 'attachment'
        };
        return typeMap[inputId];
    }

    async analyzeRecipientsFile(file) {
        try {
            // Show analysis in progress
            this.showInfo('Analyzing recipients file...');
            
            // Read file content (for Excel files, this would require a library like SheetJS)
            // For now, we'll simulate the analysis
            setTimeout(() => {
                this.showAnalysisResults(file);
            }, 1000);
            
        } catch (error) {
            console.error('Error analyzing file:', error);
            this.showError('Could not analyze recipients file');
        }
    }

    showAnalysisResults(file) {
        // Simulate analysis results
        const mockResults = {
            totalRows: Math.floor(Math.random() * 1000) + 100,
            hasContactColumn: true,
            hasMessageColumn: Math.random() > 0.5,
            validContacts: Math.floor(Math.random() * 900) + 80,
            duplicates: Math.floor(Math.random() * 20)
        };

        const analysisHtml = `
            <div class="alert alert-info mt-2">
                <h6><i class="fas fa-info-circle me-1"></i>File Analysis Results</h6>
                <ul class="list-unstyled mb-0 small">
                    <li><strong>Total rows:</strong> ${mockResults.totalRows}</li>
                    <li><strong>Valid contacts:</strong> ${mockResults.validContacts}</li>
                    <li><strong>Has Contact column:</strong> ${mockResults.hasContactColumn ? 'Yes' : 'No'}</li>
                    <li><strong>Has Message column:</strong> ${mockResults.hasMessageColumn ? 'Yes' : 'No'}</li>
                    ${mockResults.duplicates > 0 ? `<li class="text-warning"><strong>Duplicates found:</strong> ${mockResults.duplicates}</li>` : ''}
                </ul>
            </div>
        `;

        // Find container to show analysis
        const input = document.getElementById('recipientsFile') || document.getElementById('excelFile');
        if (input) {
            const container = input.closest('.modal-body') || input.closest('.card-body');
            if (container) {
                // Remove existing analysis
                const existingAnalysis = container.querySelector('.file-analysis');
                if (existingAnalysis) {
                    existingAnalysis.remove();
                }
                
                // Add new analysis
                const analysisDiv = document.createElement('div');
                analysisDiv.className = 'file-analysis';
                analysisDiv.innerHTML = analysisHtml;
                
                const fileGroup = input.closest('.mb-3') || input.parentElement;
                fileGroup.insertAdjacentElement('afterend', analysisDiv);
            }
        }
    }

    previewFile(inputId) {
        const input = document.getElementById(inputId);
        if (!input || !input.files[0]) return;

        const file = input.files[0];
        const extension = file.name.split('.').pop().toLowerCase();

        if (['jpg', 'jpeg', 'png', 'gif'].includes(extension)) {
            this.previewImage(file);
        } else if (extension === 'pdf') {
            this.previewPDF(file);
        } else if (['xlsx', 'xls'].includes(extension)) {
            this.previewExcel(file);
        } else {
            this.showInfo('Preview not available for this file type');
        }
    }

    previewImage(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            this.showPreviewModal(`
                <img src="${e.target.result}" class="img-fluid" alt="${file.name}" style="max-height: 70vh;">
            `, file.name);
        };
        reader.readAsDataURL(file);
    }

    previewPDF(file) {
        const url = URL.createObjectURL(file);
        this.showPreviewModal(`
            <iframe src="${url}" style="width: 100%; height: 70vh;" frameborder="0"></iframe>
        `, file.name);
    }

    previewExcel(file) {
        // For Excel preview, we'd need a library like SheetJS
        // For now, show basic file info
        this.showPreviewModal(`
            <div class="text-center p-4">
                <i class="fas fa-file-excel fa-5x text-success mb-3"></i>
                <h5>${file.name}</h5>
                <p class="text-muted">Excel file preview requires additional processing</p>
                <p><strong>Size:</strong> ${this.formatFileSize(file.size)}</p>
                <p><strong>Type:</strong> ${file.type}</p>
            </div>
        `, file.name);
    }

    showPreviewModal(content, title) {
        // Create modal if it doesn't exist
        let modal = document.getElementById('filePreviewModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'filePreviewModal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">File Preview</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body text-center">
                            <!-- Content will be inserted here -->
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        // Update content
        modal.querySelector('.modal-title').textContent = title;
        modal.querySelector('.modal-body').innerHTML = content;

        // Show modal
        const modalInstance = new bootstrap.Modal(modal);
        modalInstance.show();
    }

    // Drag and drop event handlers
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight(e) {
        if (e.target.closest('.file-upload-area')) {
            e.target.closest('.file-upload-area').classList.add('dragover');
        }
    }

    unhighlight(e) {
        document.querySelectorAll('.file-upload-area').forEach(area => {
            area.classList.remove('dragover');
        });
    }

    handleDrop(e) {
        const dropZone = e.target.closest('.file-upload-area');
        if (!dropZone) return;

        const files = e.dataTransfer.files;
        if (files.length === 0) return;

        const input = dropZone.querySelector('input[type="file"]');
        if (!input) return;

        // Handle single file drop
        const file = files[0];
        
        // Create a new FileList with the dropped file
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;

        // Trigger change event
        const event = new Event('change', { bubbles: true });
        input.dispatchEvent(event);
    }

    // Utility methods
    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showInfo(message) {
        this.showNotification(message, 'info');
    }

    showNotification(message, type) {
        if (window.dashboardUtils) {
            window.dashboardUtils.showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    // Get uploaded files
    getUploadedFiles() {
        return { ...this.uploadedFiles };
    }

    // Check if required files are uploaded
    isReady() {
        return this.uploadedFiles.recipients !== null;
    }

    // Create FormData for API submission
    createFormData() {
        const formData = new FormData();
        
        if (this.uploadedFiles.recipients) {
            formData.append('recipientsFile', this.uploadedFiles.recipients);
        }
        
        if (this.uploadedFiles.attachment) {
            formData.append('attachmentFile', this.uploadedFiles.attachment);
        }
        
        return formData;
    }

    // Reset all uploads
    reset() {
        Object.keys(this.uploadedFiles).forEach(key => {
            this.uploadedFiles[key] = null;
        });
        
        // Clear all file inputs
        Object.values(this.elements).forEach(input => {
            if (input) {
                input.value = '';
                this.resetFileDisplay(input);
            }
        });
    }

    resetFileDisplay(input) {
        const wrapper = input.closest('.file-upload-area');
        if (wrapper) {
            const uploadText = wrapper.querySelector('.upload-text');
            const uploadIcon = wrapper.querySelector('.upload-icon');
            
            if (uploadText) {
                uploadText.innerHTML = `
                    <p class="mb-1"><strong>Drag and drop files here</strong></p>
                    <p class="text-muted small">or click to browse</p>
                `;
            }
            
            if (uploadIcon) {
                uploadIcon.innerHTML = '<i class="fas fa-cloud-upload-alt fa-3x text-muted"></i>';
            }
        }
    }
}

// Initialize file upload handler when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.fileUploader = new FileUploadHandler();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FileUploadHandler;
} else {
    window.FileUploadHandler = FileUploadHandler;
}
