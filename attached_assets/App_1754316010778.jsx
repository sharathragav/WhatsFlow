import React, { useState, useEffect, useCallback } from 'react';
import FileDropzone from './components/FileDropzone';
import ProgressLog from './components/ProgressLog';
import { ToastContainer, useToast } from './components/Toast';
import { Send, Server, Zap, HelpCircle, Github } from 'lucide-react';

// API endpoint
const API_URL = '/api';

const App = () => {
  // File state
  const [recipientsFile, setRecipientsFile] = useState(null);
  const [attachmentFile, setAttachmentFile] = useState(null);

  // UI state
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);
  
  // Progress state
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [logs, setLogs] = useState([]);
  
  // Toast notifications
  const { toasts, showToast, removeToast } = useToast();

  // Poll for progress updates
  useEffect(() => {
    let interval;
    if (isSending) {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_URL}/progress`);
          if (!response.ok) {
            throw new Error('Failed to fetch progress');
          }
          const data = await response.json();
          
          setProgress({ current: data.current, total: data.total });
          setLogs(data.logs.map(log => {
            let type = 'info';
            if (log.includes('✓') || log.includes('Success')) type = 'success';
            if (log.includes('✗') || log.includes('Failed') || log.includes('Error')) type = 'error';
            return { message: log, type };
          }));

          if (!data.is_active) {
            setIsSending(false);
            showToast('Process completed!', 'success');
          }
        } catch (err) {
          setError(err.message);
          setIsSending(false);
          showToast(err.message, 'error');
        }
      }, 2000); // Poll every 2 seconds
    }
    return () => clearInterval(interval);
  }, [isSending, showToast]);

  // Handle form submission
  const handleSend = async () => {
    if (!recipientsFile) {
      showToast('Recipients file is required.', 'warning');
      return;
    }

    setIsSending(true);
    setError(null);
    setLogs([]);
    setProgress({ current: 0, total: 0 });

    const formData = new FormData();
    formData.append('recipientsFile', recipientsFile);
    if (attachmentFile) {
      formData.append('attachmentFile', attachmentFile);
    }

    try {
      const response = await fetch(`${API_URL}/send`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to start sending process.');
      }

      showToast(data.message, 'info');

    } catch (err) {
      setError(err.message);
      setIsSending(false);
      showToast(err.message, 'error');
    }
  };

  // Clear progress log
  const handleClearLog = () => {
    setLogs([]);
    setProgress({ current: 0, total: 0 });
  };

  return (
    <>
      <ToastContainer toasts={toasts} onRemove={removeToast} />
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4 font-sans">
        <div className="w-full max-w-3xl mx-auto">
          {/* Header */}
          <header className="text-center mb-8 animate-fade-in">
            <div className="flex items-center justify-center space-x-3 mb-2">
              <Zap className="w-8 h-8 text-whatsapp-green" />
              <h1 className="text-4xl font-bold text-gray-800">
                WhatsApp Bulk Sender
              </h1>
            </div>
            <p className="text-md text-gray-600">
              Automate your WhatsApp messaging with ease and efficiency.
            </p>
          </header>

          {/* Main Content */}
          <main className="bg-white p-8 rounded-2xl shadow-lg border border-gray-200">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Left Column: File Uploads */}
              <div className="space-y-6">
                <FileDropzone
                  label="Recipients File"
                  onFileSelect={setRecipientsFile}
                  acceptedFormats={['.xlsx', '.xls']}
                  currentFile={recipientsFile}
                  disabled={isSending}
                />
                <FileDropzone
                  label="Attachment (Optional)"
                  onFileSelect={setAttachmentFile}
                  acceptedFormats={['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx', '.txt']}
                  currentFile={attachmentFile}
                  disabled={isSending}
                />
              </div>

              {/* Right Column: Actions & Status */}
              <div className="flex flex-col justify-between">
                <div className="space-y-4">
                  <div className="p-4 bg-whatsapp-blue/10 border border-whatsapp-blue/20 rounded-lg">
                    <div className="flex items-start space-x-3">
                      <HelpCircle className="w-5 h-5 text-whatsapp-blue mt-0.5 flex-shrink-0" />
                      <div>
                        <h3 className="text-md font-semibold text-whatsapp-green-dark">Instructions</h3>
                        <ol className="list-decimal list-inside text-sm text-whatsapp-green-dark/80 mt-1 space-y-1">
                          <li>Upload an Excel file with a 'Contact' column.</li>
                          <li>Optionally, add a 'Message' column for personalized texts.</li>
                          <li>Optionally, attach a file to send to all contacts.</li>
                          <li>Click 'Send Messages' and scan the QR code in the new window.</li>
                        </ol>
                      </div>
                    </div>
                  </div>
                  
                  <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <Server className="w-5 h-5 text-gray-500" />
                      <div>
                        <h3 className="text-md font-semibold text-gray-800">Backend Status</h3>
                        <p className="text-sm text-gray-600">
                          API is expected to be running at <code className="bg-gray-200 px-1 rounded">/api</code>.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleSend}
                  disabled={isSending || !recipientsFile}
                  className={`
                    w-full flex items-center justify-center space-x-2 px-6 py-3 mt-6
                    text-lg font-semibold text-white rounded-lg shadow-md
                    transition-all duration-300 ease-in-out
                    ${isSending ? 'bg-gray-400 cursor-not-allowed' : 'bg-whatsapp-green hover:bg-whatsapp-green-dark'}
                    ${!recipientsFile && !isSending ? 'opacity-50 cursor-not-allowed' : ''}
                    focus:outline-none focus:ring-4 focus:ring-whatsapp-green/50
                  `}
                >
                  {isSending ? (
                    <div className="w-6 h-6 border-4 border-white border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <Send className="w-6 h-6" />
                  )}
                  <span>{isSending ? 'Sending...' : 'Send Messages'}</span>
                </button>
              </div>
            </div>

            {/* Progress Log */}
            {(isSending || logs.length > 0) && (
              <div className="mt-8">
                <ProgressLog
                  isActive={isSending}
                  progress={progress}
                  logs={logs}
                  onClose={handleClearLog}
                />
              </div>
            )}
          </main>

          {/* Footer */}
          <footer className="text-center mt-8">
            <p className="text-sm text-gray-500">
              Developed with ❤️ by Your Name. 
              <a 
                href="https://github.com/your-repo" 
                target="_blank" 
                rel="noopener noreferrer"
                className="ml-2 text-blue-500 hover:underline flex items-center justify-center"
              >
                <Github className="w-4 h-4 mr-1" />
                View on GitHub
              </a>
            </p>
          </footer>
        </div>
      </div>
    </>
  );
};

export default App;
