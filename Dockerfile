FROM nipreps/nitransforms:base

# Create a shared $HOME directory
RUN useradd -m -s /bin/bash -G users neuro
WORKDIR /home/neuro
ENV HOME="/home/neuro"

# Install package
# CRITICAL: Make sure python setup.py --version has been run at least once
#           outside the container, with access to the git history.
COPY . /src/nitransforms
RUN pip install --no-cache-dir "/src/nitransforms[all]"

RUN find $HOME -type d -exec chmod go=u {} + && \
    find $HOME -type f -exec chmod go=u {} +

WORKDIR /tmp/

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="nitransforms" \
      org.label-schema.vcs-url="https://github.com/poldracklab/nitransforms" \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0"
