FROM timescale/timescaledb:latest-pg14

# Add labels for better maintenance
LABEL maintainer="Marcus Rodrigues <marcus.v.rodrigues@outlook.com>"
LABEL description="TimescaleDB instance for pump monitoring"
LABEL version="1.0"

# Create directory for SSL certificates
USER root
RUN mkdir -p /etc/certificate && \
    chown postgres:postgres /etc/certificate

# Copy custom configuration files
COPY docker/timescaledb/postgresql.conf /etc/postgresql/postgresql.conf
RUN chown postgres:postgres /etc/postgresql/postgresql.conf

# Add initialization scripts
COPY docker/timescaledb/init-scripts/ /docker-entrypoint-initdb.d/
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d/

USER postgres

# Default command is inherited from base image