// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IBicoCertoDisputeResolver {
    struct Dispute {
        bytes32 jobId;
        address initiator;
        string reason;
        uint256 createdAt;
        bool resolved;
        address resolver;
        string resolution;
    }

    event JobDisputed(bytes32 indexed jobId, address indexed initiator, string reason);
    event DisputeResolved(bytes32 indexed jobId, address indexed resolver, string resolution);

    function openDispute(bytes32 _jobId, string memory _reason) external;
    function resolveDispute(bytes32 _jobId, bool _favorClient, string memory _resolution) external;
    function addArbitrator(address _arbitrator) external;
    function removeArbitrator(address _arbitrator) external;
    function isArbitrator(address _addr) external view returns (bool);
    function getDispute(bytes32 _jobId) external view returns (Dispute memory);
}

