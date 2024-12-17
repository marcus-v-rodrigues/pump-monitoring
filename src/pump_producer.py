import time
import random
import psycopg2
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
from flask import Flask
from prometheus_client import start_http_server, Gauge

# Configuração do logging
log_format = os.getenv('LOGGING__FORMAT', 'json')
log_level = os.getenv('LOGGING__LEVEL', 'INFO')

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
PUMP_METRICS = Gauge('pump_metrics', 'Métricas da bomba', ['metric_type'])
load_dotenv()

class PumpDataProducer:
    def __init__(self):
        self.db_config = {
            'dbname': os.getenv('DATABASE__NAME', 'postgres'),
            'user': os.getenv('DATABASE__USER', 'postgres'),
            'password': os.getenv('DATABASE__PASSWORD', 'postgres'),
            'host': os.getenv('DATABASE__HOST', 'pump-monitoring-timescaledb'),
            'port': os.getenv('DATABASE__PORT', '5432')
        }
        self.pump_id = os.getenv('PUMP__ID', 'pump1')
        self.max_retries = 5
        self.retry_delay = 5
        self.retention_days = int(os.getenv('DATA__RETENTION_DAYS', '30'))
        self.debug = os.getenv('MONITORING__DEBUG', 'false').lower() == 'true'
        self.setup_database()

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
                return
                
            except psycopg2.Error as e:
                last_error = e
                retry_count += 1
                logger.error(f"Tentativa {retry_count} falhou: {e}")
                if retry_count < self.max_retries:
                    logger.info(f"Tentando novamente em {self.retry_delay} segundos...")
                    time.sleep(self.retry_delay)
                continue
                
            except Exception as e:
                logger.error(f"Erro inesperado ao configurar banco de dados: {e}")
                raise

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

    def generate_pump_data(self):
        """Gera dados simulados da bomba."""
        return {
            'pressure': random.uniform(2.0, 4.0),
            'flow_rate': random.uniform(100, 200),
            'temperature': random.uniform(35, 45),
            'vibration': abs(np.random.normal(0.5, 0.1)),
            'power_consumption': random.uniform(75, 85)
        }

    def store_data(self, data):
        """Armazena os dados no TimescaleDB com tratamento de erros."""
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

                # Atualizar métricas Prometheus
                for key, value in data.items():
                    PUMP_METRICS.labels(metric_type=key).set(value)

                return True

            except psycopg2.Error as e:
                retry_count += 1
                logger.error(f"Tentativa {retry_count} falhou ao armazenar dados: {e}")
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                continue
                
            except Exception as e:
                logger.error(f"Erro inesperado ao armazenar dados: {e}")
                return False

        logger.error(f"❌ Falha ao armazenar dados após {self.max_retries} tentativas")
        return False

    def run(self):
        """Loop principal do produtor."""
        while True:
            try:
                data = self.generate_pump_data()
                if self.store_data(data):
                    formatted_data = self.format_data(data)
                    logger.info(f"✅ Dados armazenados com sucesso: {formatted_data}")
                time.sleep(1)
            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")
                time.sleep(5)

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

if __name__ == "__main__":
    # Iniciar servidor Prometheus metrics
    prometheus_port = int(os.getenv('MONITORING__PROMETHEUS_PORT', '8000'))
    flask_port = int(os.getenv('MONITORING__FLASK_PORT', '8080'))
    
    start_http_server(prometheus_port)
    logger.info(f"Servidor Prometheus iniciado na porta {prometheus_port}")
    
    # Iniciar servidor Flask em uma thread separada
    import threading
    threading.Thread(target=lambda: app.run(
        host='0.0.0.0', 
        port=flask_port, 
        debug=os.getenv('MONITORING__DEBUG', 'false').lower() == 'true'
    )).start()
    logger.info(f"Servidor Flask iniciado na porta {flask_port}")
    
    # Iniciar produtor
    producer = PumpDataProducer()
    producer.run()