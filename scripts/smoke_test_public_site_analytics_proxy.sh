#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
docker=(env -u DOCKER_HOST -u DOCKER_CONTEXT docker --host unix:///var/run/docker.sock)

"${docker[@]}" run --rm -i --pull=never --network none --add-host backend:127.0.0.1 \
  --user nginx --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$root/frontend/docker/nginx.conf,target=/docker.conf,readonly" \
  --mount "type=bind,source=$root/frontend/docker/nginx.staging.conf,target=/staging.conf,readonly" \
  --mount "type=bind,source=$root/ops/vps/nginx/clinic.conf.template,target=/vps.conf,readonly" \
  --entrypoint /bin/sh nginx:1.27-alpine -s <<'PROBE'
set -eu
fixture=/tmp/analytics-proxy
mkdir "$fixture"
pid=

stop_proxy() {
    if [ -n "$pid" ]; then
        kill -QUIT "$pid" 2>/dev/null || :
        wait "$pid" || :
        pid=
    fi
}
trap stop_proxy EXIT
trap 'exit 1' HUP INT TERM

cat > "$fixture/nginx.conf" <<'NGINX'
worker_processes 1;
pid /tmp/analytics-proxy/nginx.pid;
error_log /tmp/analytics-proxy/error.log;
events {}
http {
    access_log /tmp/analytics-proxy/access-primary.log combined;
    access_log /tmp/analytics-proxy/access-secondary.log combined;
    client_body_temp_path /tmp/analytics-proxy/client_temp;
    proxy_temp_path /tmp/analytics-proxy/proxy_temp;
    fastcgi_temp_path /tmp/analytics-proxy/fastcgi_temp;
    uwsgi_temp_path /tmp/analytics-proxy/uwsgi_temp;
    scgi_temp_path /tmp/analytics-proxy/scgi_temp;
    include /tmp/analytics-proxy/site.conf;

    server {
        listen 127.0.0.1:8000;
        listen 127.0.0.1:18000;
        access_log off;
        location / {
            return 200 "$request_method|$request_uri|$http_host|$http_x_real_ip|$http_x_forwarded_for|$http_x_forwarded_proto|$http_content_length|$server_protocol";
        }
    }
}
NGINX

collector=/api/v1/public-site/analytics/events
encoded=/api/v1/public-site/analytics/%65vents
host=analytics-probe.invalid
forwarded=192.0.2.10
failed=0

probe_post() {
    target=$1
    if ! response=$(wget -q -T 5 -O - --header="Host: $host" \
        --header="X-Forwarded-For: $forwarded" --post-data=site_view "http://127.0.0.1$target"); then
        echo "FAIL $variant: synthetic proxy request failed" >&2
        exit 1
    fi
    if [ "$response" != "POST|$target|$host|127.0.0.1|$expected_forwarded|http|9|$protocol" ]; then
        echo "FAIL $variant: synthetic response did not preserve the upstream request" >&2
        exit 1
    fi
}

for variant in docker staging vps; do
    expected_forwarded="$forwarded, 127.0.0.1"
    protocol=HTTP/1.1
    case "$variant" in
        docker) protocol=HTTP/1.0 ;;
        vps) expected_forwarded=127.0.0.1 ;;
    esac
    sed -e "s|__APP_HOST__|$host|g" -e 's|__APP_ROOT__|/tmp/analytics-proxy|g' \
        "/$variant.conf" > "$fixture/site.conf"
    if ! nginx -t -p "$fixture/" -c "$fixture/nginx.conf" > /dev/null 2>&1; then
        echo "FAIL $variant: Nginx config check failed" >&2
        exit 1
    fi
    : > "$fixture/access-primary.log"
    : > "$fixture/access-secondary.log"
    nginx -p "$fixture/" -c "$fixture/nginx.conf" -g 'daemon off;' > /dev/null 2>&1 &
    pid=$!
    for attempt in 1 2 3 4 5; do
        if wget -q -T 1 -O /dev/null http://127.0.0.1:18000/ready 2>/dev/null; then break; fi
        if [ "$attempt" = 5 ]; then
            echo "FAIL $variant: synthetic upstream did not start" >&2
            exit 1
        fi
        sleep 1
    done

    probe_post "$collector?check=collector-canary"
    probe_post "$collector/?check=collector-canary"
    probe_post "$encoded?check=collector-canary"
    probe_post "$collector-extra?check=neighbor-canary"
    probe_post "$collector/info?check=nested-canary"
    probe_post '/api/v1/health?check=health-canary'
    stop_proxy

    logged=0
    for sink in primary secondary; do
        log="$fixture/access-$sink.log"
        for control in neighbor nested health; do
            if ! grep -Fq "check=$control-canary" "$log"; then
                echo "FAIL $variant: missing $control access-log control" >&2
                exit 1
            fi
        done
        logged=$((logged + $(grep -Fc 'check=collector-canary' "$log" || :)))
    done
    if [ "$logged" -eq 0 ]; then
        echo "PASS $variant: forwarding intact, controls present and collector absent in both sinks"
    else
        echo "FAIL $variant: $logged collector entries across both access-log sinks" >&2
        failed=1
    fi
done
exit "$failed"
PROBE
