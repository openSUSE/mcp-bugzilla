#!BuildTag: mcp-bugzilla:%VERSION%
#!UseOBSRepositories

FROM registry.opensuse.org/opensuse/bci/python:3.13
COPY . /app
WORKDIR /app
RUN zypper --non-interactive in python313-uv
RUN uv sync --locked
CMD ["uv", "run", "mcp-bugzilla"]
