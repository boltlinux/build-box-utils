# -*- encoding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2019 Tobias Koch <tobias.koch@gmail.com>
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

import os
import re
import shlex
import subprocess
import shutil
import signal
import sys
import time

from boltlinux.buildbox.bootstrap import BBoxBootstrap
from boltlinux.buildbox.error import BBoxError
from boltlinux.buildbox.misc.paths import Paths

class BBoxTarget:

    @classmethod
    def create(cls, target_name, target_spec, **options):
        try:
            subprocess.run(
                shlex.split("{} init".format(sys.argv[0])),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise BBoxError(e.stderr.strip())

        target_prefix = options.get("target_prefix", Paths.target_prefix())

        if not os.path.isdir(target_prefix):
            try:
                os.makedirs(target_prefix)
            except OSError as e:
                raise BBoxError(
                    "failed to create target prefix '{}': {}"
                    .format(target_prefix, str(e))
                )

        if not re.match(r"^[-_a-zA-Z0-9.]+$", target_name):
            raise BBoxError(
                "the target name must consist only of characters "
                "matching [-_a-zA-Z0-9.]"
            )

        target_dir = os.path.join(target_prefix, target_name)
        if os.path.exists(target_dir):
            if os.listdir(target_dir):
                if options.get("force"):
                    cls.delete([target_name], **options)
                else:
                    raise BBoxError(
                        "target '{}' already exists, aborting."
                        .format(target_name)
                    )
                #end if
            #end if
        else:
            os.makedirs(target_dir)

        dev_dir = os.path.join(target_dir, "dev")
        if not os.path.exists(dev_dir):
            os.makedirs(dev_dir)

        mount_cmd = shlex.split(
            "{} mount -m dev -t '{}' .".format(sys.argv[0], target_dir)
        )
        proc = subprocess.run(mount_cmd)
        if proc.returncode != 0:
            raise BBoxError("failed to bind mount /dev.")

        try:
            bootstrapper = BBoxBootstrap(
                options.get("release", "stable"),
                options.get("arch", "x86_64"),
                do_verify=options.get("do_verify", True),
                cache_dir=options.get("cache_dir")
            )

            bootstrapper.bootstrap(
                target_dir, target_spec, **options
            )
        except (KeyboardInterrupt, Exception):
            old_sig_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)

            try:
                cls.delete([target_name], **options)
            except Exception:
                pass
            finally:
                signal.signal(signal.SIGINT, old_sig_handler)

            raise
        else:
            umount_cmd = shlex.split(
                "{} umount -t '{}' .".format(sys.argv[0], target_dir)
            )
            subprocess.run(umount_cmd)
        #end try
    #end function

    @classmethod
    def list(cls, **options):
        target_prefix = options.get("target_prefix", Paths.target_prefix())
        if not os.path.isdir(target_prefix):
            return

        for entry in sorted(os.listdir(target_prefix)):
            machine = "unknown"

            if not os.path.isdir(os.path.join(target_prefix, entry)):
                continue

            shell_found = False

            for prefix in ["usr", "tools"]:
                shell = os.path.join(target_prefix, entry, prefix, "bin", "sh")
                if os.path.exists(shell):
                    shell_found = True
                    break

            if not shell_found:
                machine = "defunct"

            etc_target = os.path.join(target_prefix, entry, "etc", "target")

            if not os.path.exists(etc_target):
                machine = "defunct"

            if machine != "defunct":
                with open(etc_target, "r", encoding="utf-8") as f:
                    for line in f:
                        m = re.match(
                            r"^TARGET_MACHINE\s*=\s*(?P<machine>\S+)\s*$", line
                        )
                        if not m:
                            continue
                        machine = m.group("machine")
                    #end for
                #end with
            #end if

            print("{} ({})".format(entry, machine))
        #end for
    #end function

    @classmethod
    def delete(cls, targets: list, **options):
        for target_name in set(targets):
            cls._delete(target_name, **options)

    @classmethod
    def _delete(cls, target_name, **options):
        target_prefix = options.get("target_prefix", Paths.target_prefix())

        target_dir = os.path.normpath(os.path.join(target_prefix, target_name))
        if not os.path.isdir(target_dir):
            raise BBoxError("target '{}' not found.".format(target_name))

        BBoxTarget._kill_chrooted_processes(target_dir)

        umount_cmd = shlex.split(
            "{} umount -t '{}' .".format(sys.argv[0], target_dir)
        )
        proc = subprocess.run(umount_cmd)
        if proc.returncode != 0:
            raise BBoxError("failed to remove bind mounts.")

        homedir = Paths.homedir()

        for subdir in ["dev", "proc", "sys", homedir.lstrip(os.sep)]:
            full_path = os.path.join(target_dir, subdir)
            if os.path.exists(full_path) and os.listdir(full_path):
                raise BBoxError(
                    "the '{}' subdirectory is not empty, aborting."
                    .format(subdir)
                )

        with open("/proc/mounts", "r", encoding="utf-8") as f:
            buf = f.read()

        for line in buf.splitlines():
            _, mountpoint, _, _, _, _ = line.strip().split()

            mountpoint = os.path.normpath(os.path.realpath(mountpoint))
            if mountpoint.startswith(target_dir + os.sep):
                raise BBoxError(
                    "there is something mounted at '{}', aborting."
                    .format(mountpoint)
                )
            #end if
        #end for

        old_sig_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        shutil.rmtree(target_dir)
        signal.signal(signal.SIGINT, old_sig_handler)
    #end function

    @classmethod
    def _kill_chrooted_processes(cls, chroot):
        chroot = os.path.normpath(os.path.realpath(chroot))

        for entry in os.listdir("/proc"):
            try:
                pid = int(entry)

                proc_root = os.path.normpath(
                    os.path.realpath("/proc/{}/root".format(entry))
                )

                proc_entry = "/proc/{}".format(entry)

                if chroot == proc_root:
                    os.kill(-pid, signal.SIGTERM)
                    for i in range(10):
                        os.lstat(proc_entry)
                        time.sleep(0.05 * 1.1**i)

                    os.kill(-pid, signal.SIGKILL)
                    for i in range(10):
                        os.lstat(proc_entry)
                        time.sleep(0.05 * 1.1**i)
                #end if
            except (ValueError, ProcessLookupError, PermissionError,
                        FileNotFoundError):
                pass
        #end for
    #end function

#end class
