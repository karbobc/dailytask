FROM --platform=$BUILDPLATFORM python:3.12.3-alpine AS build
WORKDIR /app
COPY ./src ./src
COPY ./pyproject.toml ./pyproject.toml
RUN set -ex \
    && python -m pip install build \
    && python -m build

FROM --platform=$TARGETPLATFORM python:3.12.3-alpine
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FORWARDED_ALLOW_IPS *

WORKDIR /app
COPY --from=build /app/dist /app/dist
COPY entrypoint.sh /

RUN set -ex \
    && python -m pip install --no-cache-dir dist/dailytask-*.whl \
    && rm -rf /app/dist \
    && rm -rf /root/.cache

EXPOSE 7777
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/local/bin/dailytask", "--server"]
