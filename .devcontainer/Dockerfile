# WindowsのDocker Desktop上でも同じ開発ツールを使うための最小イメージ。
# Node.jsは`.node-version`と同じ版の公式イメージから複写する（ADR 0030）。
ARG NODE_VERSION=22.11.0
FROM node:${NODE_VERSION}-bookworm-slim AS node

FROM python:3.12-slim-bookworm

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

# sudoは作業ツリーの所有者をそろえる専用Scriptの実行だけに使う（ADR 0016）。
COPY --chown=root:root --chmod=0755 .devcontainer/fix-workspace-owner.sh /usr/local/bin/fix-workspace-owner

# web/のHTMLを実物のまま検査するNode.jsとnpm（ADR 0030）。
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version \
    && npm --version

RUN apt-get update \
    && apt-get install --no-install-recommends --yes git sudo \
    && groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" --create-home "${USERNAME}" \
    && install --directory --owner="${USERNAME}" --group="${USERNAME}" \
        "/home/${USERNAME}/.vscode-server" \
        "/home/${USERNAME}/.vscode-server/bin" \
        "/home/${USERNAME}/.vscode-server/extensions" \
    && printf '%s ALL=(root) NOPASSWD: /usr/local/bin/fix-workspace-owner ""\n' "${USERNAME}" \
        > /etc/sudoers.d/fix-workspace-owner \
    && chmod 0440 /etc/sudoers.d/fix-workspace-owner \
    && visudo --check --file=/etc/sudoers.d/fix-workspace-owner \
    && rm -rf /var/lib/apt/lists/*

USER vscode
