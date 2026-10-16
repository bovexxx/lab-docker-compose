# Frontend — статический веб-интерфейс на nginx
FROM nginx:1.27-alpine

# Убираем дефолтную страницу и ставим свою конфигурацию
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Копируем статику
COPY index.html /usr/share/nginx/html/index.html
COPY style.css  /usr/share/nginx/html/style.css
COPY app.js     /usr/share/nginx/html/app.js

EXPOSE 80
