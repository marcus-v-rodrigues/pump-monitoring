import time
import random
import psycopg2
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
from flask import Flask, jsonify
from prometheus_client import start_http_server, Gauge, Counter, Histogram, CollectorRegistry
import psutil
import threading
from functools import lru_cache

# Logging configuration
log_format = os.getenv('LOGGING_FORMAT', 'json')
log_level = os.getenv('LOGGING_LEVEL', 'INFO')

if log_format.lower() == 'json':
    logging.basicConfig(
        level=log_level,
        format='{"timestamp":"%(asctime)s", "level":"%(levelname)s", "message":"%(message)s"}'
    )
else:
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Prometheus Metrics
registry = CollectorRegistry()

# Register metrics with custom registry to prevent duplicates
@lru_cache(maxsize=1)
def get_metrics():
    registry = CollectorRegistry()
    return {
        'pump_metrics': Gauge('pump_metrics', 'Pump metrics', ['metric_type'], registry=registry),
        'pump_operations': Counter('pump_operations_total', 'Total pump operations', ['operation_type'], registry=registry),
        'pump_processing_time': Histogram('pump_data_processing_seconds', 'Data processing time', registry=registry),
        'system_cpu': Gauge('system_cpu_usage', 'System CPU usage', registry=registry),
        'system_memory': Gauge('system_memory_usage', 'System memory usage', registry=registry),
        'system_disk': Gauge('system_disk_usage', 'System disk usage', registry=registry),
        'registry': registry
    }

load_dotenv()

