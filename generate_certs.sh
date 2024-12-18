#!/bin/bash

# Carrega variáveis de ambiente
set -a
source .env
set +a

# Configurações
NAMESPACE="${KUBERNETES_NAMESPACE:-default}"
SERVICE_NAME="pump-monitoring-timescaledb"
SECRET_NAME="${KUBERNETES_CERTIFICATE_SECRET_NAME:-pump-monitoring-certificate}"

# Criar diretório para certificados
mkdir -p certs
cd certs

# Gerar chave privada da CA
openssl genrsa -out ca.key 4096

# Gerar certificado CA auto-assinado
openssl req -x509 -new -nodes -key ca.key -days 365 -out ca.crt \
    -subj "/CN=TimescaleDB-CA"

# Gerar chave privada do servidor
openssl genrsa -out server.key 2048

# Configurar permissões da chave
chmod 600 server.key

# Gerar CSR (Certificate Signing Request)
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

# Assinar o certificado do servidor com a CA
openssl x509 -req -in server.csr \
    -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 365 \
    -extensions v3_req -extfile server.conf

# Criar diretório k8s-config se não existir
mkdir -p ../k8s-config

# Criar Secret no Kubernetes
kubectl create secret generic ${SECRET_NAME} \
    --from-file=tls.crt=server.crt \
    --from-file=tls.key=server.key \
    --from-file=ca.crt=ca.crt \
    --dry-run=client -o yaml > ../k8s-config/certificates-secret.yaml

# Aplicar o secret no namespace correto
kubectl apply -f ../k8s-config/certificates-secret.yaml -n ${NAMESPACE}

echo "✅ Certificados gerados com sucesso no namespace ${NAMESPACE}!"