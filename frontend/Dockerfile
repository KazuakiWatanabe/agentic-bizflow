FROM nginx:alpine

RUN apk add --no-cache gettext

COPY public/ /usr/share/nginx/html/
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template

ENV PORT=8080
ENV LIFF_ID=""
ENV BACKEND_BASE_URL=""

EXPOSE 8080

CMD ["/bin/sh", "-c", "export PORT=${PORT:-8080}; envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && envsubst '$LIFF_ID $BACKEND_BASE_URL' < /usr/share/nginx/html/config.js.template > /usr/share/nginx/html/config.js && nginx -g 'daemon off;'"]
