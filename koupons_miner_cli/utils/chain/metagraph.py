import argparse
import asyncio
import json
import socket
import struct
import sys
from typing import Optional

# Testnet Configuration
FINNEY_NETWORK = "finney"
FINNEY_TEST_NETWORK = "test"
FINNEY_SUBTENSOR_ADDRESS = "wss://entrypoint-finney.opentensor.ai:443"
FINNEY_TEST_SUBTENSOR_ADDRESS = "wss://test.finney.opentensor.ai:443/"

SS58_FORMAT = 42

SUBTENSOR_NETWORK_TO_SUBTENSOR_ADDRESS = {
    FINNEY_NETWORK: FINNEY_SUBTENSOR_ADDRESS,
    FINNEY_TEST_NETWORK: FINNEY_TEST_SUBTENSOR_ADDRESS,
}

FINNEY_NETUID = 16
FINNEY_TEST_NETUID = 368

NETWORK_TO_NETUID = {
    FINNEY_NETWORK: FINNEY_NETUID,
    FINNEY_TEST_NETWORK: FINNEY_TEST_NETUID,
}


def check_dependencies():
    """Check if all required packages are installed"""
    required_packages = {
        "async_substrate_interface": "async-substrate-interface",
        "scalecodec": "scalecodec",
    }

    missing_packages = []
    for module, package in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("Error: Missing required packages. Please install them using pip:")
        print(f"pip install {' '.join(missing_packages)}")
        sys.exit(1)


check_dependencies()

from async_substrate_interface import AsyncSubstrateInterface
from scalecodec.utils.ss58 import ss58_encode


def get_chain_endpoint(
    subtensor_network: Optional[str], subtensor_address: Optional[str]
) -> str:
    """Get the chain endpoint URL for the specified network"""
    if subtensor_network is None and subtensor_address is None:
        raise ValueError("subtensor_network and subtensor_address cannot both be None")

    if subtensor_address is not None:
        print(f"🔗 Using chain address: {subtensor_address}")
        return subtensor_address

    if subtensor_network not in SUBTENSOR_NETWORK_TO_SUBTENSOR_ADDRESS:
        raise ValueError(f"❌ Unrecognized chain network: {subtensor_network}")

    subtensor_address = SUBTENSOR_NETWORK_TO_SUBTENSOR_ADDRESS[subtensor_network]
    print(f"🌐 Using network: {subtensor_network} -> {subtensor_address}")
    return subtensor_address


def get_substrate(
    subtensor_network: Optional[str] = FINNEY_TEST_NETWORK,
    subtensor_address: Optional[str] = None,
) -> AsyncSubstrateInterface:
    """Create AsyncSubstrateInterface for testnet connection"""
    subtensor_address = get_chain_endpoint(subtensor_network, subtensor_address)
    substrate = AsyncSubstrateInterface(
        ss58_format=SS58_FORMAT,
        use_remote_preset=True,
        url=subtensor_address,
    )
    return substrate


def ss58_encode_address(
    address: list[int] | list[list[int]], ss58_format: int = SS58_FORMAT
) -> str:
    """Encode address to SS58 format"""
    if not isinstance(address[0], int):
        address = address[0]
    return ss58_encode(bytes(address).hex(), ss58_format)


def parse_ip(ip_int: int) -> str:
    """Parse integer IP to string format"""
    ip_bytes = struct.pack(">I", ip_int)
    return socket.inet_ntoa(ip_bytes)


