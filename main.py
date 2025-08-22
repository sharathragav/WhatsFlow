
from app import app, scheduler

if __name__ == '__main__':
    try:
        if not scheduler.running:
            scheduler.start()
            print("APScheduler started...")
    except Exception as e:
        print(f"Scheduler already running or error: {e}")
    
    print("Starting WhatsApp Bulk Sender Application...")
    app.run(host='0.0.0.0', port=5000, debug=True)
