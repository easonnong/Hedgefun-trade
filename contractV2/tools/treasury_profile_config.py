#!/usr/bin/env python3
"""Prepare (never send) a named treasury profile after checking its live registry identity.

The first converged profile is strategy / rebalance / continuous, schema 3. Price
single/cycle and percentage buyback are deliberately unavailable, not aliases for
older behavior. Requires the local candidate build and cast; all RPC calls are reads.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "strategy/rebalance/continuous"
PROXY = "HedgeFunV2TradablePercentEngineTreasury"
POLICY = "V2TradablePercentRebalancePolicy"


def hex_value(value, size, name):
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{%d}" % (size * 2), value):
        raise ValueError(f"{name} must be {size} bytes of hex")
    if int(value, 16) == 0:
        raise ValueError(f"{name} must not be zero")
    return value.lower()


def bps(value, name):
    # Decimal strings prevent float rounding, exponent notation, negative values
    # and accidentally passing an old USDG raw-unit amount as a percentage.
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,3}(?:\.\d{1,2})?", value):
        raise ValueError(f"{name} must be a percentage string with at most two decimals")
    whole, _, fraction = value.partition(".")
    result = int(whole) * 100 + int(fraction.ljust(2, "0") or "0")
    if result > 10_000:
        raise ValueError(f"{name} exceeds 100%")
    return result


def engine_config(profile, policy_key):
    fields = {"mode", "strategy", "execution", "targetPercent", "bandPercent",
              "buyPercent", "sellPercent", "profitToBuybackPercent", "cooldownSeconds"}
    if not isinstance(profile, dict) or set(profile) not in (
            fields | {"dailyPercent"}, fields | {"dailyBuyPercent", "dailySellPercent"}):
        raise ValueError("profile must contain exactly the documented fields; legacy USDG caps are not accepted")
    if (profile["mode"], profile["strategy"], profile["execution"]) != ("strategy", "rebalance", "continuous"):
        raise ValueError("only strategy/rebalance/continuous is implemented by this adapter")
    target, band, buy, sell, payout = [bps(profile[k], k) for k in (
        "targetPercent", "bandPercent", "buyPercent", "sellPercent", "profitToBuybackPercent")]
    if "dailyPercent" in profile:
        daily_buy = daily_sell = bps(profile["dailyPercent"], "dailyPercent")
        daily_word = daily_buy  # Legacy encoding: same percentage for each direction.
    else:
        daily_buy = bps(profile["dailyBuyPercent"], "dailyBuyPercent")
        daily_sell = bps(profile["dailySellPercent"], "dailySellPercent")
        daily_word = daily_buy | daily_sell << 16
    cooldown = profile["cooldownSeconds"]
    if type(cooldown) is not int or not 600 <= cooldown <= 2**32 - 1:
        raise ValueError("cooldownSeconds must be an integer between 600 and uint32.max")
    if not 2000 <= target <= 9000 or band >= target or target + band >= 10000:
        raise ValueError("target must be 20–90%; band must stay strictly inside 0–100% allocation")
    if min(buy, sell, daily_buy, daily_sell) == 0:
        raise ValueError("buy, sell and daily percentages must be positive")
    return {"schema": 3, "engineVersion": 1, "policyKey": hex_value(policy_key, 32, "policyKey"),
            "words": [f"0x{x:064x}" for x in (target | band << 16 | cooldown << 32 | payout << 64,
                                              buy | sell << 16, daily_word)]}


def cast(*args):
    return subprocess.check_output(["cast", *map(str, args)], text=True).strip()


class Readback:
    def __init__(self, rpc, block):
        self.rpc, self.block = rpc, block

    def words(self, target, signature, *args):
        raw = cast("call", target, signature, *args, "--rpc-url", self.rpc, "--block", self.block)
        if not re.fullmatch(r"0x(?:[0-9a-fA-F]{64})+", raw):
            raise ValueError(f"malformed readback: {signature}")
        return [int(raw[i:i + 64], 16) for i in range(2, len(raw), 64)]

    def code(self, address):
        return cast("code", address, "--rpc-url", self.rpc, "--block", self.block)


def address_word(value):
    if not 0 < value < 2**160:
        raise ValueError("invalid address in readback")
    return f"0x{value:040x}"


def artifact_bytecode(name, member):
    artifact = json.loads((ROOT / "out" / (name + ".sol") / (name + ".json")).read_text())
    code = artifact[member]["object"]
    if not re.fullmatch(r"0x[0-9a-fA-F]+", code) or len(code) % 2:
        raise ValueError(f"{name}: compile the candidate before preparing a profile")
    return code


def bound_runtime(code, bindings):
    data = bytearray.fromhex(code.removeprefix("0x"))
    for offset, value in bindings.items():
        if (offset <= 0 or offset + 32 > len(data) or data[offset - 1] != 0x7f
                or any(data[offset:offset + 32]) or not 0 <= value < 2**256):
            raise ValueError("stale or overlapping immutable runtime offsets")
        data[offset:offset + 32] = value.to_bytes(32, "big")
    return "0x" + data.hex()


def verify_runtime(reader, address, name, bindings, template_hash, keccak=cast):
    template = artifact_bytecode(name, "deployedBytecode")
    if keccak("keccak", template).lower() != template_hash:
        raise ValueError(f"{name}: compiler template differs from reviewed release")
    expected = bound_runtime(template, bindings)
    if reader.code(address).lower() != expected.lower():
        raise ValueError(f"{name}: runtime differs from reviewed release")


def verify_infrastructure(reader, factory, registry, controller, keccak=cast):
    # Same complete immutable binding as the Solidity publication guard. Do not
    # replace these comparisons with a few getters or operator-supplied hashes.
    groups = {"poolManager()": (0x06ea, 0x0dcc, 0x0e83, 0x0f72, 0x0fe5, 0x1077, 0x19f4),
              "v3Factory()": (0x0475, 0x15c0), "usdg()": (0x078e, 0x15ef, 0x19c4, 0x37e1),
              "protocol()": (0x0536, 0x1cc6, 0x370f, 0x382e),
              "treasuryDeployer()": (0x027e, 0x07f4, 0x0951, 0x1dab, 0x22d9),
              "tokenDeployer()": (0x02b1, 0x0a0d, 0x2234),
              "hook()": (0x04a8, 0x23e9, 0x2567, 0x3996, 0x3a11),
              "curveDeployer()": (0x05a9, 0x0894, 0x1bfb, 0x1e57, 0x2820, 0x29ec, 0x340a, 0x34b9, 0x35b8, 0x3865)}
    bindings = {}
    addresses = {}
    for getter, offsets in groups.items():
        value = reader.words(factory, getter)[0]
        addresses[getter] = address_word(value)
        bindings.update({offset: value for offset in offsets})
    verify_runtime(reader, factory, "HedgeFunV2Factory", bindings,
        "0x89c15b5927042e7ad12d61494556be1e3ad27e2f277ea6a2928d853dd15e850d", keccak)
    curve = addresses["curveDeployer()"]
    if address_word(reader.words(curve, "factory()")[0]) != factory:
        raise ValueError("graduation module is not bound to factory")
    curve_chunk = address_word(reader.words(curve, "curveChunk()")[0])
    vault_chunk = address_word(reader.words(curve, "vaultChunk()")[0])
    verify_runtime(reader, curve, "CurveDeployer",
        {0x0952: int(curve, 16), 0x0d05: int(curve, 16), 0x014d: int(curve_chunk, 16),
         0x1175: int(curve_chunk, 16), 0x01c4: int(vault_chunk, 16), 0x08b7: int(vault_chunk, 16)},
        "0xdc029369e5848c68a2587b5ea648ca5332feca7243a82720529d2824a1767a64", keccak)
    if (keccak("keccak", reader.code(curve_chunk)).lower()
            != "0xf9300a4b32d609e484af5bb208cc46000f4e83f6b57bc7f19f0b5c22f2a43f3c"
            or keccak("keccak", reader.code(vault_chunk)).lower()
            != "0xe0b01f54fd3d486753adada93bee53dc2602c494ed2faba0144215b58a2d73f0"):
        raise ValueError("graduation creation code differs from reviewed release")
    trigger = int(keccak("keccak", artifact_bytecode("HedgeFunV2UpgradeableTreasury", "bytecode")), 16)
    verify_runtime(reader, registry, "V2TreasuryDeployer",
        {1335: trigger, 7163: trigger, 975: int(controller, 16)},
        "0xb1b1adc4d2960d06e0eaa957fba812db587e4c8a701b342a027854b6425cacb7", keccak)
    verify_runtime(reader, controller, "V2TreasuryUpgradeController", {1856: int(registry, 16)},
        "0x6506bf8c847967c042988fa140a0673ffc0e8338e300850707a0d06f670bc930", keccak)


def verify_registration(reader, factory, kind, policy_key, proxy_hash, policy_hash, keccak=cast):
    factory = hex_value(factory, 20, "factory")
    policy_key = hex_value(policy_key, 32, "policyKey")
    if type(kind) is not int or not 0 < kind < 255:
        raise ValueError("kind must be an appended registry ID, not a product name")
    registry = address_word(reader.words(factory, "treasuryDeployer()")[0])
    if address_word(reader.words(registry, "factory()")[0]) != factory:
        raise ValueError("registry is not bound to this factory")
    if reader.words(registry, "kindManifest(uint8)", kind) != [1, 3, int(proxy_hash, 16), 3]:
        raise ValueError("kind is not this candidate's upgradeable schema-3 profile")
    chunks = reader.words(registry, "kinds(uint8)", kind)
    if len(chunks) != 2:
        raise ValueError("invalid kind chunks")
    raw = "0x" + "".join(reader.code(address_word(a)).removeprefix("0x") for a in chunks)
    if keccak("keccak", raw).lower() != proxy_hash.lower():
        raise ValueError("registered creation code differs from candidate build")
    manifest = reader.words(registry, "policy(bytes32)", policy_key)
    if len(manifest) != 8:
        raise ValueError("invalid policy readback")
    policy = address_word(manifest[0])
    if manifest[1:] != [int(policy_hash, 16), 1, 3, 400_000, 160, 3, 1]:
        raise ValueError("policy is disabled or its identity/limits differ from the candidate")
    if keccak("keccak", reader.code(policy)).lower() != policy_hash.lower():
        raise ValueError("policy runtime differs from the candidate build")
    controller = address_word(reader.words(registry, "upgradeController()")[0])
    verify_infrastructure(reader, factory, registry, controller, keccak)
    if (reader.words(controller, "UPGRADE_DELAY()") != [172800]
            or reader.words(controller, "owner()") != reader.words(factory, "owner()")):
        raise ValueError("upgrade authority or delay is not the reviewed configuration")
    dependencies = reader.words(registry, "policyDependencyManifestHash(bytes32)", policy_key)[0]
    audit = reader.words(registry, "policyAuditManifestHash(bytes32)", policy_key)[0]
    if not dependencies or not audit:
        raise ValueError("policy manifest commitments are missing")
    commitment = keccak("abi-encode", "f(address,bytes32,uint32,uint32,uint256,uint32,uint16,bytes32,bytes32)",
        policy, policy_hash, 1, 3, 3, 400_000, 160, f"0x{dependencies:064x}", f"0x{audit:064x}")
    if keccak("keccak", commitment).lower() != policy_key:
        raise ValueError("policy key does not commit to its returned metadata and evidence")
    return {"profile": PROFILE, "factory": factory, "registry": registry, "kind": kind,
            "creationCodeHash": proxy_hash, "policy": policy, "policyKey": policy_key,
            "policyRuntimeCodeHash": policy_hash, "upgradeController": controller,
            "dependencyManifestHash": f"0x{dependencies:064x}", "auditManifestHash": f"0x{audit:064x}"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("rpc-url", "factory", "policy-key", "creator", "symbol", "input"):
        parser.add_argument("--" + arg, required=True)
    parser.add_argument("--kind", required=True, type=int)
    parser.add_argument("--nonce", required=True, type=int)
    args = parser.parse_args()
    if not 0 <= args.nonce < 2**96:
        raise ValueError("nonce is outside uint96")
    creator = hex_value(args.creator, 20, "creator")
    if not args.symbol or len(args.symbol.encode()) > 32:
        raise ValueError("symbol must contain 1–32 bytes")
    config = engine_config(json.loads(Path(args.input).read_text()), args.policy_key)
    block = int(cast("block-number", "--rpc-url", args.rpc_url))
    reader = Readback(args.rpc_url, block)
    binding = verify_registration(reader, args.factory, args.kind, config["policyKey"],
        cast("keccak", artifact_bytecode(PROXY, "bytecode")),
        cast("keccak", artifact_bytecode(POLICY, "deployedBytecode")))
    words = "[" + ",".join(config["words"]) + "]"
    encoded = f"(3,1,{config['policyKey']},{words})"
    data = cast("calldata", "setEngineConfig(string,uint96,uint8,(uint32,uint32,bytes32,bytes32[3]))",
                args.symbol, args.nonce, args.kind, encoded)
    # eth_call only: validates the creator's selection at this block, without storing it or launching.
    cast("call", binding["registry"], "--data", data, "--from", creator, "--rpc-url", args.rpc_url, "--block", block)
    print(json.dumps({"chainId": int(cast("chain-id", "--rpc-url", args.rpc_url)), "block": block,
        "binding": binding, "engineConfig": config,
        "transaction": {"from": creator, "to": binding["registry"], "data": data, "value": "0"},
        "status": "selection simulated, not sent; factory launch still requires a fresh prediction and simulation"}, indent=2))


if __name__ == "__main__":
    main()
