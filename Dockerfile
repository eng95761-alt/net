FROM python:3.11-slim

# Install wget, tar and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates && rm -rf /var/lib/apt/lists/*

# Install wireproxy (userspace WireGuard to SOCKS5 tunnel)
RUN wget -qO /tmp/wireproxy.tar.gz https://github.com/windtf/wireproxy/releases/download/v1.1.3/wireproxy_linux_amd64.tar.gz && \
    tar -xzf /tmp/wireproxy.tar.gz -C /usr/local/bin wireproxy && \
    chmod +x /usr/local/bin/wireproxy && \
    rm /tmp/wireproxy.tar.gz

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and entrypoint
COPY dashboard/ ./dashboard/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV PORT=8000
EXPOSE 8000

CMD ["./entrypoint.sh"]
