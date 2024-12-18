import time
import random
import psycopg2
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
from flask import Flask, jsonify
from prometheus_client import start_http_server, Gauge, Counter, Histogram
import psutil
import threading

# Configuração do logging
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

# Métricas Prometheus
PUMP_METRICS = Gauge('pump_metrics', 'Métricas da bomba', ['metric_type'])
PUMP_OPERATIONS = Counter('pump_operations_total', 'Total de operações da bomba', ['operation_type'])
PUMP_DATA_PROCESSING_TIME = Histogram('pump_data_processing_seconds', 'Tempo de processamento dos dados')
SYSTEM_CPU_USAGE = Gauge('system_cpu_usage', 'Uso de CPU do sistema')
SYSTEM_MEMORY_USAGE = Gauge('system_memory_usage', 'Uso de memória do sistema')
SYSTEM_DISK_USAGE = Gauge('system_disk_usage', 'Uso de disco do sistema')

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
            last_update = 0
            while True:
                try:
                    current_time = time.time()
                    if current_time - last_update >= 15:
                        cpu_usage = psutil.cpu_percent(interval=1)
                        memory_usage = psutil.virtual_memory().percent
                        disk_usage = psutil.disk_usage('/').percent

                        SYSTEM_CPU_USAGE.set(cpu_usage)
                        SYSTEM_MEMORY_USAGE.set(memory_usage)
                        SYSTEM_DISK_USAGE.set(disk_usage)

                        logger.info(f"Sistema - CPU: {cpu_usage}%, Memória: {memory_usage}%, Disco: {disk_usage}%")
                        last_update = current_time
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Erro ao coletar métricas do sistema: {e}")
                    time.sleep(1)

        threading.Thread(target=monitor_system_metrics, daemon=True).start()

    def setup_database(self):
        """Configura o esquema do banco de dados com tentativas de reconexão."""
        retry_count = 0
        last_error = None

        while retry_count < self.max_retries:
            try:
                conn = psycopg2.connect(**self.db_config)
                conn.autocommit = True
                cur = conn.cursor()
                
                # Criar extensão TimescaleDB se não existir
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                
                # Criar tabela se não existir
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
                
                # Criar índices úteis
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_pump_metrics_pump_id 
                    ON pump_metrics (pump_id, time DESC);
                """)
                
                # Converter para hypertable se ainda não for
                cur.execute("""
                    SELECT create_hypertable('pump_metrics', 'time', 
                        if_not_exists => TRUE, 
                        migrate_data => TRUE);
                """)
                
                # Configurar políticas de retenção de dados
                cur.execute(f"""
                    SELECT add_retention_policy('pump_metrics', 
                        INTERVAL '{self.retention_days} days', 
                        if_not_exists => TRUE);
                """)
                
                logger.info("✅ Banco de dados configurado com sucesso!")
                cur.close()
                conn.close()
                PUMP_OPERATIONS.labels(operation_type='success').inc()
                return True
                
            except psycopg2.Error as e:
                last_error = e
                retry_count += 1
                logger.error(f"Tentativa {retry_count} falhou: {e}")
                PUMP_OPERATIONS.labels(operation_type='failure').inc()
                if retry_count < self.max_retries:
                    logger.info(f"Tentando novamente em {self.retry_delay} segundos...")
                    time.sleep(self.retry_delay)
                continue
                
            except Exception as e:
                PUMP_OPERATIONS.labels(operation_type='error').inc()
                logger.error(f"Erro inesperado ao configurar banco de dados: {e}")
                return False

        if last_error:
            logger.error(f"❌ Falha ao configurar banco de dados após {self.max_retries} tentativas: {last_error}")
            raise last_error

    def format_data(self, data):
        """Formata os dados para exibição no log."""
        return (
            f"Pressão: {data['pressure']:.2f} PSI, "
            f"Fluxo: {data['flow_rate']:.2f} L/min, "
            f"Temperatura: {data['temperature']:.2f}°C, "
            f"Vibração: {data['vibration']:.4f} mm/s, "
            f"Consumo: {data['power_consumption']:.2f} kW"
        )

    @PUMP_DATA_PROCESSING_TIME.time()
    def generate_pump_data(self):
        """Gera dados simulados da bomba."""
        data = {
            'pressure': random.uniform(2.0, 4.0),
            'flow_rate': random.uniform(100, 200),
            'temperature': random.uniform(35, 45),
            'vibration': abs(np.random.normal(0.5, 0.1)),
            'power_consumption': random.uniform(75, 85)
        }
        return data

    def store_data(self, data):
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

                # Atualizar métricas da bomba
                for key, value in data.items():
                    PUMP_METRICS.labels(metric_type=key).set(value)

                PUMP_OPERATIONS.labels(operation_type='success').inc()
                return True

            except Exception as e:
                retry_count += 1
                logger.error(f"Tentativa {retry_count} falhou ao armazenar dados: {e}")
                PUMP_OPERATIONS.labels(operation_type='failure').inc()
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                continue

        logger.error(f"❌ Failed to store data after {self.max_retries} attempts")
        return False

    def run(self):
        """Loop principal do produtor.
        
        Este método implementa o loop principal que:
        1. Gera e armazena dados continuamente
        2. Gerencia métricas e monitoramento
        3. Implementa lógica de recuperação de falhas
        4. Mantém estatísticas de operação
        """
        consecutive_failures = 0
        max_consecutive_failures = 3
        base_delay = 1  # Delay base em segundos
        max_delay = 30  # Delay máximo em segundos

        logger.info(f"✅ Starting Data Producer for Pump {self.pump_id}")
        
        while True:
            try:
                # Gera e armazena dados com monitoramento de tempo
                with PUMP_DATA_PROCESSING_TIME.time():
                    data = self.generate_pump_data()
                    success = self.store_data(data)

                if success:
                    # Reseta contadores em caso de sucesso
                    consecutive_failures = 0
                    formatted_data = self.format_data(data)
                    PUMP_OPERATIONS.labels(operation_type='total').inc()
                    logger.info(f"✅ Data stored successfully: {formatted_data}")
                    
                    # Delay padrão entre operações bem-sucedidas
                    time.sleep(base_delay)
                else:
                    # Incrementa falhas e aplica backoff exponencial
                    consecutive_failures += 1
                    delay = min(base_delay * (2 ** consecutive_failures), max_delay)
                    
                    logger.warning(
                        f" ⚠️ Failed to store data. "
                        f"Attempt {consecutive_failures} of {max_consecutive_failures}. "
                        f"Waiting {delay} seconds."
                    )
                    
                    # Verifica se atingiu o limite de falhas consecutivas
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            f" ❌ Maximum number of consecutive failures reached"
                            f"({max_consecutive_failures}). Restarting service..."
                        )
                        # Aqui poderíamos implementar uma lógica de reinicialização
                        # Por enquanto, apenas resetamos o contador
                        consecutive_failures = 0
                    
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"❌ Critical error in the main loop: {str(e)}")
                PUMP_OPERATIONS.labels(operation_type='error').inc()
                
                # Em caso de erro crítico, aguarda um pouco antes de tentar novamente
                time.sleep(5)
                continue

@app.route('/health')
def health():
    """
    Endpoint de verificação de saúde da aplicação.
    Retorna o status do serviço e o identificador da bomba.
    Este endpoint é crucial para monitoramento e verificações
    de disponibilidade do serviço (health checks).
    """
    return {
        'status': 'healthy',
        'pump_id': os.getenv('PUMP_ID', 'unknown')
    }, 200

@app.route('/metrics/summary')
def metrics_summary():
    """
    Endpoint para resumo estatístico das métricas da bomba.
    Fornece uma visão consolidada das últimas métricas coletadas,
    incluindo médias de pressão, temperatura e vibração da última hora,
    além do uso atual de recursos do sistema.
    """
    try:
        conn = psycopg2.connect(**PumpDataProducer().db_config)
        cur = conn.cursor()
        
        # Consulta métricas da última hora
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
    # Configuração inicial dos servidores
    prometheus_port = int(os.getenv('MONITORING_PROMETHEUS_PORT', '8000'))
    flask_port = int(os.getenv('MONITORING_FLASK_PORT', '8080'))
    
    # Inicia servidor Prometheus em thread separada
    start_http_server(prometheus_port)
    logger.info(f"📊 Prometheus server started on port {prometheus_port}")
    
    # Inicia servidor Flask em thread separada
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host='0.0.0.0', 
            port=flask_port, 
            debug=os.getenv('MONITORING_DEBUG', 'false').lower() == 'true'
        ),
        daemon=True  # Garante que a thread termine quando o programa principal terminar
    )
    flask_thread.start()
    logger.info(f"🌐 Flask server started on port {flask_port}")
    
    try:
        # Inicia o produtor
        producer = PumpDataProducer()
        logger.info("🚀 Starting data producer...")
        producer.run()
    except KeyboardInterrupt:
        logger.info("👋 Wrapping up data producer...")
    except Exception as e:
        logger.error(f"❌ Crash when starting producer: {str(e)}")
        raise