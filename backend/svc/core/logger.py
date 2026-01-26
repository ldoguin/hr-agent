import logging
import sys

def configure_logger() -> None:
    """Configure a custom logger with Couchbase SDK logging."""

    # Create a logger
    logger = logging.getLogger("uvicorn.error" )
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(processName)s: %(process)d] [%(threadName)s: %(thread)d] [%(levelname)s] %(name)s: %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler("info.log")
    file_handler.setFormatter(formatter)

    #logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    # Configure Couchbase SDK logging to show query details
    couchbase_logger = logging.getLogger("couchbase")
    couchbase_logger.setLevel(logging.DEBUG)

    # Add handlers to Couchbase logger
    couchbase_stream_handler = logging.StreamHandler(sys.stdout)
    couchbase_stream_handler.setFormatter(formatter)
    couchbase_file_handler = logging.FileHandler("couchbase_queries.log")
    couchbase_file_handler.setFormatter(formatter)

    couchbase_logger.addHandler(couchbase_stream_handler)
    couchbase_logger.addHandler(couchbase_file_handler)

    # Also configure specific Couchbase modules for detailed query logging
    logging.getLogger("couchbase.query").setLevel(logging.DEBUG)
    logging.getLogger("couchbase.search").setLevel(logging.DEBUG)
    logging.getLogger("couchbase.analytics").setLevel(logging.DEBUG)
    logging.getLogger("couchbase.vector_search").setLevel(logging.DEBUG)
