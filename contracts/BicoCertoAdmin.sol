// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "contracts/interfaces/IBicoCertoAdmin.sol";
import "contracts/interfaces/IBicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoDisputeResolver.sol";

contract BicoCertoAdmin is IBicoCertoAdmin {
    IBicoCertoRegistry public registry;
    address public owner;
    uint256 public platformFeePercent;
    bool public paused;

    constructor(address _registryAddress, uint256 _initialPlatformFeePercent) {
        registry = IBicoCertoRegistry(_registryAddress);
        owner = msg.sender;
        platformFeePercent = _initialPlatformFeePercent;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Apenas owner");
        _;
    }

    function updatePlatformFee(uint256 _newFee) external onlyOwner {
        require(_newFee <= 10, "Taxa muito alta"); // Máximo 10%
        uint256 oldFee = platformFeePercent;
        platformFeePercent = _newFee;
        emit PlatformFeeUpdated(oldFee, _newFee);
    }

    function togglePause() external onlyOwner {
        paused = !paused;
        if (paused) {
            emit Paused(msg.sender);
        } else {
            emit Unpaused(msg.sender);
        }
    }

    function addArbitrator(address _arbitrator) external onlyOwner {
        IBicoCertoDisputeResolver(registry.getDisputeResolver()).addArbitrator(_arbitrator);
    }

    function removeArbitrator(address _arbitrator) external onlyOwner {
        IBicoCertoDisputeResolver(registry.getDisputeResolver()).removeArbitrator(_arbitrator);
    }

    function getPlatformFeePercent() external view returns (uint256) {
        return platformFeePercent;
    }

    function isPaused() external view returns (bool) {
        return paused;
    }
}


