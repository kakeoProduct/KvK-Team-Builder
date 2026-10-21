#!/bin/sh
# Dev Containerの起動時に、/workspaces直下のGit作業ツリーとその.gitの所有者を、sudoを
# 実行した利用者へそろえる（ADR 0016）。
#
# WindowsのDocker Desktopが共有する作業ツリーはroot所有に見え、Gitが「dubious ownership」で
# 停止する。Gitが所有者を検査するのは作業ツリーの最上位と.gitだけなので、その2つだけを変更し、
# Symbolic Linkはたどらない。sudoersでは引数なしの実行だけを許可する。
set -eu

[ "$#" -eq 0 ] || {
    echo "fix-workspace-owner: 引数は指定できません。" >&2
    exit 2
}

# sudoが設定する実行元の利用者を使う。任意の利用者を指定させない。
case "${SUDO_UID:-}:${SUDO_GID:-}" in
    *[!0-9:]* | :* | *:)
        echo "fix-workspace-owner: sudo経由で実行してください。" >&2
        exit 2
        ;;
esac
owner="${SUDO_UID}:${SUDO_GID}"

for directory in /workspaces/*; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || continue
    [ -e "$directory/.git" ] && [ ! -L "$directory/.git" ] || continue
    chown -h "$owner" "$directory" "$directory/.git"
done
