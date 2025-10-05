import multiprocessing  # For CPU core count to size workers dynamically
import os  # For reading optional WEB_CONCURRENCY override

# Allow explicit override via WEB_CONCURRENCY, else use heuristic (2 x cores) + 1
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))  # (2 x cores) + 1 heuristic
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "wms.settings"))  # Ensure Django settings loaded from env
threads = 1  # Threads per worker process (raise for more I/O concurrency)
worker_class = "gthread"  # Threaded worker class (enables >1 threads if increased)
accesslog = "-"  # Write HTTP access logs to stdout (captured by container logs)
errorlog = "-"  # Write error logs to stderr (captured by container logs)
loglevel = "info"  # Logging verbosity (debug < info < warning < error < critical)
timeout = 60  # Restart worker if a single request runs longer than 60s
keepalive = 5  # Seconds to hold an idle HTTP connection open for reuse
