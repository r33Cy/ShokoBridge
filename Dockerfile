# Define Python version as an ARG to be used in both stages for easier updates.
ARG PYTHON_VERSION=3.13.7
ARG PYTHON_MAJOR_MINOR_VERSION=3.13

# ---- Builder Stage ----
# This stage installs dependencies using pipenv for reproducible builds
FROM python:${PYTHON_VERSION}-alpine AS builder

# Install pipenv
RUN pip install pipenv

# Set the working directory in the container
WORKDIR /app

# Copy dependency definition files
COPY Pipfile Pipfile.lock ./

# Install dependencies into the system python, not a virtualenv.
# --deploy checks that Pipfile.lock is up-to-date and fails if not.
# --system installs to the system site-packages.
RUN pipenv install --system --deploy --ignore-pipfile


# ---- Final Stage ----
# This stage creates the final, lean image
FROM python:${PYTHON_VERSION}-alpine

# Re-declare ARGs so they are available in this stage.
ARG PYTHON_VERSION
ARG PYTHON_MAJOR_MINOR_VERSION

# Create a non-root user and group for security.
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Set working directory
WORKDIR /app

# Copy the installed dependencies from the builder stage
# Using an ARG makes this path robust against future Python version changes.
COPY --from=builder /usr/local/lib/python${PYTHON_MAJOR_MINOR_VERSION}/site-packages /usr/local/lib/python${PYTHON_MAJOR_MINOR_VERSION}/site-packages

# Copy only the necessary application code from the build context
# This avoids copying dev files, git history, etc. into the final image
COPY shokobridge/ ./shokobridge/
COPY ShokoBridge.py .

# Change ownership of the app files to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user. The application will run as this user by default.
# The mounted /app/data volume will need to have permissions set correctly on the host
# for this user to write to it, which is what the PUID/PGID variables in docker-compose are for.
USER appuser

# Set the entrypoint to run the script
ENTRYPOINT ["python", "ShokoBridge.py"]