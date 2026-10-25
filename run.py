from app import create_app
from config import Config

app = create_app(Config)

if __name__ == "__main__":
    try:
        from waitress import serve
        print(f"[SERVER] Running production server on http://127.0.0.1:{Config.PORT}")
        serve(app, host=Config.HOST, port=Config.PORT, threads=8)
    except ImportError:
        print(f"[SERVER] Running threaded server on http://127.0.0.1:{Config.PORT}")
        app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)
