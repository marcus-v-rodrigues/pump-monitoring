#!/bin/bash

# Load environment variables
set -a
source .env
set +a

echo "🔄 Checking Docker Desktop..."
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please open Docker Desktop on Windows first."
    exit 1
fi

echo "🔄 Setting up Docker for Minikube..."
eval $(minikube docker-env)

echo "🧹 Removing previous Helm releases..."
helm uninstall pump-monitoring || true

echo "🧹 Cleaning up existing resources..."
kubectl delete pods --all --force --grace-period=0 || true
kubectl delete deployments --all || true
kubectl delete statefulsets --all || true
kubectl delete services --all --grace-period=0 || true
kubectl delete pvc --all --grace-period=0 || true
kubectl delete configmaps --all || true
kubectl delete secrets --all || true

echo "⏳ Waiting for complete cleanup..."
kubectl delete pods,deployments,statefulsets,services,pvc,configmaps,secrets --all --force --grace-period=0 --timeout=60s || true

echo "📦 Updating Helm repositories..."
helm repo add timescale https://charts.timescale.com
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

echo "📦 Building chart dependencies..."
cd helm/pump-monitoring
helm dependency build
cd ../..

echo "🔐 Installing Prometheus Operator..."
helm install prometheus prometheus-community/kube-prometheus-stack

echo "⏳ Waiting for Prometheus CRDs to be installed..."
while ! kubectl get crds | grep -q "monitoring.coreos.com"; do
   echo "Waiting for CRDs..."
   sleep 5
done

echo "🔐 Generating SSL certificates..."
chmod +x generate_certs.sh
./generate_certs.sh

echo "🔑 Generating credentials..."
chmod +x generate_credentials.sh
./generate_credentials.sh

echo "🏗️ Building producer image..."
docker build -t pump-producer:latest -f docker/producer/Dockerfile .

echo "🏗️ Building TimescaleDB image..."
docker build -t pump-monitoring-timescaledb:latest -f docker/timescaledb/Dockerfile .

echo "🏗️ Building Grafana image..."
docker build -t pump-monitoring-grafana:latest -f docker/grafana/Dockerfile .

# Create a temporary values file with substituted environment variables
echo "📝 Generating values file with environment variables..."

# Before envsubst
while IFS='=' read -r key value; do
    # Ignore empty lines and comments
    [[ -z "$key" || $key == \#* ]] && continue
    # Remove spaces and quotes
    value=$(echo "$value" | tr -d '"' | tr -d "'")
    export "$key"="$value"
done < .env

envsubst < helm/pump-monitoring/values.yaml > values-processed.yaml

echo "🚀 Installing Helm chart..."
helm install pump-monitoring ./helm/pump-monitoring \
  --values values-processed.yaml \
  --wait --timeout 1m

# Clean up temporary file
rm -f values-processed.yaml

echo "📊 Status of pods:"
kubectl get pods

echo "📊 Status of services:"
kubectl get services

echo "📝 Producer logs:"
kubectl logs -l app=pump-producer --tail=20
