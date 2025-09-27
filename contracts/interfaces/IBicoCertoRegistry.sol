// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IBicoCertoRegistry {
    function setJobManager(address _jobManager) external;
    function setPaymentGateway(address _paymentGateway) external;
    function setReputation(address _reputation) external;
    function setDisputeResolver(address _disputeResolver) external;
    function setUserRegistry(address _userRegistry) external;
    function setAdmin(address _admin) external;

    function getJobManager() external view returns (address);
    function getPaymentGateway() external view returns (address);
    function getReputation() external view returns (address);
    function getDisputeResolver() external view returns (address);
    function getUserRegistry() external view returns (address);
    function getAdmin() external view returns (address);
}

