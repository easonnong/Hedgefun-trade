// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Sandbox} from "./Sandbox.s.sol";

/// The same v2 rehearsal as Sandbox, with its own book variable for existing fake-dollar operators.
/// Both assets are owner-minted and worthless. This entry point shares all deployment, pricing,
/// trading, and withdrawal checks with Sandbox; a legacy FakeUsdBook is rejected by Sandbox._book().
///
/// forge script script/SandboxFakeUsd.s.sol --tc SandboxFakeUsd --sig "stage(uint256)" 10000000000 --rpc-url publicnode
/// FUSD_SANDBOX=0x.. forge script script/SandboxFakeUsd.s.sol --tc SandboxFakeUsd --sig "launch()" --rpc-url publicnode
contract SandboxFakeUsd is Sandbox {
    function _bookAddress() internal view virtual override returns (address) { return vm.envAddress("FUSD_SANDBOX"); }
    function _bookLabel() internal pure virtual override returns (string memory) { return "FUSD_SANDBOX="; }
}
