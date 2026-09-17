#!/bin/sh
set -e

# collectstatic безопасно гонять на каждом старте (идемпотентно, быстро
# на несмёнённых файлах). Миграции — НЕ отсюда: при нескольких репликах
# backend параллельный `migrate` на старте гоняет риск гонки схемы;
# накатывайте их явно: docker compose -f docker-compose.prod.yml exec backend python manage.py migrate
python manage.py collectstatic --noinput

exec "$@"
