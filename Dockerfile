# Use the official Python image from the Python Docker Hub repository as the base image
FROM python:3.12-slim-bullseye

# Set the working directory to /app in the container
WORKDIR /app

# Create a non-root user named 'myuser' with a home directory

# Copy the requirements.txt file to the container to install Python dependencies
COPY requirements.txt ./

# Install the Python packages specified in requirements.txt
RUN useradd -m myuser && pip install --no-cache-dir -r requirements.txt && \
    mkdir logs qr_codes && chown myuser:myuser logs qr_codes
# Before copying the application code, create the logs and qr_codes directories
# and ensure they are owned by the non-root user

# Copy the rest of the application's source code into the container, setting ownership to 'myuser'
COPY --chown=myuser:myuser ./app .
    
# Switch to the 'myuser' user to run the application
USER myuser

# Use the Python interpreter as the entrypoint and the script as the first argument
# This allows additional command-line arguments to be passed to the script via the docker run command
ENTRYPOINT ["python", "/app/main.py"]
# this sets a default argument, its also set in the program but this just illustrates how to use cmd and override it from the terminal
CMD ["--url","http://github.com/mihirkadam19"]