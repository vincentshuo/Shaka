FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pydantic==2.14.1 Pillow==12.3.0 \
    numpy==2.5.4 scipy==1.18.1 mypy==2.4.0
# The existing isolated worker binds a self-contained Python prefix under /root
# or /home. Keep the interpreter and its libraries together in that prefix.
RUN cp -a /usr/local /root/python && chmod 755 /root
ENV PATH="/root/python/bin:${PATH}"
USER 1000:1000