async def get_testnet_metagraph(
    substrate: AsyncSubstrateInterface,
    netuid: int = FINNEY_TEST_NETUID,
    block: Optional[int] = None,
) -> list[dict]:
    """
    Get complete metagraph data from testnet

    Args:
        substrate: AsyncSubstrateInterface connected to testnet
        netuid: Network UID (default: 368 for testnet)
        block: Specific block number (None for latest)

    Returns:
        List of node dictionaries with complete metagraph data
    """
    print(f"📊 Fetching testnet metagraph for subnet {netuid}...")

    try:
        block_hash = (
            await substrate.get_block_hash(block) if block is not None else None
        )

        response = await substrate.runtime_call(
            api="SubnetInfoRuntimeApi",
            method="get_metagraph",
            params=[netuid],
            block_hash=block_hash,
        )

        if not response or not response.value:
            print(f"❌ No metagraph data found for subnet {netuid}")
            return []

        metagraph = response.value
        nodes = []

        print(f"✅ Found {len(metagraph['hotkeys'])} nodes in subnet {netuid}")

        for uid in range(len(metagraph["hotkeys"])):
            axon = metagraph["axons"][uid]
            node = {
                "uid": uid,
                "hotkey": ss58_encode_address(metagraph["hotkeys"][uid], SS58_FORMAT),
                "coldkey": ss58_encode_address(metagraph["coldkeys"][uid], SS58_FORMAT),
                "netuid": metagraph["netuid"],
                "incentive": metagraph["incentives"][uid],
                "alpha_stake": metagraph["alpha_stake"][uid] * 10**-9,
                "tao_stake": metagraph["tao_stake"][uid] * 10**-9,
                "total_stake": metagraph["total_stake"][uid] * 10**-9,
                "trust": metagraph["trust"][uid],
                "dividends": metagraph["dividends"][uid],
                "last_updated": float(metagraph["last_update"][uid]),
                "ip": parse_ip(axon["ip"]),
                "ip_type": axon["ip_type"],
                "port": axon["port"],
                "protocol": axon["protocol"],
            }
            nodes.append(node)

        return nodes

    except Exception as e:
        print(f"❌ Error fetching metagraph: {e}")
        return []


async def analyze_testnet_metagraph(nodes: list[dict]):
    """Analyze and display testnet metagraph statistics"""
    if not nodes:
        print("❌ No nodes to analyze")
        return

    print("\n" + "=" * 80)
    print("📈 TESTNET METAGRAPH ANALYSIS")
    print("=" * 80)

    # Basic statistics
    total_nodes = len(nodes)
    active_nodes = [n for n in nodes if n["ip"] != "0.0.0.0"]
    total_stake = sum(n["total_stake"] for n in nodes)

    print("📊 Network Statistics:")
    print(f"   Total nodes: {total_nodes}")
    print(f"   Active nodes (with real IP): {len(active_nodes)}")
    print(f"   Total network stake: {total_stake:.2f} TAO")
    print(f"   Average stake per node: {total_stake / total_nodes:.2f} TAO")

    # URLs/IPs and Ports Section
    print("\n🌐 NODE ENDPOINTS (IPs and Ports):")
    print("-" * 80)
    if active_nodes:
        for node in active_nodes:
            endpoint_url = f"http://{node['ip']}:{node['port']}"
            print(
                f"   UID {node['uid']:3d} | {node['ip']:15s}:{node['port']:5d} | {endpoint_url}"
            )
            print(f"          Hotkey: {node['hotkey'][:20]}...")
            print(f"          Stake: {node['total_stake']:8.2f} TAO")
            print()
    else:
        print("   ❌ No active nodes with real IP addresses found")

    # Summary of all endpoints
    print("\n📋 ENDPOINT SUMMARY:")
    endpoints = []
    for node in active_nodes:
        endpoint = {
            "uid": node["uid"],
            "ip": node["ip"],
            "port": node["port"],
            "url": f"http://{node['ip']}:{node['port']}",
            "stake": node["total_stake"],
            "hotkey": node["hotkey"],
        }
        endpoints.append(endpoint)

    # Sort by stake
    endpoints.sort(key=lambda x: x["stake"], reverse=True)

    print(f"   Total endpoints: {len(endpoints)}")
    print("\n   Top 10 by stake:")
    for i, ep in enumerate(endpoints[:10]):
        print(
            f"   {i + 1:2d}. {ep['url']:25s} | {ep['stake']:8.2f} TAO | UID {ep['uid']}"
        )

    # Top nodes by stake
    print("\n💰 Top 10 Nodes by Stake:")
    sorted_nodes = sorted(nodes, key=lambda x: x["total_stake"], reverse=True)
    for i, node in enumerate(sorted_nodes[:10]):
        print(
            f"   {i + 1:2d}. UID {node['uid']:3d} | {node['total_stake']:8.2f} TAO | {node['hotkey'][:10]}..."
        )

    # Network activity
    print("\n🔥 Network Activity:")
    recent_updates = [n for n in nodes if n["last_updated"] > 0]
    print(f"   Nodes with recent updates: {len(recent_updates)}")

    # IP distribution
    unique_ips = set(n["ip"] for n in active_nodes)
    print(f"   Unique IP addresses: {len(unique_ips)}")

    # Protocol distribution
    protocols = {}
    for node in nodes:
        proto = node["protocol"]
        protocols[proto] = protocols.get(proto, 0) + 1

    print("\n🌐 Protocol Distribution:")
    for proto, count in protocols.items():
        print(f"   Protocol {proto}: {count} nodes")

    # Port distribution
    ports = {}
    for node in active_nodes:
        port = node["port"]
        ports[port] = ports.get(port, 0) + 1

    print("\n🔌 Port Distribution:")
    for port, count in sorted(ports.items()):
        print(f"   Port {port}: {count} nodes")

    return endpoints


