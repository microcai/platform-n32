# type: ignore
import json
import os
import sys

from platformio.public import PlatformBase

IS_WINDOWS = sys.platform.startswith("win")

PLATFORM_DIR = os.path.dirname(__file__)


class Platformn32Platform(PlatformBase):

    def is_embedded(self):
        return True

    def configure_default_packages(self, variables, targets):
        board = variables.get("board")
        board_config = self.board_config(board)

        default_protocol = board_config.get("upload.protocol") or ""
        upload = variables.get("upload_protocol", default_protocol)
        if upload == "daplink":
            self.packages["tool-pyocd"]["optional"] = False

        # TODO: also do same for jlink

        return super().configure_default_packages(
            variables, targets)


    def get_boards(self, id_=None):
        result = super().get_boards(id_)
        if not result:
            return result
        if id_:
            return self._add_default_debug_tools(result)
        else:
            for key, value in result.items():
                result[key] = self._add_default_debug_tools(result[key])
        return result

    def _add_default_debug_tools(self, board):
        debug = board.manifest.get("debug", {})
        upload_protocols = board.manifest.get("upload", {}).get(
            "protocols", [])
        if "tools" not in debug:
            debug["tools"] = {}

        for link in ("daplink", "jlink"):
            if link not in upload_protocols or link in debug["tools"]:
                continue

            if link == "daplink":
                pyocd_target = debug.get("pyocd_target")
                assert pyocd_target

                debug["tools"][link] = {
                    # "onboard": True,
                    "server": {
                        "package": "tool-pyocd",
                        "executable": "$PYTHONEXE",
                        "arguments": [
                            "pyocd-gdbserver.py",
                            "--pack", os.path.join(PLATFORM_DIR, 'misc', debug.get("pack")),
                            "--target",  pyocd_target,
                        ],
                        "ready_pattern": "GDB server started on port"
                    }
                }

            elif link == "jlink":
                assert debug.get("jlink_device"), (
                    "Missed J-Link Device ID for %s" % board.id)
                debug["tools"][link] = {
                    "server": {
                        "package": "tool-jlink",
                        "arguments": [
                            "-singlerun",
                            "-if", "SWD",
                            "-select", "USB",
                            "-device", debug.get("jlink_device"),
                            "-port", "2331"
                        ],
                        "executable": ("JLinkGDBServerCL.exe"
                                       if IS_WINDOWS else
                                       "JLinkGDBServer")
                    }
                }

        board.manifest["debug"] = debug
        return board

    def configure_debug_session(self, debug_config):
        if debug_config.speed:
            if "jlink" in (debug_config.server or {}).get("executable", "").lower():
                debug_config.server["arguments"].extend(
                    ["-speed", debug_config.speed]
                )
            elif "pyocd" in debug_config.server["package"]:
                debug_config.server["arguments"].extend(
                    ["--frequency", debug_config.speed]
                )
