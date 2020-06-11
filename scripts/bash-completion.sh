#
# The MIT License (MIT)
#
# Copyright (c) 2020 Tobias Koch <tobias.koch@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

_build_box_arg_complete() {
    local _build_box_cmd="${COMP_WORDS[0]} ${COMP_WORDS[1]}"
    local _previous_arg="${COMP_WORDS[$(($COMP_CWORD-1))]}"

    local _opt_arg=""

    case "$_previous_arg" in
        -*)
            _opt_arg=$(
                $_build_box_cmd --help | \
                    grep -E '^ -' | \
                    sed -E -e 's/^\s*/,/g' -e 's/ /,/' -e 's/  .*$//g' | \
                    grep -E -- ",$_previous_arg," | \
                    cut -d',' -f4
            )
            ;;
    esac

    case "$_opt_arg" in
        '<arch>')
            COMPREPLY=(
                $(
                    compgen -W "aarch64 armv6 armv7a i686 mipsel mips64el powerpc64le s390x x86_64" \
                        -- ${COMP_WORDS[COMP_CWORD]}
                )
            )
            return
            ;;
        '<dir>')
            _cd
            return
            ;;
        '<fstype>')
            COMPREPLY=(
                $(
                    compgen -W "dev proc sys home" -- ${COMP_WORDS[COMP_CWORD]}
                )
            )
            return
            ;;
    esac

    local _word_counter=0
    local _varg_counter=0
    local _target_dir="$HOME/.bolt/targets"

    while [ "$_word_counter" -lt "${#COMP_WORDS[*]}" ]; do
        local _varg="${COMP_WORDS[$_word_counter]}"

        case "$_varg" in
            -t|--targets)
                case "${COMP_WORDS[$(($_word_counter+1))]}" in
                    =)
                        _target_dir="${COMP_WORDS[$(($_word_counter+2))]}"
                        _word_counter=$(($_word_counter+3))
                        ;;
                    *)
                        _target_dir="${COMP_WORDS[$(($_word_counter+1))]}"
                        _word_counter=$(($_word_counter+2))
                        ;;
                esac
                ;;
            -*)
                _opt_arg=$(
                    $_build_box_cmd --help | \
                        grep -E '^ -' | \
                        sed -E -e 's/^\s*/,/g' -e 's/ /,/' -e 's/  .*$//g' | \
                        grep -E -- ",$_varg," | \
                        cut -d',' -f4
                )

                if [ -n "$_opt_arg" ]; then
                    case "${COMP_WORDS[$(($_word_counter+1))]}" in
                        =)
                            _word_counter=$(($_word_counter+3))
                            ;;
                        *)
                            _word_counter=$(($_word_counter+2))
                            ;;
                    esac
                else
                    _word_counter=$(($_word_counter+1))
                fi
                ;;
            *)
                _word_counter=$(($_word_counter+1))
                _varg_counter=$(($_varg_counter+1))
                ;;
        esac
    done

    local _expected_arg=$(
        $_build_box_cmd --help | \
            grep -E '^Usage:' | \
            sed -E -e 's/^Usage:\s*//' -e 's/\[OPTIONS\]//' -e 's/\s+/ /g' | \
            cut -d' ' -f"$(($_varg_counter))"
    )

    case "$_expected_arg" in
        '<target-name>')
            COMPREPLY=(
                $(
                    compgen -W "$(
                        ${COMP_WORDS[0]} list --targets="$_target_dir" | \
                            cut -d' ' -f1
                    )" -- ${COMP_WORDS[COMP_CWORD]}
                )
            )
            ;;
        '<dir>')
            _cd
            ;;
        '<spec>')
            compopt -o default
            COMPREPLY=()
            ;;
    esac
}

_build_box_opt_complete() {
    local _opts="-h -help"

    case "${COMP_WORDS[1]}" in
        create)
            _opts="$_opts -r --release -a --arch -t --targets --force --repo-base --no-verify"
            ;;
        delete|list|mount)
            _opts="$_opts -t --targets"
            ;;
        login|run)
            _opts="$_opts -t --targets -n --no-mount --no-file-copy"
            ;;
        mount|umount)
            _opts="$_opts -t --targets -m --mount"
            ;;
    esac

    COMPREPLY=($(compgen -W "$_opts" -- ${COMP_WORDS[COMP_CWORD]}))
}

_build_box_complete() {
    local _valid_commands="create delete list login mount umount run"

    case "$COMP_CWORD" in
        1)
            COMPREPLY=(
                $(
                    compgen -W "$_valid_commands" \
                        -- ${COMP_WORDS[COMP_CWORD]}
                )
            )
            ;;
        *)
            _valid_commands=$(echo $_valid_commands | sed 's/ /|/g')

            eval "case \"${COMP_WORDS[1]}\" in
                $_valid_commands)
                    case \"${COMP_WORDS[COMP_CWORD]}\" in
                        -*)
                            _build_box_opt_complete
                            ;;
                        *)
                            _build_box_arg_complete
                            ;;
                    esac
                    ;;
            esac"
            ;;
    esac
}

complete -F _build_box_complete build-box