async def check_testnet_connection():
    """Check basic testnet connectivity"""
    print("🧪 Testing testnet connection...")

    try:
        async with get_substrate(FINNEY_TEST_NETWORK) as substrate:
            # Test basic connection by getting current block
            block_number = await substrate.get_block_number(None)
            print(f"✅ Connected to testnet, current block: {block_number}")

            # Test runtime call to verify subnet access
            netuid = FINNEY_TEST_NETUID
            try:
                response = await substrate.runtime_call(
                    api="SubnetInfoRuntimeApi",
                    method="get_metagraph",
                    params=[netuid],
                )
                if response and response.value:
                    print(f"✅ Subnet {netuid} is accessible")
                    return True
                else:
                    print(f"⚠️  Subnet {netuid} exists but has no data")
                    return False
            except Exception as e:
                print(f"❌ Subnet {netuid} not accessible: {e}")
                return False

    except Exception as e:
        print(f"❌ Testnet connection failed: {e}")
        return False


async def main():
    """Main function to connect to testnet metagraph"""
    parser = argparse.ArgumentParser(
        description="Connect to Bittensor Testnet Metagraph"
    )
    parser.add_argument(
        "--netuid",
        type=int,
        default=FINNEY_TEST_NETUID,
        help=f"Network UID to analyze (default: {FINNEY_TEST_NETUID})",
    )
    parser.add_argument(
        "--block",
        type=int,
        default=None,
        help="Specific block number to query (default: latest)",
    )
    parser.add_argument(
        "--network",
        type=str,
        default=FINNEY_TEST_NETWORK,
        choices=[FINNEY_NETWORK, FINNEY_TEST_NETWORK],
        help="Network to connect to (default: test)",
    )

    args = parser.parse_args()

    print("🚀 CONNECTING TO BITTENSOR TESTNET METAGRAPH")
    print("=" * 60)

    # Test connection first
    if not await check_testnet_connection():
        print("❌ Cannot connect to testnet. Exiting.")
        return

    print("\n" + "=" * 60)

    # Connect to metagraph
    try:
        async with get_substrate(args.network) as substrate:
            print(f"🔗 Connected to {args.network} network")

            # Get metagraph data
            nodes = await get_testnet_metagraph(
                substrate, netuid=args.netuid, block=args.block
            )

            if nodes:
                # Analyze the data
                endpoints = await analyze_testnet_metagraph(nodes)

                print(f"\n✅ Successfully retrieved metagraph for subnet {args.netuid}")
                print(f"📊 Found {len(nodes)} total nodes")

                # Save full data to JSON file
                filename = f"testnet_metagraph_{args.netuid}.json"
                with open(filename, "w") as f:
                    json.dump(nodes, f, indent=2)
                print(f"💾 Full data saved to {filename}")

                # Save endpoints to separate JSON file
                if endpoints:
                    endpoints_filename = f"testnet_endpoints_{args.netuid}.json"
                    with open(endpoints_filename, "w") as f:
                        json.dump(endpoints, f, indent=2)
                    print(f"🔗 Endpoints saved to {endpoints_filename}")

                    # Create simple URLs list
                    urls_list = [ep["url"] for ep in endpoints]
                    urls_filename = f"testnet_urls_{args.netuid}.txt"
                    with open(urls_filename, "w") as f:
                        for url in urls_list:
                            f.write(f"{url}\n")
                    print(f"📝 URL list saved to {urls_filename}")

            else:
                print(f"❌ No data found for subnet {args.netuid}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
