import argparse
import logging
import sys
import os
from asyncio.events import get_event_loop

import lightbus
import lightbus.bus
from lightbus.config import Config
from lightbus.plugins import autoload_plugins, plugin_hook, remove_all_plugins
from lightbus.utilities.logging import configure_logging
from lightbus.utilities.async import block
import lightbus.commands.run
import lightbus.commands.shell
import lightbus.commands.dump_schema
import lightbus.commands.dump_config_schema

logger = logging.getLogger(__name__)


def lightbus_entry_point():  # pragma: no cover
    sys.path.insert(0, "")
    configure_logging()
    args = parse_args()
    config = load_config(args)
    args.func(args, config)


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Lightbus management command.")
    parser.add_argument(
        "--service-name",
        "-s",
        help="Name of service in which this process resides. YOU SHOULD "
        "LIKELY SET THIS IN PRODUCTION. Can also be set using the "
        "LIGHTBUS_SERVICE_NAME environment. Will default to a random string.",
    )
    parser.add_argument(
        "--process-name",
        "-p",
        help="A unique name of this process within the service. Can also be set using the "
        "LIGHTBUS_PROCESS_NAME environment. Will default to a random string.",
    )
    parser.add_argument("--config", help="Config file to load, JSON or YAML", metavar="FILE")
    parser.add_argument(
        "--log-level",
        help="Set the log level. Overrides any value set in config. "
        "One of debug, info, warning, critical, exception.",
        metavar="LOG_LEVEL",
    )

    subparsers = parser.add_subparsers(help="Commands", dest="subcommand")
    subparsers.required = True

    lightbus.commands.run.Command().setup(parser, subparsers)
    lightbus.commands.shell.Command().setup(parser, subparsers)
    lightbus.commands.dump_schema.Command().setup(parser, subparsers)
    lightbus.commands.dump_schema.Command().setup(parser, subparsers)
    lightbus.commands.dump_config_schema.Command().setup(parser, subparsers)

    autoload_plugins(config=Config.load_dict({}))

    loop = get_event_loop()
    block(plugin_hook("before_parse_args", parser=parser, subparsers=subparsers), loop, timeout=5)
    args = parser.parse_args(sys.argv[1:] if args is None else args)
    # Note that we don't have an after_parse_args plugin hook. Instead we use the receive_args
    # hook which is called once we have instantiated our plugins

    return args


def load_config(args) -> Config:
    return lightbus.bus.load_config(
        from_file=args.config,
        service_name=args.service_name or os.environ.get("LIGHTBUS_SERVICE_NAME"),
        process_name=args.process_name or os.environ.get("LIGHTBUS_PROCESS_NAME"),
    )
