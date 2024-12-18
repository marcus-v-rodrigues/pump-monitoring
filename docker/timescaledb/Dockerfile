FROM timescale/timescaledb:latest-pg14

# Add labels for better maintenance
LABEL maintainer="Marcus Rodrigues <marcus.v.rodrigues@outlook.com>"
LABEL description="TimescaleDB instance for pump monitoring"
LABEL version="1.0"

# Copy custom configuration files if needed
COPY docker/timescaledb/postgresql.conf /etc/postgresql/postgresql.conf

# Create directory for SSL certificates
RUN mkdir -p /etc/certificate && \
    chown postgres:postgres /etc/certificate

# Add initialization scripts if needed
COPY docker/timescaledb/init-scripts/ /docker-entrypoint-initdb.d/

# Default command is inherited from base image