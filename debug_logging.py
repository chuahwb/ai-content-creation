#!/usr/bin/env python3
"""
Debug script to check logging configuration
Run this to see what LOG_LEVEL is being used
"""

import os
import logging

print("=== LOGGING DEBUG ===")
print(f"LOG_LEVEL env var: {os.getenv('LOG_LEVEL', 'NOT SET')}")
print(f"ENV env var: {os.getenv('ENV', 'NOT SET')}")

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
numeric_level = getattr(logging, log_level, logging.INFO)

print(f"Resolved log_level: {log_level}")
print(f"Numeric level: {numeric_level}")
print(f"INFO level: {logging.INFO}")
print(f"DEBUG level: {logging.DEBUG}")

# Configure logging the same way as the API
logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("test_logger")

print("\n=== TESTING LOG LEVELS ===")
logger.debug("🔍 This is a DEBUG message")
logger.info("ℹ️ This is an INFO message") 
logger.warning("⚠️ This is a WARNING message")
logger.error("❌ This is an ERROR message")

print(f"\nIf you only see INFO/WARNING/ERROR messages, your LOG_LEVEL is set to INFO")
print(f"If you see DEBUG messages too, your LOG_LEVEL is set to DEBUG")
