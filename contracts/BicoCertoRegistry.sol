// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract BicoCertoRegistry {
    address public owner;

    address public jobManagerAddress;
    address public paymentGatewayAddress;
    address public reputationAddress;
    address public disputeResolverAddress;
    address public userRegistryAddress;
    address public adminAddress;

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function setJobManager(address _jobManager) external onlyOwner {
        jobManagerAddress = _jobManager;
    }

    function setPaymentGateway(address _paymentGateway) external onlyOwner {
        paymentGatewayAddress = _paymentGateway;
    }

    function setReputation(address _reputation) external onlyOwner {
        reputationAddress = _reputation;
    }

    function setDisputeResolver(address _disputeResolver) external onlyOwner {
        disputeResolverAddress = _disputeResolver;
    }

    function setAdmin(address _admin) external onlyOwner {
        adminAddress = _admin;
    }

    function getJobManager() external view returns (address) {
        return jobManagerAddress;
    }

    function getPaymentGateway() external view returns (address) {
        return paymentGatewayAddress;
    }

    function getReputation() external view returns (address) {
        return reputationAddress;
    }

    function getDisputeResolver() external view returns (address) {
        return disputeResolverAddress;
    }

    function getAdmin() external view returns (address) {
        return adminAddress;
    }
}


