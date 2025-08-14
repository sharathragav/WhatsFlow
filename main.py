from app import app, scheduler

if __name__ == '__main__':

    print("APScheduler started...")
    print("Starting WhatsApp Bulk Sender Application...")
    app.run(host='0.0.0.0', port=5000, debug=True)