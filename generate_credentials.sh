#!/bin/bash

# Carrega variáveis de ambiente
set -a
source .env
set +a

# Criar diretório k8s-config se não existir
mkdir -p k8s-config

# Usa variáveis do .env para criação de secrets
kubectl create secret generic "${KUBERNETES_CREDENTIALS_SECRET_NAME}" \
    --from-literal="PATRONI_SUPERUSER_PASSWORD=${CREDENTIALS_SUPERUSER_PASSWORD}" \
    --from-literal="PATRONI_REPLICATION_PASSWORD=${CREDENTIALS_REPLICATION_PASSWORD}" \
    --from-literal="PATRONI_ADMIN_PASSWORD=${CREDENTIALS_ADMIN_PASSWORD}" \
    --namespace "${KUBERNETES_NAMESPACE}" \
    --dry-run=client -o yaml > k8s-config/credentials-secret.yaml

# Aplicar o secret no namespace correto
kubectl apply -f k8s-config/credentials-secret.yaml -n "${KUBERNETES_NAMESPACE}"

echo "✅ Credenciais geradas com sucesso no namespace ${KUBERNETES_NAMESPACE}!"

# Log das credenciais geradas (apenas em ambiente de desenvolvimento)
if [ "${ENVIRONMENT_TYPE}" = "development" ]; then
    echo "🔑 Credenciais geradas:"
    echo "Superuser Password: ${CREDENTIALS_SUPERUSER_PASSWORD}"
    echo "Replication Password: ${CREDENTIALS_REPLICATION_PASSWORD}"
    echo "Admin Password: ${CREDENTIALS_ADMIN_PASSWORD}"
fi