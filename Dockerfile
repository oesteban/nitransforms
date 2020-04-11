FROM nipreps/nitransforms:base

RUN pip install --no-cache notebook

ARG NB_UID
ARG NB_USER
# Create a shared $HOME directory
ENV USER ${NB_USER}
ENV HOME /home/${NB_USER}

RUN adduser --disabled-password \
    --gecos "Default user" \
    --uid ${NB_UID} \
    ${NB_USER}
WORKDIR ${HOME}

# Install package
# CRITICAL: Make sure python setup.py --version has been run at least once
#           outside the container, with access to the git history.
COPY . /src/nitransforms
RUN pip install --no-cache-dir "/src/nitransforms[all]"

COPY docs/notebooks/* $HOME/

RUN find $HOME -type d -exec chmod go=u {} + && \
    find $HOME -type f -exec chmod go=u {} +

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="nitransforms" \
      org.label-schema.vcs-url="https://github.com/poldracklab/nitransforms" \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0"
