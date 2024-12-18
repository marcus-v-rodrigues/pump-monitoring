FROM grafana/grafana:latest

# Add labels for better maintenance
LABEL maintainer="Marcus Rodrigues <marcus.v.rodrigues@outlook.com>"
LABEL description="Grafana instance for pump monitoring visualization"
LABEL version="1.0"

# Environment variables for configuration
ENV GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD} \
    GF_AUTH_ANONYMOUS_ENABLED=false

# Create directory for SSL certificates
USER root
RUN mkdir -p /etc/grafana/ssl && \
    chown grafana:grafana /etc/grafana/ssl
USER grafana

# Copy custom configuration files
COPY docker/grafana/grafana.ini /etc/grafana/grafana.ini
COPY docker/grafana/dashboards /etc/grafana/dashboards
COPY docker/grafana/datasources /etc/grafana/provisioning/datasources

# Default command is inherited from base image