FROM nipreps/nitransforms:base

RUN pip install --no-cache notebook
RUN pip install --no-cache git+https://github.com/poldracklab/niworkflows.git@master

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
COPY docs/_static/* $HOME/_static/
COPY docs/notebooks/*.ipynb $HOME/
ENV NT_TEST_DATA=$HOME/data

# Install package
# CRITICAL: Make sure python setup.py --version has been run at least once
#           outside the container, with access to the git history.
COPY . /src/nitransforms
RUN pip install --no-cache-dir "/src/nitransforms[all]"

RUN curl -sSL "https://files.osf.io/v1/resources/fvuh8/providers/osfstorage/5e7d5b65c3f8d300bafa05e0/?zip=" -o data.zip && \
    python -c "from pathlib import Path; import zipfile as z; zr = z.ZipFile('data.zip', 'r'); zr.extractall(str(Path.home() / 'data'))" && \
    rm data.zip

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
