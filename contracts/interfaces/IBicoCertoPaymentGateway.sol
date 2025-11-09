// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IBicoCertoPaymentGateway {
    event PaymentReleased(bytes32 indexed jobId, address indexed provider, uint256 amount);
    event RefundIssued(bytes32 indexed jobId, address indexed client, uint256 amount);

    function releasePayment(bytes32 _jobId, address _provider, uint256 _amount, uint256 _platformFee) external;
    function refundClient(bytes32 _jobId, address _client, uint256 _amount) external;
}

