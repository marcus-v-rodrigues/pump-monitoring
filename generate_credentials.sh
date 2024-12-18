#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# Create k8s-config directory if it doesn't exist
mkdir -p k8s-config

# Use variables from .env to create secrets
kubectl create secret generic "${KUBERNETES_CREDENTIALS_SECRET_NAME}" \
    --from-literal="PATRONI_SUPERUSER_PASSWORD=${CREDENTIALS_SUPERUSER_PASSWORD}" \
    --from-literal="PATRONI_REPLICATION_PASSWORD=${CREDENTIALS_REPLICATION_PASSWORD}" \
    --from-literal="PATRONI_ADMIN_PASSWORD=${CREDENTIALS_ADMIN_PASSWORD}" \
    --namespace "${KUBERNETES_NAMESPACE}" \
    --dry-run=client -o yaml > k8s-config/credentials-secret.yaml

# Apply the secret to the correct namespace
kubectl apply -f k8s-config/credentials-secret.yaml -n "${KUBERNETES_NAMESPACE}"

echo "✅ Credentials successfully generated in namespace ${KUBERNETES_NAMESPACE}!"

# Log the generated credentials (only in development environment)
if [ "${ENVIRONMENT_TYPE}" = "development" ]; then
    echo "🔑 Generated credentials:"
    echo "Superuser Password: ${CREDENTIALS_SUPERUSER_PASSWORD}"
    echo "Replication Password: ${CREDENTIALS_REPLICATION_PASSWORD}"
    echo "Admin Password: ${CREDENTIALS_ADMIN_PASSWORD}"
fi
