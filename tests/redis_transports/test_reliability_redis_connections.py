import asyncio
import logging

import pytest
from aioredis import create_redis_pool

import lightbus

pytestmark = pytest.mark.reliability


@pytest.mark.asyncio
async def test_redis_connections_closed(redis_client, loop, dummy_api, new_bus, caplog):
    # Ensure we have no connections at the start
    await redis_client.execute(b"CLIENT", b"KILL", b"TYPE", b"NORMAL")

    info = await redis_client.info()
    assert int(info["clients"]["connected_clients"]) == 1  # This connection

    # Open and close the bus
    bus = await new_bus()

    info = await redis_client.info()
    assert int(info["clients"]["connected_clients"]) > 1

    await bus.client.close_async()

    # Now check we still have no connections
    info = await redis_client.info()
    assert int(info["clients"]["connected_clients"]) == 1  # This connection


@pytest.mark.asyncio
async def test_create_and_destroy_redis_buses(redis_client, loop, dummy_api, new_bus, caplog):
    caplog.set_level(logging.WARNING)

    for _ in range(0, 100):
        # make a bus
        bus = await new_bus()
        # fire an event
        await bus.my.dummy.my_event.fire_async(field="a")
        # close it
        await bus.client.close_async()

    info = await redis_client.info()

    assert int(info["stats"]["total_connections_received"]) >= 100
    assert int(info["clients"]["connected_clients"]) == 1


@pytest.mark.parametrize(
    "transport_class,kwargs",
    [
        (lightbus.RedisRpcTransport, {}),
        (lightbus.RedisResultTransport, {}),
        (
            lightbus.RedisEventTransport,
            {"consumer_group_prefix": "test_cg", "consumer_name": "test_consumer"},
        ),
        (lightbus.RedisSchemaTransport, {}),
    ],
    ids=["rpc", "result", "event", "schema"],
)
@pytest.mark.asyncio
async def test_create_and_destroy_redis_transports(
    transport_class, kwargs, redis_client, loop, server, caplog
):
    caplog.set_level(logging.WARNING)

    for _ in range(0, 100):
        pool = await create_redis_pool(server.tcp_address, loop=loop, maxsize=1000)
        transport = transport_class(redis_pool=pool, **kwargs)
        await transport.open()
        await transport.close()

    info = await redis_client.info()

    assert int(info["stats"]["total_connections_received"]) >= 100
    assert int(info["clients"]["connected_clients"]) == 1
