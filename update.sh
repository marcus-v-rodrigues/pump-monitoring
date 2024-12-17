#!/bin/bash

echo "🔄 Verificando Docker Desktop..."
if ! docker info &> /dev/null; then
    echo "❌ Docker não está rodando. Abra o Docker Desktop no Windows primeiro."
    exit 1
fi

echo "🔄 Configurando Docker para Minikube..."
eval $(minikube docker-env)

echo "🏗️ Construindo nova imagem do produtor..."
docker build -t pump-producer:latest .

echo "🔄 Reiniciando pods do produtor..."
kubectl rollout restart deployment pump-monitoring-producer

echo "⏳ Aguardando pods reiniciarem..."
kubectl rollout status deployment pump-monitoring-producer

echo "📝 Logs do produtor:"
kubectl logs -l app=pump-producer --tail=20 -f