"""Offline profile guards: no compiler artifacts, cast binary, RPC or wallet required."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("treasury_profile_config", ROOT / "tools/treasury_profile_config.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def address(n):
    return f"0x{n:040x}"


def fixture_cast(operation, *args):
    # Test-only digest/ABI stand-in. Cryptographic bytecode commitments are tested
    # against actual deployed bytecode in the Solidity registration/fork suite.
    if operation == "keccak":
        return "0x" + hashlib.sha256(bytes.fromhex(args[0].removeprefix("0x"))).hexdigest()
    if operation == "abi-encode":
        return "0x" + "".join(f"{int(a, 16) if isinstance(a, str) and a.startswith('0x') else int(a):064x}"
                               for a in args[1:])
    raise AssertionError(f"unexpected command {operation}")


def profile():
    return {"mode": "strategy", "strategy": "rebalance", "execution": "continuous",
            "targetPercent": "50", "bandPercent": "5", "buyPercent": "20", "sellPercent": "30",
            "dailyPercent": "50", "profitToBuybackPercent": "25", "cooldownSeconds": 600}


class ProfileSerializationTest(unittest.TestCase):
    def test_schema_three_golden_words_keep_all_reserved_bits_zero(self):
        c = TOOL.engine_config(profile(), "0x" + "AB" * 32)
        self.assertEqual((c["schema"], c["engineVersion"], c["policyKey"]), (3, 1, "0x" + "ab" * 32))
        self.assertEqual(c["words"], ["0x" + "09c40000025801f41388".zfill(64),
                                     "0x" + "0bb807d0".zfill(64), "0x" + "1388".zfill(64)])
        self.assertEqual(int(c["words"][0], 16) >> 80, 0)
        self.assertEqual(int(c["words"][1], 16) >> 32, 0)

    def test_directional_daily_limits_are_distinct_and_exclusive(self):
        p = profile()
        del p["dailyPercent"]
        p.update(dailyBuyPercent="50", dailySellPercent="20")
        c = TOOL.engine_config(p, "0x" + "01" * 32)
        self.assertEqual(int(c["words"][2], 16), 5000 | 2000 << 16)
        for bad in (dict(p, dailyPercent="50"), dict(p, dailyBuyPercent="0"),
                    dict(p, dailySellPercent="0"), dict(p, dailySellPercent="100.01"),
                    {k: v for k, v in p.items() if k != "dailySellPercent"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                TOOL.engine_config(bad, "0x" + "01" * 32)

    def test_decimal_strings_have_exact_basis_point_precision(self):
        for value, expected in (("0.01", 1), ("0.10", 10), ("19.99", 1999), ("100", 10000)):
            with self.subTest(value=value):
                self.assertEqual(TOOL.bps(value, "percentage"), expected)
        for value in (0.01, 20, True, "1e2", "20.001", "-1", "100.01", "2000000000", "20%"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                TOOL.bps(value, "percentage")

    def test_input_asset_percentages_need_not_be_below_daily_percentage(self):
        p = profile()
        p.update(buyPercent="100", sellPercent="100", dailyPercent="0.01")
        c = TOOL.engine_config(p, "0x" + "01" * 32)
        self.assertEqual(int(c["words"][1], 16), 0x27102710)
        self.assertEqual(int(c["words"][2], 16), 1)

    def test_invalid_configuration_is_refused_before_any_readback(self):
        cases = (("targetPercent", "19.99"), ("targetPercent", "90.01"), ("bandPercent", "50"),
                 ("buyPercent", "0"), ("sellPercent", "0"), ("dailyPercent", "0"),
                 ("profitToBuybackPercent", "100.01"), ("cooldownSeconds", 599),
                 ("cooldownSeconds", 2**32), ("cooldownSeconds", True))
        for field, value in cases:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                TOOL.engine_config(dict(profile(), **{field: value}), "0x" + "01" * 32)

    def test_legacy_amounts_raw_words_and_unimplemented_modes_are_not_silent_aliases(self):
        cases = [dict(profile(), maxTradeUsdg=2000_000_000), dict(profile(), words=[0, 20, 50]),
                 dict(profile(), kind=2), dict(profile(), mode="buyback"),
                 dict(profile(), strategy="price", execution="single"),
                 dict(profile(), strategy="price", execution="cycle")]
        for p in cases:
            with self.subTest(profile=p), self.assertRaises(ValueError):
                TOOL.engine_config(p, "0x" + "01" * 32)
        for key in ("0x" + "00" * 32, "0x1234", "1", None):
            with self.subTest(key=key), self.assertRaises(ValueError):
                TOOL.engine_config(profile(), key)


class FakeReadback:
    def __init__(self):
        self.responses = {}
        self.codes = {}

    def words(self, target, signature, *args):
        return list(self.responses[(target, signature, args)])

    def code(self, target):
        return self.codes[target]


class RegistrationIdentityTest(unittest.TestCase):
    def setUp(self):
        self.factory, self.registry, self.controller, self.policy = map(address, (1, 2, 3, 4))
        self.a, self.b, self.owner = map(address, (5, 6, 7))
        self.reader = FakeReadback()
        self.proxy_hash = fixture_cast("keccak", "0x606100")
        self.policy_hash = fixture_cast("keccak", "0x606200")
        self.dependencies, self.audit = 8, 9
        commitment = fixture_cast("abi-encode", "unused signature", self.policy, self.policy_hash,
                                  1, 3, 3, 400_000, 160, self.dependencies, self.audit)
        self.key = fixture_cast("keccak", commitment)
        r = self.reader.responses
        r[self.factory, "treasuryDeployer()", ()] = [2]
        r[self.registry, "factory()", ()] = [1]
        r[self.registry, "kindManifest(uint8)", (4,)] = [1, 3, int(self.proxy_hash, 16), 3]
        r[self.registry, "kinds(uint8)", (4,)] = [5, 6]
        r[self.registry, "policy(bytes32)", (self.key,)] = [4, int(self.policy_hash, 16), 1, 3, 400_000, 160, 3, 1]
        r[self.registry, "upgradeController()", ()] = [3]
        r[self.controller, "UPGRADE_DELAY()", ()] = [172800]
        r[self.controller, "owner()", ()] = r[self.factory, "owner()", ()] = [7]
        r[self.registry, "policyDependencyManifestHash(bytes32)", (self.key,)] = [self.dependencies]
        r[self.registry, "policyAuditManifestHash(bytes32)", (self.key,)] = [self.audit]
        self.template = "0x7f" + "00" * 32 + "00"
        self.reader.codes = {self.a: "0x60", self.b: "0x6100", self.policy: "0x606200",
                             self.controller: "0x7f" + f"{2:064x}" + "00"}
        # Keep exact runtime comparison active, using a minimal constructor
        # immutable template instead of depending on a prior forge build.
        self.artifacts = mock.patch.object(TOOL, "artifact_bytecode", return_value=self.template)
        self.artifacts.start()
        self.addCleanup(self.artifacts.stop)

        def infrastructure(reader, factory, registry, controller, keccak):
            self.assertEqual((factory, registry, controller), (self.factory, self.registry, self.controller))
            TOOL.verify_runtime(reader, controller, "V2TreasuryUpgradeController", {1: int(registry, 16)},
                                fixture_cast("keccak", self.template), keccak)

        self.infrastructure = mock.patch.object(TOOL, "verify_infrastructure", side_effect=infrastructure)
        self.verify_infrastructure = self.infrastructure.start()
        self.addCleanup(self.infrastructure.stop)

    def verify(self):
        return TOOL.verify_registration(self.reader, self.factory, 4, self.key,
                                        self.proxy_hash, self.policy_hash, fixture_cast)

    def test_valid_profile_is_bound_to_registry_code_and_policy_evidence(self):
        result = self.verify()
        self.assertEqual(result["profile"], "strategy/rebalance/continuous")
        self.assertEqual((result["kind"], result["policyKey"], result["registry"]), (4, self.key, self.registry))
        self.assertEqual(result["auditManifestHash"], "0x" + f"{9:064x}")
        self.verify_infrastructure.assert_called_once()

    def test_kind_and_policy_schema_mixups_are_rejected(self):
        for field, index, value in (("kindManifest(uint8)", 1, 1), ("kindManifest(uint8)", 3, 1),
                                    ("policy(bytes32)", 3, 2), ("policy(bytes32)", 4, 500_000)):
            args = (4,) if field == "kindManifest(uint8)" else (self.key,)
            row = self.reader.responses[self.registry, field, args]
            old = row[index]
            row[index] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.verify()
            row[index] = old

    def test_disabled_policy_or_replaced_runtime_cannot_be_selected(self):
        row = self.reader.responses[self.registry, "policy(bytes32)", (self.key,)]
        row[-1] = 0
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.verify()
        row[-1] = 1
        self.reader.codes[self.policy] = "0x606300"
        with self.assertRaisesRegex(ValueError, "policy runtime"):
            self.verify()

    def test_same_manifest_hash_does_not_mask_replaced_creation_chunks(self):
        self.reader.codes[self.b] = "0x6200"
        with self.assertRaisesRegex(ValueError, "creation code"):
            self.verify()

    def test_matching_delay_and_owner_getters_do_not_mask_fake_controller_runtime(self):
        self.reader.codes[self.controller] = "0x60006000"
        with self.assertRaisesRegex(ValueError, "runtime differs"):
            self.verify()

    def test_retargeted_controller_deployer_is_rejected_even_with_expected_getters(self):
        self.reader.codes[self.controller] = "0x7f" + f"{99:064x}" + "00"
        with self.assertRaisesRegex(ValueError, "runtime differs"):
            self.verify()

    def test_nonzero_evidence_must_still_match_the_policy_key(self):
        self.reader.responses[self.registry, "policyAuditManifestHash(bytes32)", (self.key,)] = [10]
        with self.assertRaisesRegex(ValueError, "does not commit"):
            self.verify()

    def test_numeric_kind_must_not_overflow_or_accept_boolean_alias(self):
        for kind in (0, 255, 256, -1, True, "4"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                TOOL.verify_registration(self.reader, self.factory, kind, self.key,
                                         self.proxy_hash, self.policy_hash, fixture_cast)


class RuntimeBindingTest(unittest.TestCase):
    def test_all_immutable_references_are_bound_without_altering_instruction_bytes(self):
        template = "0x7f" + "00" * 32 + "7f" + "00" * 32 + "00"
        expected = "0x7f" + f"{123:064x}" + "7f" + f"{456:064x}" + "00"
        self.assertEqual(TOOL.bound_runtime(template, {1: 123, 34: 456}), expected)
        self.assertEqual(template.count("7f"), 2)

    def test_stale_out_of_bounds_or_already_populated_offsets_fail_closed(self):
        for code, bindings in (("0x7f" + "00" * 32, {0: 1}),
                               ("0x7f" + "00" * 32, {2: 1}),
                               ("0x60" + "00" * 32, {1: 1}),
                               ("0x7f" + f"{1:064x}", {1: 2}),
                               ("0x7f" + "00" * 32, {1: 2**256})):
            with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                TOOL.bound_runtime(code, bindings)

    def test_compiler_template_change_is_rejected_before_runtime_comparison(self):
        reader = FakeReadback()
        with mock.patch.object(TOOL, "artifact_bytecode", return_value="0x6000"):
            with self.assertRaisesRegex(ValueError, "compiler template"):
                TOOL.verify_runtime(reader, address(1), "Controller", {}, "0x" + "11" * 32, fixture_cast)

    def test_readback_keeps_every_call_on_the_selected_block(self):
        with mock.patch.object(TOOL, "cast", return_value="0x" + f"{172800:064x}") as cast:
            self.assertEqual(TOOL.Readback("https://example.invalid", 123).words(address(1), "UPGRADE_DELAY()"), [172800])
            cast.assert_called_once_with("call", address(1), "UPGRADE_DELAY()", "--rpc-url", "https://example.invalid",
                                         "--block", 123)
        for malformed in ("172800", "0x", "0x01", "0x" + "gg" * 32):
            with mock.patch.object(TOOL, "cast", return_value=malformed), self.assertRaises(ValueError):
                TOOL.Readback("https://example.invalid", 123).words(address(1), "UPGRADE_DELAY()")


if __name__ == "__main__":
    unittest.main()
