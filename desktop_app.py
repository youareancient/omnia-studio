import sys
import os
import threading
import time
import webview

# Add current directory to path
STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO_DIR)

from app import create_app, HOST, PORT
from aiohttp import web

def start_server():
    try:
        app = create_app()
        web.run_app(app, host=HOST, port=PORT, print=None)
    except Exception as e:
        print("[Server Thread Error]:", e)

if __name__ == '__main__':
    # Start app server in background daemon thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Allow server to initialize
    time.sleep(1.2)
    
    # Launch native Windows Desktop Application Window
    window = webview.create_window(
        title='YouTube 2.0 Production Studio',
        url=f'http://localhost:{PORT}/youtube-2.0',
        width=1380,
        height=900,
        resizable=True,
        min_size=(1024, 700)
    )
    webview.start()
