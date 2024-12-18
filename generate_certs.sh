#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# Configurations
NAMESPACE="${KUBERNETES_NAMESPACE:-default}"
SERVICE_NAME="pump-monitoring-timescaledb"
SECRET_NAME="${KUBERNETES_CERTIFICATE_SECRET_NAME:-pump-monitoring-certificate}"

# Create directory for certificates
mkdir -p certs
cd certs

# Generate CA private key
openssl genrsa -out ca.key 4096

# Generate self-signed CA certificate
openssl req -x509 -new -nodes -key ca.key -days 365 -out ca.crt \
    -subj "/CN=TimescaleDB-CA"

# Generate server private key
openssl genrsa -out server.key 2048

# Set key permissions
chmod 600 server.key

# Generate CSR (Certificate Signing Request)
cat > server.conf << EOF
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name

[req_distinguished_name]

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${SERVICE_NAME}
DNS.2 = ${SERVICE_NAME}.${NAMESPACE}
DNS.3 = ${SERVICE_NAME}.${NAMESPACE}.svc
DNS.4 = ${SERVICE_NAME}.${NAMESPACE}.svc.cluster.local
DNS.5 = localhost
IP.1 = 127.0.0.1
EOF

openssl req -new -key server.key -out server.csr \
    -subj "/CN=${SERVICE_NAME}" -config server.conf

# Sign the server certificate with the CA
openssl x509 -req -in server.csr \
    -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 365 \
    -extensions v3_req -extfile server.conf

# Create k8s-config directory if it doesn't exist
mkdir -p ../k8s-config

# Create Secret in Kubernetes
kubectl create secret generic ${SECRET_NAME} \
    --from-file=tls.crt=server.crt \
    --from-file=tls.key=server.key \
    --from-file=ca.crt=ca.crt \
    --dry-run=client -o yaml > ../k8s-config/certificates-secret.yaml

# Apply the secret to the correct namespace
kubectl apply -f ../k8s-config/certificates-secret.yaml -n ${NAMESPACE}

echo "✅ Certificates successfully generated in namespace ${NAMESPACE}!"
