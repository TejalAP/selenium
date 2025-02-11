# Licensed to the Software Freedom Conservancy (SFC) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The SFC licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import os
import typing
from subprocess import PIPE

from selenium.webdriver.common import service
from selenium.webdriver.common import utils

DEFAULT_EXECUTABLE_PATH: str = "/usr/bin/safaridriver"


class Service(service.Service):
    """
    Object that manages the starting and stopping of the SafariDriver
    """

    def __init__(
        self,
        executable_path: str = DEFAULT_EXECUTABLE_PATH,
        port: int = 0,
        quiet: bool = False,
        service_args: typing.Optional[typing.List[str]] = None,
    ):
        """
        Creates a new instance of the Service

        :Args:
         - executable_path : Path to the SafariDriver
         - port : Port the service is running on
         - quiet : Suppress driver stdout and stderr
         - service_args : List of args to pass to the safaridriver service"""

        if not os.path.exists(executable_path):
            if "Safari Technology Preview" in executable_path:
                message = "Safari Technology Preview does not seem to be installed. You can download it at https://developer.apple.com/safari/download/."
            else:
                message = "SafariDriver was not found; are you running Safari 10 or later? You can download Safari at https://developer.apple.com/safari/download/."
            raise Exception(message)

        port = port or utils.free_port()
        self.service_args = service_args or []
        self.quiet = quiet
        log = PIPE
        if quiet:
            log = open(os.devnull, "w", encoding="utf-8")
        super().__init__(executable_path, port, log)

    def command_line_args(self) -> typing.List[str]:
        return ["-p", f"{self.port}"] + self.service_args

    @property
    def service_url(self) -> str:
        """
        Gets the url of the SafariDriver Service
        """
        return f"http://localhost:{self.port}"
