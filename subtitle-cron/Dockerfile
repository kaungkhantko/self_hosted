FROM python:3.12-alpine

# Install subliminal and its dependencies
RUN pip install --no-cache-dir subliminal

# Copy subtitle downloader script
COPY download_subs.py /app/download_subs.py

# Set up crontab: run daily at 03:00, log to stdout (PID 1 fd)
RUN echo "0 3 * * * python /app/download_subs.py /mnt/media/TV /mnt/media/Movies >> /proc/1/fd/1 2>&1" \
    | crontab -

# busybox crond: -f foreground, -d 8 debug level (warnings + errors only)
CMD ["crond", "-f", "-d", "8"]