class PumpDataProducer:
    def __init__(self):
        self.db_config = {
            'dbname': os.getenv('DATABASE_NAME', 'postgres'),
            'user': os.getenv('DATABASE_USER', 'postgres'),
            'password': os.getenv('DATABASE_PASSWORD', 'postgres'),
            'host': os.getenv('DATABASE_HOST', 'pump-monitoring-timescaledb'),
            'port': os.getenv('DATABASE_PORT', '5432')
        }
        self.pump_id = os.getenv('PUMP_ID', 'pump1')
        self.max_retries = 5
        self.retry_delay = 5
        self.retention_days = int(os.getenv('DATA_RETENTION_DAYS', '30'))
        self.debug = os.getenv('MONITORING_DEBUG', 'false').lower() == 'true'
        self.setup_database()
        self.setup_system_metrics_monitoring()

    def setup_system_metrics_monitoring(self):
        def monitor_system_metrics():
            metrics = get_metrics()
            last_update = 0
            while True:
                try:
                    current_time = time.time()
                    if current_time - last_update >= 15:
                        cpu_usage = psutil.cpu_percent(interval=1)
                        memory_usage = psutil.virtual_memory().percent
                        disk_usage = psutil.disk_usage('/').percent

                        metrics['system_cpu'].set(cpu_usage)
                        metrics['system_memory'].set(memory_usage)
                        metrics['system_disk'].set(disk_usage)

                        logger.info(f"System - CPU: {cpu_usage}%, Memory: {memory_usage}%, Disk: {disk_usage}%")
                        last_update = current_time
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error collecting system metrics: {e}")
                    time.sleep(1)

        threading.Thread(target=monitor_system_metrics, daemon=True).start()

    def setup_database(self):
        """Configures the database schema with reconnection attempts."""
        metrics = get_metrics()
        retry_count = 0
        last_error = None

        while retry_count < self.max_retries:
            try:
                conn = psycopg2.connect(**self.db_config)
                conn.autocommit = True
                cur = conn.cursor()
                
                # Create TimescaleDB extension if it doesn't exist
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                
                # Create table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pump_metrics (
                        time TIMESTAMPTZ NOT NULL,
                        pump_id TEXT,
                        pressure FLOAT,
                        flow_rate FLOAT,
                        temperature FLOAT,
                        vibration FLOAT,
                        power_consumption FLOAT
                    );
                """)
                
                # Create useful indices
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_pump_metrics_pump_id 
                    ON pump_metrics (pump_id, time DESC);
                """)
                
                # Convert to hypertable if not already
                cur.execute("""
                    SELECT create_hypertable('pump_metrics', 'time', 
                        if_not_exists => TRUE, 
                        migrate_data => TRUE);
                """)
                
                # Configure data retention policies
                cur.execute(f"""
                    SELECT add_retention_policy('pump_metrics', 
                        INTERVAL '{self.retention_days} days', 
                        if_not_exists => TRUE);
                """)
                
                logger.info("✅ Database configured successfully!")
                cur.close()
                conn.close()
                metrics['pump_operations'].labels(operation_type='success').inc()
                return True
                
            except psycopg2.Error as e:
                last_error = e
                retry_count += 1
                logger.error(f"Attempt {retry_count} failed: {e}")
                metrics['pump_operations'].labels(operation_type='failure').inc()
                if retry_count < self.max_retries:
                    logger.info(f"Trying again in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                continue
                
            except Exception as e:
                metrics['pump_operations'].labels(operation_type='error').inc()
                logger.error(f"Unexpected error configuring database: {e}")
                return False

        if last_error:
            logger.error(f"❌ Failed to configure database after {self.max_retries} attempts: {last_error}")
            raise last_error

    def format_data(self, data):
        """Formats data for log display."""
        return (
            f"Pressure: {data['pressure']:.2f} PSI, "
            f"Flow Rate: {data['flow_rate']:.2f} L/min, "
            f"Temperature: {data['temperature']:.2f}°C, "
            f"Vibration: {data['vibration']:.4f} mm/s, "
            f"Power Consumption: {data['power_consumption']:.2f} kW"
        )

    def generate_pump_data(self):
        """Generates simulated pump data."""
        metrics = get_metrics()
        with metrics['pump_processing_time'].time():
            data = {
                'pressure': random.uniform(2.0, 4.0),
                'flow_rate': random.uniform(100, 200),
                'temperature': random.uniform(35, 45),
                'vibration': abs(np.random.normal(0.5, 0.1)),
                'power_consumption': random.uniform(75, 85)
            }
            return data

    def store_data(self, data):
        metrics = get_metrics()
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                conn = psycopg2.connect(**self.db_config)
                cur = conn.cursor()
                
                cur.execute("""
                    INSERT INTO pump_metrics (
                        time, pump_id, pressure, flow_rate, 
                        temperature, vibration, power_consumption
                    ) VALUES (NOW(), %s, %s, %s, %s, %s, %s)
                """, (
                    self.pump_id,
                    data['pressure'],
                    data['flow_rate'],
                    data['temperature'],
                    data['vibration'],
                    data['power_consumption']
                ))
                
                conn.commit()
                cur.close()
                conn.close()

                # Update pump metrics
                for key, value in data.items():
                    metrics['pump_metrics'].labels(metric_type=key).set(value)

                metrics['pump_operations'].labels(operation_type='success').inc()
                return True

            except Exception as e:
                retry_count += 1
                logger.error(f"Attempt {retry_count} failed to store data: {e}")
                metrics['pump_operations'].labels(operation_type='failure').inc()
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                continue

        logger.error(f"❌ Failed to store data after {self.max_retries} attempts")
        return False

    def run(self):
        """Main producer loop.
        
        This method implements the main loop that:
        1. Continuously generates and stores data
        2. Manages metrics and monitoring
        3. Implements failure recovery logic
        4. Maintains operation statistics
        """
        metrics = get_metrics()
        consecutive_failures = 0
        max_consecutive_failures = 3
        base_delay = 1  # Base delay in seconds
        max_delay = 30  # Maximum delay in seconds

        logger.info(f"✅ Starting Data Producer for Pump {self.pump_id}")
        
        while True:
            try:
                # Generate and store data with time monitoring
                with metrics['pump_processing_time'].time():
                    data = self.generate_pump_data()
                    success = self.store_data(data)

                if success:
                    # Reset counters on success
                    consecutive_failures = 0
                    formatted_data = self.format_data(data)
                    metrics['pump_operations'].labels(operation_type='total').inc()
                    logger.info(f"✅ Data stored successfully: {formatted_data}")
                    
                    # Standard delay between successful operations
                    time.sleep(base_delay)
                else:
                    # Increment failures and apply exponential backoff
                    consecutive_failures += 1
                    delay = min(base_delay * (2 ** consecutive_failures), max_delay)
                    
                    logger.warning(
                        f" ⚠️ Failed to store data. "
                        f"Attempt {consecutive_failures} of {max_consecutive_failures}. "
                        f"Waiting {delay} seconds."
                    )
                    
                    # Check if maximum consecutive failures reached
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            f" ❌ Maximum number of consecutive failures reached "
                            f"({max_consecutive_failures}). Restarting service..."
                        )
                        # Here we could implement a restart logic
                        # For now, we just reset the counter
                        consecutive_failures = 0
                    
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"❌ Critical error in the main loop: {str(e)}")
                metrics['pump_operations'].labels(operation_type='error').inc()
                
                # On critical error, wait before trying again
                time.sleep(5)
                continue

