FROM grafana/grafana:latest

# Add labels for better maintenance
LABEL maintainer="Marcus Rodrigues <marcus.v.rodrigues@outlook.com>"
LABEL description="Grafana instance for pump monitoring visualization"
LABEL version="1.0"

# Create directory for SSL certificates with correct permissions
USER root
RUN mkdir -p /etc/grafana/ssl && \
    chown grafana:root /etc/grafana/ssl && \
    chmod 775 /etc/grafana/ssl

# Copy custom configuration files
COPY docker/grafana/grafana.ini /etc/grafana/grafana.ini
COPY docker/grafana/dashboards /etc/grafana/dashboards
COPY docker/grafana/datasources /etc/grafana/provisioning/datasources

# Switch back to grafana user
USER grafana

# Environment variables for configuration (using ARG instead of ENV for build-time only)
ARG GF_SECURITY_ADMIN_PASSWORD=admin
ARG GF_AUTH_ANONYMOUS_ENABLED=false

# Default command is inherited from base image