#!/usr/bin/env bash
set -euo pipefail

# Одноразовый скрипт: выпускает (или переиспускает) TLS-сертификат
# Let's Encrypt для DOMAIN из .env.prod и заводит весь прод-стек.
# Дальнейшее автопродление делает сервис `certbot` в docker-compose.prod.yml
# (он крутится постоянно и раз в 12ч гоняет `certbot renew`) — этот скрипт
# запускать повторно не нужно, только если сертификат совсем потерялся.
#
# Предварительно: DNS-запись DOMAIN уже указывает на этот сервер,
# порт 80 открыт снаружи (certbot проверяет владение доменом по HTTP).
#
# Схема (стандартная для nginx+certbot в Docker, не самодельная):
# 1) кладём временный self-signed сертификат, чтобы nginx вообще смог
#    стартовать с 443-портом в конфиге (без файла сертификата nginx
#    не запустится, а без запущенного nginx certbot не может пройти
#    HTTP-проверку — тут разрываем этот замкнутый круг);
# 2) поднимаем nginx с этим временным сертификатом;
# 3) удаляем временный, запрашиваем настоящий у Let's Encrypt через
#    тот же nginx (webroot-режим);
# 4) перезапускаем nginx — теперь уже с настоящим сертификатом.

cd "$(dirname "$0")"

if [ ! -f .env.prod ]; then
  echo "Не найден .env.prod — сначала: cp .env.prod.example .env.prod && заполните" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env.prod
set +a

if [ -z "${DOMAIN:-}" ]; then
  echo "В .env.prod не задан DOMAIN" >&2
  exit 1
fi

COMPOSE=(docker compose -p searchvakancy-prod -f docker-compose.prod.yml --env-file .env.prod)
RSA_KEY_SIZE=4096
DATA_PATH="./certbot"

if [ -d "$DATA_PATH/conf/live/$DOMAIN" ]; then
  read -rp "Для $DOMAIN уже есть сертификат в $DATA_PATH. Перевыпустить с нуля? (y/N) " decision
  if [[ ! "$decision" =~ ^[Yy]$ ]]; then
    echo "Отменено."
    exit 0
  fi
  rm -rf "${DATA_PATH:?}/conf/live/$DOMAIN" "$DATA_PATH/conf/archive/$DOMAIN" "$DATA_PATH/conf/renewal/$DOMAIN.conf"
fi

echo "### 1/4 Создаю временный self-signed сертификат для $DOMAIN..."
mkdir -p "$DATA_PATH/conf"
mkdir -p "$DATA_PATH/conf/live/$DOMAIN"
"${COMPOSE[@]}" run --rm --entrypoint sh certbot -c "
  openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
    -keyout '/etc/letsencrypt/live/$DOMAIN/privkey.pem' \
    -out '/etc/letsencrypt/live/$DOMAIN/fullchain.pem' \
    -subj '/CN=localhost'
"

echo "### 2/4 Поднимаю db/redis/backend/frontend (nginx стартует с временным сертификатом)..."
"${COMPOSE[@]}" up -d db redis backend frontend

echo "### 3/4 Удаляю временный сертификат и запрашиваю настоящий..."
"${COMPOSE[@]}" run --rm --entrypoint sh certbot -c "
  rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf
"

EMAIL_ARG="--register-unsafely-without-email"
if [ -n "${LETSENCRYPT_EMAIL:-}" ]; then
  EMAIL_ARG="--email $LETSENCRYPT_EMAIL --no-eff-email"
fi

"${COMPOSE[@]}" run --rm --entrypoint sh certbot -c "
  certbot certonly --webroot -w /var/www/certbot \
    $EMAIL_ARG \
    -d $DOMAIN \
    --rsa-key-size $RSA_KEY_SIZE \
    --agree-tos \
    --non-interactive \
    --force-renewal
"

echo "### 4/4 Перезапускаю nginx с настоящим сертификатом и поднимаю остальной стек..."
"${COMPOSE[@]}" exec frontend nginx -s reload
"${COMPOSE[@]}" up -d

echo
echo "Готово: https://$DOMAIN должен быть доступен."
echo "Проверить: curl -I https://$DOMAIN/api/jobs/"
