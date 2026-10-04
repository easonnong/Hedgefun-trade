"""cc_desk_batch.py: the parts that need no chain. `cast` must be on PATH (it is in CI, after foundry-toolchain)."""
import json, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "emergency"))
import build  # noqa: E402
import cc_desk_batch as cc  # noqa: E402

DESK = "0xC65cBee407eb6aE2e685eA7C2c844cC3c4188EAd"
NVDA = "0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC"
FEED = "0x379EC4f7C378F34a1B47E4F3cbeBCbAC3E8E9F15"
DEAD = "0x000000000000000000000000000000000000dEaD"
# the offer the fork rehearsal executed on 2026-10-01 (280 NVDA, strike 240, 1.80/token, Fri 2026-10-09 16:00 ET, NetShare)
TERMS = [DEAD, NVDA, 280 * 10**18, 240_000000, 504_000000, 1791576000, 1791001541, 1, FEED, 7200, 1000775159164630595]
OFFER_DATA = ("0x39cc22fe000000000000000000000000000000000000000000000000000000000000dead000000000000000000000000d0601ce157db5bdc3162bbac2a2c8af5320d9eec"
              "00000000000000000000000000000000000000000000000f2dc7d47f15600000000000000000000000000000000000000000000000000000000000000e4e1c00"
              "000000000000000000000000000000000000000000000000000000001e0a6e00000000000000000000000000000000000000000000000000000000006ac947c0"
              "000000000000000000000000000000000000000000000000000000006ac083c50000000000000000000000000000000000000000000000000000000000000001"
              "000000000000000000000000379ec4f7c378f34a1b47e4f3cbebcbac3e8e9f150000000000000000000000000000000000000000000000000000000000001c20"
              "0000000000000000000000000000000000000000000000000de377b4760af643")


class Times(unittest.TestCase):
    def test_date_means_the_close_in_new_york(self):
        self.assertEqual(cc.parse_when("2026-10-09", "x"), 1791576000)      # Fri 16:00 EDT = 20:00 UTC
        self.assertEqual(cc.parse_when("2026-12-18", "x"), 1797627600)      # Fri 16:00 EST = 21:00 UTC: the offset follows DST
        self.assertEqual(cc.fmt_when(1791576000), "Fri 2026-10-09 16:00 ET")

    def test_time_is_eastern_unless_an_offset_is_given(self):
        self.assertEqual(cc.parse_when("2026-10-07T16:00", "x"), 1791403200)
        self.assertEqual(cc.parse_when("2026-10-07T20:00+00:00", "x"), 1791403200)
        with self.assertRaises(build.Refuse): cc.parse_when("next friday", "x")


class Units(unittest.TestCase):
    def test_whole_tokens_and_usdg(self):
        self.assertEqual(cc.to_units("280", 18, "size"), 280 * 10**18)
        self.assertEqual(cc.to_units("1.80", 6, "premium"), 1_800000)
        self.assertEqual(cc.to_units("0.5", 18, "size"), 5 * 10**17)

    def test_refuses_dust_zero_and_junk(self):
        for bad, dec in (("1.2345678", 6), ("0", 18), ("-1", 18), ("abc", 6)):
            with self.assertRaises(build.Refuse): cc.to_units(bad, dec, "x")


class Calldata(unittest.TestCase):
    def test_offer_terms_encode_as_the_contract_decoded_them(self):
        c = cc.make_call(DESK, "offer", [TERMS])
        self.assertEqual(c["data"], OFFER_DATA)
        self.assertEqual(c["data"][:10], build.selector(f"offer({cc.TERMS_T})"))

    def test_offer_round_trips_through_decode(self):
        vals = json.loads(build.cast("calldata-decode", "--json", cc.METHODS["offer"][0], OFFER_DATA))
        terms = [build._norm(v) for v in vals[0]]
        self.assertEqual([str(x).lower() for x in terms], [str(x).lower() for x in TERMS])

    def test_safe_ui_sees_the_tuple_with_components(self):
        j = cc.tx_json(cc.make_call(DESK, "offer", [TERMS]))
        self.assertEqual(j["contractMethod"]["name"], "offer")
        t = j["contractMethod"]["inputs"][0]
        self.assertEqual(t["type"], "tuple")
        self.assertEqual([x["name"] for x in t["components"]], [n for n, _ in cc.TERMS_FIELDS])
        self.assertEqual(json.loads(j["contractInputsValues"]["t"])[2], str(280 * 10**18))
        self.assertEqual(j["value"], "0")

    def test_setup_calls(self):
        self.assertEqual(cc.make_call(DESK, "list", [NVDA, FEED, True])["data"],
                         "0xaabd41eb000000000000000000000000d0601ce157db5bdc3162bbac2a2c8af5320d9eec000000000000000000000000379ec4f7c378f34a1b47e4f3cbebcbac3e8e9f15"
                         "0000000000000000000000000000000000000000000000000000000000000001")
        self.assertEqual(cc.make_call(DESK, "setBuyer", [DEAD, True])["data"][:10], build.selector("setBuyer(address,bool)"))
        with self.assertRaises(build.Refuse): cc.make_call(DESK, "setWriter", [DEAD])

    def test_bundle_checksum_is_the_safe_uis(self):
        b = cc.bundle([cc.make_call(DESK, "setWriter", [DEAD, True])], 4663, DEAD, "n", "d")
        self.assertEqual(b["meta"]["checksum"], build.safe_checksum(b))
        b["transactions"][0]["data"] = OFFER_DATA
        self.assertNotEqual(b["meta"]["checksum"], build.safe_checksum(b))


if __name__ == "__main__":
    unittest.main()
