import multiprocessing  # For CPU core count to size workers dynamically
import os  # For reading optional WEB_CONCURRENCY override

# For Nano containers (512MB), use 1 worker to maximize available memory per request.
# The default heuristic (2*cores+1) causes OOM with large image processing.
# Override via WEB_CONCURRENCY env var for larger containers.
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "wms.settings"))  # Ensure Django settings loaded from env
threads = 1  # Threads per worker process (raise for more I/O concurrency)
worker_class = "gthread"  # Threaded worker class (enables >1 threads if increased)
errorlog = "-"  # Write error logs to stderr (captured by container logs)
loglevel = "info"  # Logging verbosity (debug < info < warning < error < critical)
timeout = 60  # Restart worker if a single request runs longer than 60s
keepalive = 5  # Seconds to hold an idle HTTP connection open for reuse

# Disable gunicorn access log - Django middleware handles request logging with filtering
# This eliminates health check noise from ELB-HealthChecker hitting /healthz/
accesslog = None
