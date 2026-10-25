from app import create_app
from config import Config

app = create_app(Config)

if __name__ == "__main__":
    try:
        from waitress import serve
        print(f"[SERVER] Starting production WSGI server on http://{Config.HOST}:{Config.PORT}")
        serve(app, host=Config.HOST, port=Config.PORT, threads=8)
    except ImportError:
        print(f"[SERVER] Starting threaded server on http://{Config.HOST}:{Config.PORT}")
        app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
