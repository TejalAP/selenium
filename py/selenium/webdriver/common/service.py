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
import contextlib
import errno
import logging
import os
import subprocess
import typing
from abc import ABC
from abc import abstractmethod
from platform import system
from subprocess import DEVNULL
from subprocess import PIPE
from time import sleep
from urllib import request
from urllib.error import URLError

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common import utils

log = logging.getLogger(__name__)


_HAS_NATIVE_DEVNULL = True


class Service(ABC):
    def __init__(
        self,
        executable: str,
        port: int = 0,
        log_file=DEVNULL,
        env: typing.Optional[typing.Dict[typing.Any, typing.Any]] = None,
        start_error_message: str = "",
    ) -> None:
        self.path = executable
        self.port = port or utils.free_port()
        self.log_file = open(os.devnull, "wb") if not _HAS_NATIVE_DEVNULL and log_file == DEVNULL else log_file
        self.start_error_message = start_error_message
        # Default value for every python subprocess: subprocess.Popen(..., creationflags=0)
        self.creation_flags = 0
        self.env = env or os.environ
        self.process: typing.Optional[subprocess.Popen] = None

    @property
    def service_url(self) -> str:
        """
        Gets the url of the Service
        """
        return f"http://{utils.join_host_port('localhost', self.port)}"

    @abstractmethod
    def command_line_args(self) -> typing.List[str]:
        raise NotImplementedError("This method needs to be implemented in a sub class")

    def start(self) -> None:
        """
        Starts the Service.

        :Exceptions:
         - WebDriverException : Raised either when it can't start the service
           or when it can't connect to the service
        """
        try:
            cmd = [self.path]
            cmd.extend(self.command_line_args())
            self.process = subprocess.Popen(
                cmd,
                env=self.env,
                close_fds=system() != "Windows",
                stdout=self.log_file,
                stderr=self.log_file,
                stdin=PIPE,
                creationflags=self.creation_flags,
            )
        except TypeError:
            raise
        except OSError as err:
            if err.errno == errno.ENOENT:
                raise WebDriverException(
                    "'{}' executable needs to be in PATH. {}".format(
                        os.path.basename(self.path), self.start_error_message
                    )
                )
            elif err.errno == errno.EACCES:
                raise WebDriverException(
                    "'{}' executable may have wrong permissions. {}".format(
                        os.path.basename(self.path), self.start_error_message
                    )
                )
            else:
                raise
        except Exception as e:
            raise WebDriverException(
                "The executable %s needs to be available in the path. %s\n%s"
                % (os.path.basename(self.path), self.start_error_message, str(e))
            )
        count = 0
        while True:
            self.assert_process_still_running()
            if self.is_connectable():
                break

            count += 1
            sleep(0.5)
            if count == 60:
                raise WebDriverException(f"Can not connect to the Service {self.path}")

    def assert_process_still_running(self) -> None:
        """Check if the underlying process is still running."""
        return_code = self.process.poll()
        if return_code:
            raise WebDriverException(f"Service {self.path} unexpectedly exited. Status code was: {return_code}")

    def is_connectable(self) -> bool:
        """Establishes a socket connection to determine if the service running on
        the port is accessible."""
        return utils.is_connectable(self.port)

    def send_remote_shutdown_command(self) -> None:
        """
        Dispatch an HTTP request to the shutdown endpoint for the service in an
        attempt to stop it.
        """
        try:
            request.urlopen(f"{self.service_url}/shutdown")
        except URLError:
            return

        for _ in range(30):
            if not self.is_connectable():
                break
            sleep(1)

    def stop(self) -> None:
        """
        Stops the service.
        """
        if self.log_file != PIPE and not (self.log_file == DEVNULL and _HAS_NATIVE_DEVNULL):
            with contextlib.suppress(Exception):
                # Todo: Be explicit in what we are catching here.
                self.log_file.close()

        if self.process is not None:
            with contextlib.suppress(TypeError):
                self.send_remote_shutdown_command()
            self._terminate_process()

    def _terminate_process(self) -> None:
        """Terminate the child process.  On POSIX this attempts a graceful
        SIGTERM followed by a SIGKILL, on a Windows OS kill is an alias to
        terminate.  Terminating does not raise itself if something has gone
        wrong but (currently) silently ignores errors here."""
        try:
            stdin, stdout, stderr = self.process.stdin, self.process.stdout, self.process.stderr
            for stream in stdin, stdout, stderr:
                with contextlib.suppress(AttributeError):
                    stream.close()
            self.process.terminate()
            self.process.wait(60)
            # Todo: only SIGKILL if necessary; the process may be cleanly exited by now.
            self.process.kill()
        except OSError:
            log.error("Error terminating service process.", exc_info=True)

    def __del__(self) -> None:
        # `subprocess.Popen` doesn't send signal on `__del__`;
        # so we attempt to close the launched process when `__del__`
        # is triggered.
        with contextlib.suppress(Exception):
            self.stop()