@app.route('/health')
def health():
    """
    Application health check endpoint.
    Returns the service status and pump identifier.
    This endpoint is crucial for monitoring and service
    availability checks (health checks).
    """
    return {
        'status': 'healthy',
        'pump_id': os.getenv('PUMP_ID', 'unknown')
    }, 200

@app.route('/metrics/summary')
def metrics_summary():
    """
    Endpoint for pump metrics statistical summary.
    Provides a consolidated view of the latest collected metrics,
    including pressure, temperature, and vibration averages from the last hour,
    plus current system resource usage.
    """
    try:
        conn = psycopg2.connect(**PumpDataProducer().db_config)
        cur = conn.cursor()
        
        # Query metrics from the last hour
        cur.execute("""
            SELECT 
                COUNT(*) as total_records,
                AVG(pressure) as avg_pressure,
                AVG(temperature) as avg_temperature,
                AVG(vibration) as avg_vibration
            FROM pump_metrics 
            WHERE time > NOW() - INTERVAL '1 hour'
        """)
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        return jsonify({
            'total_records': result[0],
            'average_pressure': result[1],
            'average_temperature': result[2],
            'average_vibration': result[3],
            'system_cpu_usage': psutil.cpu_percent(),
            'system_memory_usage': psutil.virtual_memory().percent
        })
    except Exception as e:
        logger.error(f"❌ Error retrieving metrics summary: {e}")
        return {'error': str(e)}, 500

if __name__ == "__main__":
    # Initial server configuration
    prometheus_port = int(os.getenv('MONITORING_PROMETHEUS_PORT', '8000'))
    flask_port = int(os.getenv('MONITORING_FLASK_PORT', '8080'))
    
    # Start Prometheus server in separate thread
    metrics = get_metrics()
    start_http_server(prometheus_port, registry=metrics['registry'])
    logger.info(f"📊 Prometheus server started on port {prometheus_port}")
    
    # Start Flask server in separate thread
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host='0.0.0.0', 
            port=flask_port, 
            debug=os.getenv('MONITORING_DEBUG', 'false').lower() == 'true'
        ),
        daemon=True  # Ensures thread terminates when main program ends
    )
    flask_thread.start()
    logger.info(f"🌐 Flask server started on port {flask_port}")
    
    try:
        # Start the producer
        producer = PumpDataProducer()
        logger.info("🚀 Starting data producer...")
        producer.run()
    except KeyboardInterrupt:
        logger.info("👋 Wrapping up data producer...")
    except Exception as e:
        logger.error(f"❌ Crash when starting producer: {str(e)}")
        raise