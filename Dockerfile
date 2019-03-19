# Copyright 2017-present Open Networking Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# xosproject/chameleon
FROM alpine:3.9.2

# Install base software
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    libressl-dev \
    py-setuptools \
    py2-pip \
    python2-dev \
 && mkdir /chameleon \
 && touch /chameleon/__init__.py \
 && pip freeze > /chameleon/pip_freeze_apk_`date -u +%Y%m%dT%H%M%S`

# Copy over code
COPY . /chameleon/chameleon

# Install modules and build the protos
RUN pip install -r /chameleon/chameleon/requirements.txt \
 && pip freeze > /chameleon/pip_freeze_chameleon_`date -u +%Y%m%dT%H%M%S` \
 && make -C /chameleon/chameleon/protos

# Label image
ARG org_label_schema_version=unknown
ARG org_label_schema_vcs_url=unknown
ARG org_label_schema_vcs_ref=unknown
ARG org_label_schema_build_date=unknown
ARG org_opencord_vcs_commit_date=unknown

LABEL org.label-schema.schema-version=1.0 \
      org.label-schema.name=chameleon \
      org.label-schema.version=$org_label_schema_version \
      org.label-schema.vcs-url=$org_label_schema_vcs_url \
      org.label-schema.vcs-ref=$org_label_schema_vcs_ref \
      org.label-schema.build-date=$org_label_schema_build_date \
      org.opencord.vcs-commit-date=$org_opencord_vcs_commit_date

ENV PYTHONPATH=/chameleon

# Exposing process and default entry point
CMD ["python", "/chameleon/chameleon/main.py"]
