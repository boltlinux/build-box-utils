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
import shutil
import subprocess
import tempfile

from org.boltlinux.buildbox.utils import (
    homedir, valid_arch, target_for_machine
)

from org.boltlinux.buildbox.error import BBoxError

OPKG_CONFIG_TEMPLATE = """\
##############################################################################
# OPTIONS
##############################################################################

{opt_check_sig}

option cache_dir /.pkg-cache
option signature_type usign
option no_install_recommends
option force_removal_of_dependent_packages
option force_postinstall

##############################################################################
# FEEDS
##############################################################################

src/gz main {repo_base}/{suite}/{libc}/{arch}/main
src/gz main-debug {repo_base}/{suite}/{libc}/{arch}/main-debug
src/gz tools {repo_base}/{suite}/{libc}/{arch}/tools
src/gz tools-debug {repo_base}/{suite}/{libc}/{arch}/tools-debug

##############################################################################
# ARCHES
##############################################################################

arch {arch} 1
arch all 1
arch tools 1

##############################################################################
# INSTALL ROOT
##############################################################################

dest root /
"""

ETC_TARGET_TEMPLATE="""\
TARGET_ID={target_id}
TARGET_MACHINE={machine}
TARGET_TYPE={target_type}
TOOLS_TYPE=x86_64-tools-linux-musl
"""

class BBoxBootstrap:

    def __init__(self, suite, arch, libc="musl"):
        if not valid_arch(arch):
            raise BBoxError("unknown target architecture: {}".format(arch))

        self._suite = suite
        self._arch  = arch
        self._libc  = libc
    #end function

    def bootstrap(self, target_dir, specfile, force=False, **options):
        context = {
            "suite": self._suite,
            "libc": self._libc,
            "arch": self._arch,
            "target_id": os.path.basename(target_dir),
            "machine": self._arch,
            "target_type": target_for_machine(self._arch),
            "opt_check_sig": "",
            "repo_base": options.get("repo_base")
        }

        package_cache = self.package_cache()
        if not os.path.exists(package_cache):
            os.makedirs(package_cache)

        batches = self._read_package_spec(specfile)

        package_cache_symlink = os.path.join(target_dir, ".pkg-cache")
        if not os.path.exists(package_cache_symlink):
            os.symlink(package_cache, package_cache_symlink)

        with tempfile.TemporaryDirectory(prefix="bbox-") as dirname:
            opkg_conf = os.path.join(dirname, "opkg.conf")
            with open(opkg_conf, "w+", encoding="utf-8") as f:
                f.write(OPKG_CONFIG_TEMPLATE.format(**context))
            self._prepare_target(opkg_conf, target_dir, batches)
        #end with

        etc_target = os.path.join(target_dir, "etc", "target")
        with open(etc_target, "w+", encoding="utf-8") as f:
            f.write(ETC_TARGET_TEMPLATE.format(**context))
    #end function

    def package_cache(self):
        return os.path.join(
            homedir(), ".bolt", "cache", "binaries", self._suite, self._arch
        )
    #end function

    # PRIVATE

    def _prepare_target(self, opkg_conf, target_dir, batches):
        dirs_to_create = [
            "var",
            "run",
            "etc",
            "etc/opkg",
            "etc/opkg/usign",
            "tools",
            "tools/bin",
        ]

        for dirname in dirs_to_create:
            full_path = os.path.join(target_dir, dirname)
            os.makedirs(full_path, exist_ok=True)
        #end for

        var_run_symlink = os.path.join(target_dir, "var", "run")
        if not os.path.exists(var_run_symlink):
            os.symlink("../run", var_run_symlink)

        # NOTE: important detail here...
        shutil.copy2(opkg_conf, os.path.join(target_dir, "etc", "opkg"))

        opkg_cmd = shlex.split(
            "opkg --conf '{}' --offline-root '{}' update".format(
                opkg_conf,
                target_dir
            )
        )

        try:
            subprocess.run(opkg_cmd, check=True)
        except subprocess.CalledProcessError:
            raise BBoxError("failed to update package index.")

        for mode, batch in batches:
            mode = "install" if mode == "+" else "remove"

            opkg_cmd = shlex.split(
                "opkg --conf '{}' --offline-root '{}' {} {}".format(
                    opkg_conf, target_dir, mode, " ".join(batch)
                )
            )

            try:
                subprocess.run(opkg_cmd, check=True)
            except subprocess.CalledProcessError:
                raise BBoxError("failed to install batch of packages.")
        #end for
    #end function

    def _read_package_spec(self, specfile):
        if not os.path.exists(specfile):
            raise BBoxError(
                "package spec file '{}' not found.".format(specfile)
            )
        #end if

        batches = []

        active_batch = []
        active_mode  = None

        with open(specfile, "r", encoding="utf-8") as f:
            lineno = 0

            for line in f:
                lineno += 1

                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                m = re.match(r"^(?P<mode>\+|-|=)\s*(?P<pkg>\S*)\s*$", line)

                if not m:
                    raise BBoxError(
                        "malformatted entry in '{}' on line '{}'."
                        .format(specfile, lineno)
                    )
                #end if

                mode = m.group("mode") or "+"

                if mode != active_mode:
                    if active_batch:
                        batches.append((active_mode, active_batch))
                        active_batch = []
                    #end if

                    active_mode = mode
                #end if

                if mode in ["+", "-"]:
                    pkg = m.group("pkg")

                    if not pkg:
                        raise BBoxError(
                            "malformatted entry in '{}' on line '{}'."
                            .format(specfile, lineno)
                        )
                    #end if

                    active_batch.append(pkg)
                #end if
            #end for
        #end with

        if active_batch:
            batches.append((active_mode, active_batch))

        return batches
    #end function

#end class
