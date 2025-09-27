// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "contracts/interfaces/IBicoCertoDisputeResolver.sol";
import "contracts/interfaces/IBicoCertoJobManager.sol";
import "contracts/interfaces/IBicoCertoPaymentGateway.sol";
import "contracts/interfaces/IBicoCertoReputation.sol";
import "contracts/interfaces/IBicoCertoRegistry.sol";
import "contracts/interfaces/IBicoCertoAdmin.sol";

contract BicoCertoDisputeResolver is IBicoCertoDisputeResolver {
    IBicoCertoRegistry public registry;

    mapping(bytes32 => Dispute) public disputes;
    mapping(address => bool) public arbitrators;
    uint256 public totalDisputes;

    constructor(address _registryAddress) {
        registry = IBicoCertoRegistry(_registryAddress);
    }

    modifier notPaused() {
        require(!IBicoCertoAdmin(registry.getAdmin()).isPaused(), "Contrato pausado");
        _;
    }

    modifier jobExists(bytes32 _jobId) {
        require(IBicoCertoJobManager(registry.getJobManager()).getJobStatus(_jobId) != IBicoCertoJobManager.JobStatus.None, "Trabalho nao existe");
        _;
    }

    modifier onlyParties(bytes32 _jobId) {
        address client = IBicoCertoJobManager(registry.getJobManager()).getJobClient(_jobId);
        address provider = IBicoCertoJobManager(registry.getJobManager()).getJobProvider(_jobId);
        require(
            client == msg.sender || 
            provider == msg.sender,
            "Apenas partes envolvidas"
        );
        _;
    }

    function openDispute(bytes32 _jobId, string memory _reason)
        external
        notPaused
        jobExists(_jobId)
        onlyParties(_jobId)
    {
        IBicoCertoJobManager jobManager = IBicoCertoJobManager(registry.getJobManager());
        IBicoCertoJobManager.JobStatus currentStatus = jobManager.getJobStatus(_jobId);

        require(
            currentStatus == IBicoCertoJobManager.JobStatus.Completed || 
            currentStatus == IBicoCertoJobManager.JobStatus.InProgress,
            "Status invalido para disputa"
        );
        require(bytes(_reason).length > 0, "Motivo necessario");

        jobManager.updateJobStatus(_jobId, IBicoCertoJobManager.JobStatus.Disputed);
        
        disputes[_jobId] = Dispute({
            jobId: _jobId,
            initiator: msg.sender,
            reason: _reason,
            createdAt: block.timestamp,
            resolved: false,
            resolver: address(0),
            resolution: ""
        });
        
        totalDisputes++;
        
        emit JobDisputed(_jobId, msg.sender, _reason);
    }

    function resolveDispute(
        bytes32 _jobId, 
        bool _favorClient, 
        string memory _resolution
    ) 
        external 
        notPaused 
        jobExists(_jobId) 
    {
        require(arbitrators[msg.sender], "Nao e arbitrador");
        
        IBicoCertoJobManager jobManager = IBicoCertoJobManager(registry.getJobManager());
        IBicoCertoJobManager.JobStatus currentStatus = jobManager.getJobStatus(_jobId);

        require(currentStatus == IBicoCertoJobManager.JobStatus.Disputed, "Nao esta em disputa");
        
        Dispute storage dispute = disputes[_jobId];
        require(!dispute.resolved, "Disputa ja resolvida");
        
        dispute.resolved = true;
        dispute.resolver = msg.sender;
        dispute.resolution = _resolution;
        
        address client = jobManager.getJobClient(_jobId);
        address provider = jobManager.getJobProvider(_jobId);
        uint256 amount = jobManager.getJobAmount(_jobId);
        uint256 platformFee = jobManager.getJobPlatformFee(_jobId);

        if (_favorClient) {
            jobManager.updateJobStatus(_jobId, IBicoCertoJobManager.JobStatus.Refunded);
            IBicoCertoPaymentGateway(registry.getPaymentGateway()).refundClient(
                _jobId,
                client,
                amount + platformFee
            );
        } else {
            jobManager.updateJobStatus(_jobId, IBicoCertoJobManager.JobStatus.Approved);
            IBicoCertoPaymentGateway(registry.getPaymentGateway()).releasePayment(
                _jobId,
                provider,
                amount,
                platformFee
            );
        }
        
        emit DisputeResolved(_jobId, msg.sender, _resolution);
    }

    function addArbitrator(address _arbitrator) external {
        // Only callable by Admin contract
        require(msg.sender == registry.getAdmin(), "Only Admin can add arbitrators");
        arbitrators[_arbitrator] = true;
    }
    
    function removeArbitrator(address _arbitrator) external {
        // Only callable by Admin contract
        require(msg.sender == registry.getAdmin(), "Only Admin can remove arbitrators");
        arbitrators[_arbitrator] = false;
    }

    function isArbitrator(address _addr) external view returns (bool) {
        return arbitrators[_addr];
    }

    function getDispute(bytes32 _jobId) external view returns (Dispute memory) {
        return disputes[_jobId];
    }
}


