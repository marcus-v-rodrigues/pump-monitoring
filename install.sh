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
kubectl delete pods,deployments,statefulsets,services,pvc,configmaps,secrets --all --force --grace-period=0 --timeout=60s || true

echo "📦 Atualizando repositórios Helm..."
helm repo add timescale https://charts.timescale.com
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

echo "📦 Construindo dependências do chart..."
cd helm/pump-monitoring
helm dependency build
cd ../..

echo "🔐 Instalando Prometheus Operator..."
helm install prometheus prometheus-community/kube-prometheus-stack

echo "⏳ Aguardando CRDs do Prometheus serem instalados..."
while ! kubectl get crds | grep -q "monitoring.coreos.com"; do
   echo "Aguardando CRDs..."
   sleep 5
done

echo "🔐 Gerando certificados SSL..."
chmod +x generate_certs.sh
./generate_certs.sh

echo "🔑 Gerando credenciais..."
chmod +x generate_credentials.sh
./generate_credentials.sh

echo "🏗️ Construindo imagem do produtor..."
docker build -t pump-producer:latest .

# Criar um arquivo de valores temporário com as variáveis de ambiente substituídas
echo "📝 Gerando arquivo de valores com variáveis de ambiente..."

# Antes do envsubst
while IFS='=' read -r key value; do
    # Ignora linhas vazias e comentários
    [[ -z "$key" || $key == \#* ]] && continue
    # Remove espaços e aspas
    value=$(echo "$value" | tr -d '"' | tr -d "'")
    export "$key"="$value"
done < .env

envsubst < helm/pump-monitoring/values.yaml > values-processed.yaml

echo "🚀 Instalando Helm chart..."
helm install pump-monitoring ./helm/pump-monitoring \
  --values values-processed.yaml \
  --wait --timeout 1m

# Limpar arquivo temporário
rm -f values-processed.yaml

echo "📊 Status dos pods:"
kubectl get pods

echo "📊 Status dos serviços:"
kubectl get services

echo "📝 Logs do produtor:"
kubectl logs -l app=pump-producer --tail=20