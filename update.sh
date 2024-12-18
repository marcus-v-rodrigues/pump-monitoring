#!/bin/bash

echo "🔄 Checking Docker Desktop..."
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please open Docker Desktop on Windows first."
    exit 1
fi

echo "🔄 Setting up Docker for Minikube..."
eval $(minikube docker-env)

echo "🏗️ Building producer image..."
docker build -t pump-producer:latest -f docker/producer/Dockerfile .

echo "🏗️ Building TimescaleDB image..."
docker build -t pump-monitoring-timescaledb:latest -f docker/timescaledb/Dockerfile .

echo "🏗️ Building Grafana image..."
docker build -t pump-monitoring-grafana:latest -f docker/grafana/Dockerfile .

echo "🔄 Restarting producer pods..."
kubectl rollout restart deployment pump-monitoring-producer

echo "⏳ Waiting for pods to restart..."
kubectl rollout status deployment pump-monitoring-producer

echo "📝 Producer logs:"
kubectl logs -l app=pump-producer --tail=20 -f
