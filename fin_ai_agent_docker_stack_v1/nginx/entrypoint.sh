
#!/usr/bin/env sh
set -e
if [ "$ENABLE_MTLS" = "true" ]; then
  export enable_mtls=1
else
  export enable_mtls=0
fi
envsubst '$NGINX_SERVER_NAME $NGINX_SSL_CERT $NGINX_SSL_KEY $NGINX_CA_CERT $enable_mtls' < /etc/nginx/templates/nginx.conf.tpl > /etc/nginx/nginx.conf
exec nginx -g 'daemon off;'
