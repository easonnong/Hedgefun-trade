// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {HedgeFunFactory, TreasuryDeployer, TokenDeployer} from "../src/HedgeFunFactory.sol";
import {HedgeFunHook} from "../src/hooks/HedgeFunHook.sol";
import {TradingCalendar} from "../src/TradingCalendar.sol";
import {HedgeFunLaunchRouter} from "../src/HedgeFunLaunchRouter.sol";

/// Deploys the strategy-token launchpad itself: the treasury CREATE2 deployer (needed because the factory's own
/// initcode would blow past EIP-3860 if it embedded the treasury creation code directly), THE hook, and the factory,
/// with a set of defaults already proven end-to-end by `test/StrategyFork.t.sol` (full lot cycle, buyback, launch
/// fee in all three currencies).
///
/// There is one hook for every strategy, because a router's allowlist is per hook address. A V4 hook's permissions
/// are the low 14 bits of its address, so it goes out through the canonical CREATE2 deployer (`0x4e59b4...956C`, which
/// is what forge turns `new X{salt: s}` into when broadcasting) under a salt mined here, in the script, before anything
/// is broadcast: about 16k hashes. The factory binds it in its constructor, in the transaction after. `bind()` is
/// open to whoever calls first, so a stranger who binds the hook in between makes the factory's deployment revert
/// (`AlreadyBound`) -- nothing is lost but gas; run again with HOOK_SALT_START moved on, which lands a different address.
///
/// REHEARSE IT FIRST, against a local fork of mainnet -- this repo's own `DeployNvdaMax.s.sol` lesson: contract-size
/// limits (this factory needed its deployers split out for exactly this reason) and constructor wiring bugs (the
/// str/ split just caught one: an immutable read before assignment across two base constructors) show up in a real
/// deploy, not in a unit or fork TEST run.
///
///   anvil --fork-url https://rpc.mainnet.chain.robinhood.com --chain-id 31337 -p 8545 &
///   forge script script/DeployStrategyLaunchpad.s.sol --rpc-url http://127.0.0.1:8545 --broadcast \
///        --unlocked --sender 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
///
/// (anvil's first account, unlocked by the local node: no key on the command line, in a rehearsal or anywhere else.
/// Always pass --sender: without it the broadcaster guard compares against forge's default sender, not the signer.)
///
/// `--chain-id 31337` is what makes that a rehearsal: on any chain id but 4663 the roles below default to the
/// broadcaster, as they always did. Leave the flag off and the fork reports 4663, the mainnet guards apply, and the
/// rehearsal needs the real Safes in the env -- which is the better rehearsal, once they exist.
///
/// ON CHAIN ID 4663 NOTHING PERMANENT HAS A DEFAULT (audit FA-7). `protocol` is immutable in the factory and copied
/// into every pool it ever registers as its first tax recipient (the owner can move a pool's later, one pool at a time); it used to
/// default to OWNER, which defaulted to the broadcasting key, so one forgotten env var made a hot EOA that
/// recipient. On 4663 the script now refuses to run unless:
///   OWNER           is set, is not the broadcaster, and has code (a Safe)           -- the factory's owner
///   PROTOCOL        is set, is not the broadcaster, and has code (a Safe)           -- immutable, no second chance
///   CALENDAR        is set to an already-deployed calendar (has code), OR
///   CALENDAR_OWNER  is set, is not the broadcaster, and has code (a Safe)           -- owner of the calendar this
///                   script then deploys. That owner can halt every rule priced through the calendar, so it gets
///                   the same treatment as the other two and never silently inherits OWNER.
/// and, on EVERY chain, LP_FEE must be 0 (audit FA-5): an LP fee accrues to the seeded position, which nobody can
/// ever collect from -- not burned, not paid to the treasury, just stranded. The factory now refuses it too; the
/// script check is the earlier, more legible of the two.
///
/// Fork from the chain's own RPC, not `publicnode`: publicnode's free tier refuses `eth_getCode` on the CREATE2
/// deployer proxy (`0x4e59b44...`) as an "archive request" needing a paid token, which fails the rehearsal before
/// the first transaction. The chain's own RPC serves it.
///
/// Mainnet is the same command with --rpc-url robinhood and the operator's own key. NOTHING in this repo should
/// broadcast that for you: read the printed plan, then sign it yourself.
///
/// What it does NOT do, on purpose -- each is a separate decision the owner makes afterward, by hand:
///   - list any stock. Which ticker launches first is a call this script does not make for you; `factory.list(...)`
///     comes after this, once per stock, on a V3 pool.
///   - deploy any `PriceOracle`. `list` takes one per stock; build it on the calendar printed at the end.
///   - call setPublicLaunch(true). Until then only the owner may launch, which is the right default for the very
///     first strategy on a freshly-deployed factory.
///   - launch anything.
contract DeployStrategyLaunchpad is Script {
    address constant PM = 0x8366a39CC670B4001A1121B8F6A443A643e40951;
    address constant V3_FACTORY = 0x1f7d7550B1b028f7571E69A784071F0205FD2EfA;
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;

    uint256 constant RH_MAINNET = 4663;
    /// BEFORE_INITIALIZE | BEFORE_ADD_LIQUIDITY | AFTER_SWAP | AFTER_SWAP_RETURNS_DELTA
    uint160 constant HOOK_FLAGS = 0x2844;

    error NoHookSalt();
    error HookNotWhereMined(address expected, address got);

    error MissingEnv(string name);
    error IsBroadcaster(string name, address who);
    error NotAContract(string name, address who);
    error Is7702Delegation(string name, address who, address delegate);
    error NotASafe(string name, address who);
    error SafeThresholdTooLow(string name, address who, uint256 threshold, uint256 owners);
    error LpFeeMustBeZero(uint256 lpFee, string why);
    error OutOfRange(string name, uint256 value, uint256 max);

    /// @dev every narrowed env var goes through here. A bare `uint16(vm.envOr(...))` WRAPS: SNIPE_SECONDS=300 became 44,
    ///      PROTOCOL_BPS=67536 became 2000 -- values the factory then accepts without a word (audit R5-6).
    function _u(string memory name, uint256 dflt, uint256 max) internal view returns (uint256 v) {
        v = vm.envOr(name, dflt);
        if (v > max) revert OutOfRange(name, v, max);
    }
    string public constant LP_FEE_WHY = "LP_FEE must be 0: fees would strand in the uncollectable seed (FA-5). The factory's _setDefaults refuses it anyway (BadRequest); this just says so before anything is broadcast";

    /// Who ends up holding what. `calendar != 0` means "use this one"; otherwise one is deployed for `calendarOwner`.
    struct Roles { address owner; address protocol; address calendar; address calendarOwner; }

    /// The guards, with every input explicit so a test can drive them without touching the process environment
    /// (`vm.setEnv` is process-wide and forge runs tests in parallel). Address zero means "env var not set".
    /// `view` only because of the `.code.length` reads.
    function resolveRoles(uint256 chainId, address broadcaster, address owner, address protocol, address calendar,
                          address calendarOwner) public view returns (Roles memory r) {
        if (chainId != RH_MAINNET) {
            // rehearsal: the old permissive defaults, so a bare anvil run still works
            r.owner = owner == address(0) ? broadcaster : owner;
            r.protocol = protocol == address(0) ? r.owner : protocol;
            r.calendar = calendar;
            if (calendar == address(0)) r.calendarOwner = calendarOwner == address(0) ? r.owner : calendarOwner;
            return r;
        }
        _requireSafe("OWNER", owner, broadcaster);
        _requireSafe("PROTOCOL", protocol, broadcaster);
        r.owner = owner; r.protocol = protocol;
        if (calendar != address(0)) {
            _requireCode("CALENDAR", calendar);
            r.calendar = calendar;
        } else {
            _requireSafe("CALENDAR_OWNER", calendarOwner, broadcaster);
            r.calendarOwner = calendarOwner;
        }
    }

    function _requireSafe(string memory name, address who, address broadcaster) internal view {
        if (who == address(0)) revert MissingEnv(name);
        if (who == broadcaster) revert IsBroadcaster(name, who);
        _requireCode(name, who);
        // "Has code" was the whole check, and on this chain it does not mean "is a contract". Anvil's second account,
        // whose private key is printed in every Foundry tutorial, carries an EIP-7702 delegation on Robinhood Chain
        // mainnet, so it has 23 bytes of code -- and a dry run naming it OWNER, PROTOCOL and CALENDAR_OWNER passed
        // every guard. So ask the question that was meant: does it answer like a Safe, with more than one signature
        // between a key and the permanent address?
        (bool ok, bytes memory r) = who.staticcall(abi.encodeWithSignature("getThreshold()"));
        if (!ok || r.length != 32) revert NotASafe(name, who);
        uint256 threshold = abi.decode(r, (uint256));
        (ok, r) = who.staticcall(abi.encodeWithSignature("getOwners()"));
        if (!ok || r.length < 64) revert NotASafe(name, who);
        uint256 owners = abi.decode(r, (address[])).length;
        if (threshold == 0 || owners == 0 || threshold > owners) revert NotASafe(name, who);
        // a 1-of-n Safe is an EOA with extra steps. This is a guard against a MISTAKE, not against an operator who
        // wants to cheat it: any contract can answer these two calls. A human still reads the printed plan.
        if (threshold < 2) revert SafeThresholdTooLow(name, who, threshold, owners);
    }

    /// @dev code, and not an EIP-7702 delegation designator (0xef0100 ++ 20-byte delegate): that is an EOA
    function _requireCode(string memory name, address who) internal view {
        bytes memory code = who.code;
        if (code.length == 0) revert NotAContract(name, who);
        if (code.length == 23 && code[0] == 0xef && code[1] == 0x01 && code[2] == 0x00) {
            address delegate;
            assembly { delegate := shr(96, mload(add(code, 35))) }
            revert Is7702Delegation(name, who, delegate);
        }
    }

    /// FA-5, on every chain: there is no rehearsal in which a stranded fee is the thing being rehearsed. Belt and
    /// braces: `HedgeFunFactory._setDefaults` itself reverts on `lpFee != 0`, but as a bare `BadRequest` from inside
    /// the constructor, after the deployers and the hook have already gone out. This refuses first, and says why.
    function checkLpFee(uint256 lpFee) public pure returns (uint24) {
        if (lpFee != 0) revert LpFeeMustBeZero(lpFee, LP_FEE_WHY);
        return 0;
    }

    /// The salt under which `deployer` lands the hook at an address whose low 14 bits are its permission set. Pure:
    /// nothing is sent, so it can run -- and be tested -- before any broadcast.
    /// @dev skips any address that already has code. CREATE2 to an occupied address is a `CreateCollision`, and the
    ///      first salt with the right flags is the same for every run of the same code: a sandbox deploy of this
    ///      commit took salt 4605, so an unskipping miner sent the production deploy to an address already taken.
    function mineHookSalt(address deployer, bytes32 initCodeHash, uint256 start) public view returns (bytes32 salt, address hook) {
        for (uint256 i = start; i < start + 2_000_000; i++) {
            hook = address(uint160(uint256(keccak256(abi.encodePacked(bytes1(0xff), deployer, bytes32(i), initCodeHash)))));
            if (uint160(hook) & 0x3FFF == HOOK_FLAGS && hook.code.length == 0) return (bytes32(i), hook);
        }
        revert NoHookSalt();
    }

    /// The same guards, fed from the environment. An unset var and an empty one both count as missing.
    function resolveRolesFromEnv(address broadcaster) public view returns (Roles memory) {
        return resolveRoles(block.chainid, broadcaster, _envAddr("OWNER"), _envAddr("PROTOCOL"), _envAddr("CALENDAR"),
                            _envAddr("CALENDAR_OWNER"));
    }

    function _envAddr(string memory name) internal view returns (address) {
        string memory v = vm.envOr(name, string(""));
        return bytes(v).length == 0 ? address(0) : vm.parseAddress(v);
    }

    function run() external {
        Roles memory roles = resolveRolesFromEnv(msg.sender);
        address owner = roles.owner;
        address protocol = roles.protocol;
        uint24 lpFee = checkLpFee(vm.envOr("LP_FEE", uint256(0)));

        // proven by the fork suite exactly as written here (NVDA5STR): 1e9 supply, 0.10-1.5%
        // creator-chosen tax, protocol keeps 20% of the stock-side tax with up to 30% more to the creator, a 90%
        // opening sell spike decaying over 120s, 1% execution slippage/deviation bounds, a 3% buy-back impact cap
        // on a 60s cooldown, and a 25 USDG launch fee. All of it is a *default*: changeable per-listing via
        // `setDefaults` for FUTURE launches only, never for one already live.
        HedgeFunFactory.Defaults memory d = HedgeFunFactory.Defaults({
            supply: vm.envOr("SUPPLY", uint256(1_000_000_000e18)),
            lpFee: lpFee,   // always 0, see checkLpFee
            tickSpacing: int24(uint24(_u("TICK_SPACING", 60, 32767))),                    // TickMath.MAX_TICK_SPACING
            minTaxBps: uint16(_u("MIN_TAX_BPS", uint256(100), type(uint16).max)),
            maxTaxBps: uint16(_u("MAX_TAX_BPS", uint256(1500), type(uint16).max)),
            protocolBps: uint16(_u("PROTOCOL_BPS", uint256(2000), type(uint16).max)),
            maxCreatorBps: uint16(_u("MAX_CREATOR_BPS", uint256(3000), type(uint16).max)),
            spikeBps: uint16(_u("SPIKE_BPS", uint256(9000), type(uint16).max)),
            spikeSeconds: uint32(_u("SPIKE_SECONDS", uint256(120), type(uint32).max)),
            sweepTipBps: uint16(_u("SWEEP_TIP_BPS", uint256(50), type(uint16).max)),
            snipeBps: uint16(_u("SNIPE_BPS", uint256(9900), type(uint16).max)),           // a buy in the launch second pays 99%, in tokens that burn
            snipeSeconds: uint8(_u("SNIPE_SECONDS", uint256(3), type(uint8).max)),       // ... falling to the flat tax over 3 s. The launch tx itself is exempt
            bountyBps: uint16(_u("BOUNTY_BPS", uint256(50), type(uint16).max)),
            maxSlippageBps: uint16(_u("MAX_SLIPPAGE_BPS", uint256(100), type(uint16).max)),
            maxDeviationBps: uint16(_u("MAX_DEVIATION_BPS", uint256(50), type(uint16).max)),
            maxBuybackImpactBps: uint16(_u("MAX_BUYBACK_IMPACT_BPS", uint256(300), type(uint16).max)),
            buybackCooldown: uint32(_u("BUYBACK_COOLDOWN", uint256(60), type(uint32).max)),
            minLotUsdg: vm.envOr("MIN_LOT_USDG", uint256(5e6)),
            buybackChunkUsdg: vm.envOr("BUYBACK_CHUNK_USDG", uint256(500e6)),
            sellChunkUsdg: vm.envOr("SELL_CHUNK_USDG", uint256(2_000e6)),           // the most one takeProfit/stopLoss call sells
            launchFeeCurrency: HedgeFunFactory.FeeCurrency(vm.envOr("LAUNCH_FEE_CURRENCY", uint256(2))),   // 2 = Usdg
            launchFeeAmount: vm.envOr("LAUNCH_FEE_AMOUNT", uint256(25e6))
        });

        console2.log("=== strategy-token launchpad ===");
        console2.log("chain id", block.chainid, block.chainid == 4663 ? "(Robinhood Chain -- mainnet OR a fork of it)" : "");
        console2.log("owner   ", owner);
        console2.log("protocol", protocol, "(IMMUTABLE in the factory: launch fees, and the tax recipient every pool is born with)");
        if (roles.calendar != address(0)) console2.log("calendar", roles.calendar, "(existing, not deployed here)");
        else console2.log("calendar owner", roles.calendarOwner, "(a TradingCalendar is deployed for it)");

        (bytes32 hookSalt, address hookAt) = mineHookSalt(CREATE2_FACTORY,
            keccak256(abi.encodePacked(type(HedgeFunHook).creationCode, abi.encode(PM))), vm.envOr("HOOK_SALT_START", uint256(0)));
        console2.log("hook    ", hookAt, "(mined; ONE for every strategy -- the address a router allowlists)");
        console2.logBytes32(hookSalt);

        vm.startBroadcast();

        TreasuryDeployer treasuryDeployer = new TreasuryDeployer();
        TokenDeployer tokenDeployer = new TokenDeployer();
        HedgeFunHook hook = new HedgeFunHook{salt: hookSalt}(IPoolManager(PM));
        if (address(hook) != hookAt || uint160(address(hook)) & 0x3FFF != HOOK_FLAGS) revert HookNotWhereMined(hookAt, address(hook));
        // binds the hook (and the deployer). Reverts if anyone got to `hook.bind()` first.
        HedgeFunFactory factory = new HedgeFunFactory(
            owner, PM, V3_FACTORY, USDG, protocol,
            address(treasuryDeployer), address(tokenDeployer), address(hook), d
        );

        address calendar = roles.calendar;
        if (calendar == address(0)) calendar = address(new TradingCalendar(roles.calendarOwner));
        // periphery: no owner, no state, no privilege. Launch + the launcher's first buy + a first lot, in one tx.
        HedgeFunLaunchRouter launchRouter = new HedgeFunLaunchRouter(factory);

        vm.stopBroadcast();

        console2.log("treasuryDeployer  ", address(treasuryDeployer));
        console2.log("tokenDeployer     ", address(tokenDeployer));
        console2.log("hook              ", address(hook), "bound to", hook.factory());
        console2.log("factory           ", address(factory));
        console2.log("calendar          ", calendar);
        console2.log("launchRouter      ", address(launchRouter));
        console2.log("--- read back ---");
        _readBack(factory);
        console2.log("");
        console2.log("NEXT, each a separate decision and a separate signature by the OWNER above:");
        console2.log("  0. per stock: deploy PriceOracle(stock, stockFeed, usdgFeed, calendar, maxStockAge, maxUsdgAge)");
        console2.log("     on the calendar above. Nothing in this script does that.");
        console2.log("  1. factory.list(stock, oracle, v3Pool, openPriceE18, true). Run script/V3Survey.s.sol");
        console2.log("     for the stocks that qualify: a real USDG book, and a ring that serves the 600s window.");
        console2.log("  1b. factory.setBandCeiling(stock, bps) -- only for a stock replayed with tools/band_backtest.py, and");
        console2.log("     NEVER ABOVE 10 (the contract allows 200; nothing measured needs more). First batch, DEPLOYMENT.md 7.4:");
        console2.log("     CRCL 10; USAR, GME, AMZN, META 5. Every other listing stays at 0 = Chainlink-only. A band lets a");
        console2.log("     stale feed be pulled by the pool, and a pinned pool picks the price inside it (AUDIT.md TR-1):");
        console2.log("     a larger number buys no more open hours, only a wider pin.");
        console2.log("  2. factory.setPublicLaunch(true), once ready for anyone (not just the owner) to launch");
        console2.log("  3. launch(request, terms) -- from a front end, or script/LaunchStrategy.s.sol. Nothing to mine:");
        console2.log("     the hook above serves every launch. factory.predict(request) answers where the token and the");
        console2.log("     treasury land and the `terms` to hand back, so a default moved in between reverts Restated.");
    }

    /// @dev EVERY default, by name, as the factory now holds it: the operator signs what this prints. Several of these
    ///      stop every launch, or tax every buy at 99%, without anything reverting at deploy time.
    function _readBack(HedgeFunFactory factory) internal view {
        HedgeFunFactory.Defaults memory d = factory.getDefaults();
        console2.log("supply:", d.supply);
        console2.log("lpFee:", d.lpFee);
        console2.log("tickSpacing:", d.tickSpacing);
        console2.log("minTaxBps / maxTaxBps:", d.minTaxBps, d.maxTaxBps);
        console2.log("protocolBps / maxCreatorBps:", d.protocolBps, d.maxCreatorBps);
        console2.log("spikeBps / spikeSeconds:", d.spikeBps, d.spikeSeconds);
        console2.log("snipeBps / snipeSeconds:", d.snipeBps, d.snipeSeconds);
        console2.log("sweepTipBps / bountyBps:", d.sweepTipBps, d.bountyBps);
        console2.log("maxSlippageBps / maxDeviationBps:", d.maxSlippageBps, d.maxDeviationBps);
        console2.log("maxBuybackImpactBps / buybackCooldown:", d.maxBuybackImpactBps, d.buybackCooldown);
        console2.log("minLotUsdg:", d.minLotUsdg);
        console2.log("buybackChunkUsdg:", d.buybackChunkUsdg);
        console2.log("sellChunkUsdg:", d.sellChunkUsdg);
        console2.log("launch fee currency (0 None/1 Native/2 Usdg/3 Stock):", uint256(d.launchFeeCurrency));
        console2.log("launch fee amount:", d.launchFeeAmount);
        console2.log("publicLaunch:", factory.publicLaunch());
    }
}
