#!BuildTag: mcp-bugzilla:%VERSION%
#!UseOBSRepositories

FROM registry.opensuse.org/opensuse/bci/python:3.13

RUN zypper --non-interactive in python313-uv 

RUN useradd -m -u 1001 -d /home/bz bz

COPY . /home/bz/app/

RUN chown -R bz:bz /home/bz/app

WORKDIR /home/bz/app

USER 1001

RUN uv sync --locked

ENTRYPOINT ["uv", "run", "mcp-bugzilla"]
