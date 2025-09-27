// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "contracts/interfaces/IBicoCertoPaymentGateway.sol";
import "contracts/interfaces/IBicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoAdmin.sol";

contract BicoCertoPaymentGateway is IBicoCertoPaymentGateway {
    IBicoCertoRegistry public registry;

    address public platformWallet;
    mapping(address => uint256) public pendingWithdrawals;

    constructor(address _registryAddress, address _platformWallet) {
        registry = IBicoCertoRegistry(_registryAddress);
        platformWallet = _platformWallet;
    }

    modifier notPaused() {
        require(!IBicoCertoAdmin(registry.getAdmin()).isPaused(), "Contrato pausado");
        _;
    }

    function releasePayment(bytes32 _jobId, address _provider, uint256 _amount, uint256 _platformFee) external notPaused {
        // Only callable by JobManager or DisputeResolver
        // Add access control if needed
        pendingWithdrawals[platformWallet] += _platformFee;
        pendingWithdrawals[_provider] += _amount;

        emit PaymentReleased(_jobId, _provider, _amount);
    }

    function withdraw(address _user) payable external notPaused {
        uint256 amount = pendingWithdrawals[_user];
        require(amount > 0, "Sem saldo para saque");

        pendingWithdrawals[_user] = 0;

        (bool success, ) = _user.call{value: amount}("");
        require(success, "Transferencia falhou");
    }

    function refundClient(bytes32 _jobId, address _client, uint256 _amount) external notPaused {
        // Only callable by JobManager or DisputeResolver
        // Add access control if needed
        pendingWithdrawals[_client] += _amount;

        emit RefundIssued(_jobId, _client, _amount);
    }

    function getPendingWithdrawals(address _user) external view returns (uint256) {
        return pendingWithdrawals[_user];
    }

    receive() external payable {
        // Accept ETH for the platform
    }
    
    fallback() external payable {
        // Accept ETH for the platform
    }
}


