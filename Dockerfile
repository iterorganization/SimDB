FROM python:3.7
COPY ./ /tmp/simdb/
RUN cd /tmp/simdb/ && \
    pip3 install . && \
    pip3 install flask flask_caching flask_cors flask_restx gunicorn psycopg2-binary && \
    rm -rf /tmp/simdb

ENTRYPOINT ["gunicorn", "--bind=0.0.0.0:5000", "--workers=1", "simdb.remote.wsgi:app"]
EXPOSE 5000
