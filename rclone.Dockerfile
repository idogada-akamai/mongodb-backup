FROM ~ as download-rclone

ENV RCLONE_VERSION=1.61.1
RUN apk update && \
    apk add wget unzip

WORKDIR /tmp
RUN wget -O rclone.zip https://downloads.rclone.org/v${RCLONE_VERSION}/rclone-v${RCLONE_VERSION}-linux-amd64.zip && \
    unzip rclone.zip && \
    mv rclone-v${RCLONE_VERSION}-linux-amd64/rclone /usr/local/bin

FROM alpine:3.17.2

COPY --from=download-rclone /usr/local/bin/* /usr/local/bin/
WORKDIR /app
COPY rclone.sh .
RUN chmod +x rclone.sh
ENTRYPOINT [ "./rclone.sh" ]
