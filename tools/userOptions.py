#!/usr/bin/env python3
"""
Lightweight command-line option parser used by the legacy tooling scripts.
Arguments are provided in "-option value" pairs and validated against
specified defaults.
"""

__author__ = "Matthias Nagler <matt@dforce.de>"
__url__ = ("dforce3000", "dforce3000.de")
__version__ = "0.1"

import logging
import sys


class Options:
    def __init__(self, args, defaults):
        self.__options = self.__parse_user_arguments(args, defaults)

    def get(self, option):
        if option in self.__options:
            return self.__options[option]["value"]
        logging.error("Invalid option %s requested." % option)
        sys.exit(1)

    def manualSet(self, option, value):
        self.__options[option]["value"] = value

    def set(self, option, value):
        self.__options[option]["value"] = value

    def __parse_user_arguments(self, args, defaults):
        options = {key: value.copy() for key, value in defaults.items()}
        for index, arg in enumerate(args):
            if arg.startswith("-") and arg[1:] in options and index + 1 < len(args):
                options[arg[1:]]["value"] = args[index + 1]
        return self.__sanitize_options(options)

    def __sanitize_options(self, options):
        sanitizer_lookup = self.__get_sanitizer_lookup()
        for optionName, optionValue in options.items():
            sanitizer = sanitizer_lookup.get(optionValue["type"])
            if sanitizer:
                options[optionName] = sanitizer(optionName, optionValue)
        return options

    def __sanitize_int(self, optionName, optionValue):
        if not isinstance(optionValue["value"], int):
            try:
                optionValue["value"] = int(optionValue["value"], 10)
            except (TypeError, ValueError):
                logging.error(
                    "Invalid argument %s for option -%s." % (optionValue["value"], optionName)
                )
                sys.exit(1)
        if optionValue["value"] < optionValue["min"] or optionValue["value"] > optionValue["max"]:
            logging.error(
                "Argument %s for option -%s is out of allowed range %s - %s."
                % (optionValue["value"], optionName, optionValue["min"], optionValue["max"])
            )
            sys.exit(1)
        return optionValue

    def __sanitize_float(self, optionName, optionValue):
        if not isinstance(optionValue["value"], float):
            try:
                optionValue["value"] = float(optionValue["value"])
            except (TypeError, ValueError):
                logging.error(
                    "Invalid argument %s for option -%s." % (optionValue["value"], optionName)
                )
                sys.exit(1)
        if optionValue["value"] < optionValue["min"] or optionValue["value"] > optionValue["max"]:
            logging.error(
                "Argument %s for option -%s is out of allowed range %s - %s."
                % (optionValue["value"], optionName, optionValue["min"], optionValue["max"])
            )
            sys.exit(1)
        return optionValue

    def __sanitize_hex(self, optionName, optionValue):
        if not isinstance(optionValue["value"], int):
            try:
                optionValue["value"] = int(optionValue["value"], 16)
            except (TypeError, ValueError):
                logging.error(
                    "Invalid argument %s for option -%s." % (optionValue["value"], optionName)
                )
                sys.exit(1)
        if optionValue["value"] < optionValue["min"] or optionValue["value"] > optionValue["max"]:
            logging.error(
                "Argument %s for option -%s is out of allowed range %s - %s."
                % (optionValue["value"], optionName, optionValue["min"], optionValue["max"])
            )
            sys.exit(1)
        return optionValue

    def __sanitize_str(self, optionName, optionValue):
        if optionValue["value"] is None:
            logging.error("Argument %s for option -%s is invalid." % (optionValue["value"], optionName))
            sys.exit(1)
        return optionValue

    def __sanitize_bool(self, optionName, optionValue):
        if isinstance(optionValue["value"], str):
            if optionValue["value"] not in ("on", "off"):
                logging.error(
                    "Argument %s for option -%s is invalid. Only on and off are allowed."
                    % (optionValue["value"], optionName)
                )
                sys.exit(1)
            optionValue["value"] = optionValue["value"] == "on"
        return optionValue

    def __get_sanitizer_lookup(self):
        return {
            "int": self.__sanitize_int,
            "float": self.__sanitize_float,
            "hex": self.__sanitize_hex,
            "str": self.__sanitize_str,
            "bool": self.__sanitize_bool,
        }


__all__ = ["Options"]
