#!/bin/bash

# Carrega variáveis de ambiente
set -a
source .env
set +a

# Criar diretório k8s-config se não existir
mkdir -p k8s-config

# Usa variáveis do .env para criação de secrets
kubectl create secret generic "${KUBERNETES__CREDENTIALS_SECRET_NAME}" \
    --from-literal="PATRONI_SUPERUSER_PASSWORD=${CREDENTIALS__SUPERUSER_PASSWORD}" \
    --from-literal="PATRONI_REPLICATION_PASSWORD=${CREDENTIALS__REPLICATION_PASSWORD}" \
    --from-literal="PATRONI_ADMIN_PASSWORD=${CREDENTIALS__ADMIN_PASSWORD}" \
    --namespace "${KUBERNETES__NAMESPACE}" \
    --dry-run=client -o yaml > k8s-config/credentials-secret.yaml

# Aplicar o secret no namespace correto
kubectl apply -f k8s-config/credentials-secret.yaml -n "${KUBERNETES__NAMESPACE}"

echo "✅ Credenciais geradas com sucesso no namespace ${KUBERNETES__NAMESPACE}!"

# Log das credenciais geradas (apenas em ambiente de desenvolvimento)
if [ "${ENVIRONMENT__TYPE}" = "development" ]; then
    echo "🔑 Credenciais geradas:"
    echo "Superuser Password: ${CREDENTIALS__SUPERUSER_PASSWORD}"
    echo "Replication Password: ${CREDENTIALS__REPLICATION_PASSWORD}"
    echo "Admin Password: ${CREDENTIALS__ADMIN_PASSWORD}"
fi