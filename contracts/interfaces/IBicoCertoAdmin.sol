// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IBicoCertoAdmin {
    event PlatformFeeUpdated(uint256 oldFee, uint256 newFee);
    event Paused(address account);
    event Unpaused(address account);

    function updatePlatformFee(uint256 _newFee) external;
    function togglePause() external;
    function getPlatformFeePercent() external view returns (uint256);
    function isPaused() external view returns (bool);
}

