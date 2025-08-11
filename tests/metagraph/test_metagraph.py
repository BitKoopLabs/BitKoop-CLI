import asyncio
import logging

from koupons_miner_cli.utils.chain.metagraph.metagraph_client import (
    create_metagraph_client,
)

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def test_metagraph():
    print("🔍 Testing MetagraphClient with real testnet...")

    try:
        # Create client for testnet (your actual network)
        async with create_metagraph_client("test") as client:
            # Test 1: Get metagraph info first
            print("\n📊 Getting metagraph info...")
            info = await client.get_metagraph_info()
            print(f"Network: {info.network}")
            print(f"NetUID: {info.netuid}")
            print(f"Total validators: {info.total_validators}")
            print(f"Health score: {info.health_score:.1f}%")

            # Test 2: Discover validators (this is the main test)
            print("\n🔄 Discovering validators...")
            validators = await client.discover_validators()
            print(f"Found {len(validators)} validators")

            # Test 3: Show validator details
            print("\nValidator breakdown:")
            for validator in validators[:5]:  # Show first 5
                print(f"  {validator}")
                print(f"    IP: {validator.ip}:{validator.port}")
                print(f"    Real IP: {validator.has_real_ip}")
                print(f"    Reachable: {validator.is_reachable}")
                print(f"    Status: {validator.status.value}")

            # Test 4: Get submission-ready validators
            submission_validators = await client.get_submission_validators()
            print(f"\n✅ Ready for submission: {len(submission_validators)} validators")

            if submission_validators:
                print("Best validators for submission:")
                for v in submission_validators:
                    print(
                        f"  {v.hotkey_short} - {v.endpoint_url} - Score: {v.priority_score:.1f}"
                    )
            else:
                print("⚠️  No validators ready for submission")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_metagraph())
