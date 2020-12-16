FROM tiangolo/uwsgi-nginx-flask:python3.7
RUN echo "uwsgi_read_timeout 300s;" > /etc/nginx/conf.d/custom_timeout.conf
COPY ./requirements.txt /var/www/requirements.txt
RUN pip3 install --upgrade pip
RUN pip3 install -r /var/www/requirements.txt

