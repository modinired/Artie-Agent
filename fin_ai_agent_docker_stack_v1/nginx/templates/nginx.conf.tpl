
worker_processes auto;
events { worker_connections 1024; }

http {
  include       /etc/nginx/mime.types;
  default_type  application/octet-stream;
  sendfile      on;
  keepalive_timeout  65;

  map $http_x_forwarded_proto $origin_proto {
    default $scheme;
  }

  server {
    listen 443 ssl;
    server_name ${NGINX_SERVER_NAME};

    ssl_certificate     ${NGINX_SSL_CERT};
    ssl_certificate_key ${NGINX_SSL_KEY};

    # Optional mTLS
    # Controlled by env ENABLE_MTLS=true/false via envsubst + template mount
    if ($enable_mtls) {
        ssl_client_certificate ${NGINX_CA_CERT};
        ssl_verify_client on;
    }

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    location / {
      proxy_pass http://hub:8010;
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $origin_proto;
    }
  }
}
