#!/bin/bash

# Carrega variáveis de ambiente
set -a
source .env
set +a

echo "🔄 Verificando Docker Desktop..."
if ! docker info &> /dev/null; then
    echo "❌ Docker não está rodando. Abra o Docker Desktop no Windows primeiro."
    exit 1
fi

echo "🔄 Configurando Docker para Minikube..."
eval $(minikube docker-env)

echo "🧹 Removendo releases Helm anteriores..."
helm uninstall pump-monitoring || true

echo "🧹 Limpando recursos existentes..."
kubectl delete pods --all --force --grace-period=0 || true
kubectl delete deployments --all || true
kubectl delete statefulsets --all || true
kubectl delete services --all --grace-period=0 || true
kubectl delete pvc --all --grace-period=0 || true
kubectl delete configmaps --all || true
kubectl delete secrets --all || true

echo "⏳ Aguardando limpeza completa..."
while kubectl get pods 2>/dev/null | grep -q .; do
    echo "Aguardando pods serem removidos..."
    sleep 2
done

echo "🔐 Gerando certificados SSL..."
chmod +x generate_certs.sh
./generate_certs.sh

echo "🔑 Gerando credenciais..."
chmod +x generate_credentials.sh
./generate_credentials.sh

echo "🏗️ Construindo imagem do produtor..."
docker build -t pump-producer:latest .

echo "📦 Atualizando repositórios Helm..."
helm repo add timescale https://charts.timescale.com
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Criar um arquivo de valores temporário com as variáveis de ambiente substituídas
echo "📝 Gerando arquivo de valores com variáveis de ambiente..."
envsubst < helm/pump-monitoring/values.yaml > values-processed.yaml

echo "🚀 Instalando Helm chart..."
helm install pump-monitoring ./helm/pump-monitoring \
  --values values-processed.yaml \
  --set producer.replicaCount="${PUMP_REPLICA_COUNT:-2}" \
  --set producer.resources.limits.cpu="${PRODUCER_CPU_LIMIT:-200m}" \
  --set producer.resources.limits.memory="${PRODUCER_MEMORY_LIMIT:-256Mi}" \
  --set producer.resources.requests.cpu="${PRODUCER_CPU_REQUEST:-100m}" \
  --set producer.resources.requests.memory="${PRODUCER_MEMORY_REQUEST:-128Mi}" \
  --set timescaledb-single.patroni.postgresql.parameters.max_connections="${TIMESCALEDB_CONNECTIONS_MAX:-100}" \
  --set timescaledb-single.patroni.postgresql.parameters.shared_buffers="${TIMESCALEDB_SHARED_BUFFERS:-128MB}" \
  --set timescaledb-single.persistence.size="${TIMESCALEDB_PERSISTENCE_SIZE:-1Gi}" \
  --set timescaledb-single.resources.limits.memory="${TIMESCALEDB_MEMORY_LIMIT:-512Mi}" \
  --set timescaledb-single.resources.limits.cpu="${TIMESCALEDB_CPU_LIMIT:-500m}" \
  --set timescaledb-single.resources.requests.memory="${TIMESCALEDB_MEMORY_REQUEST:-256Mi}" \
  --set timescaledb-single.resources.requests.cpu="${TIMESCALEDB_CPU_REQUEST:-250m}" \
  --set grafana.adminPassword="${GRAFANA_ADMIN_PASSWORD:-admin}" \
  --set grafana.persistence.size="${GRAFANA_PERSISTENCE_SIZE:-1Gi}" \
  --wait --timeout 10m

# Limpar arquivo temporário
rm -f values-processed.yaml

kubectl apply -f helm/pump-monitoring/templates/grafana-dashboards-configmap.yaml

echo "📊 Status dos pods:"
kubectl get pods

echo "📊 Status dos serviços:"
kubectl get services

echo "📝 Logs do produtor:"
kubectl logs -l app=pump-producer --tail=20