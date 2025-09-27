// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IBicoCertoJobManager {
    enum JobStatus {
        None,
        Created,
        Open,
        Accepted,
        InProgress,
        Completed,
        Approved,
        Disputed,
        Cancelled,
        Refunded
    }

    struct Job {
        bytes32 id;
        address client;
        address provider;
        uint256 amount;
        uint256 platformFee;
        uint256 createdAt;
        uint256 acceptedAt;
        uint256 completedAt;
        uint256 deadline;
        JobStatus status;
        string serviceType;
        string ipfsHash;
        uint8 clientRating;
        uint8 providerRating;
        bool openForProposals;
        uint256 proposalCount;
    }

        struct Proposal {
        bytes32 proposalId;
        bytes32 jobId;
        address provider;
        uint256 amount;
        uint256 estimatedTime;  // Em dias
        uint256 createdAt;
        ProposalStatus status;
        string ipfsHash;
    }

    enum ProposalStatus {
        None,
        Pending,
        Accepted,
        Rejected,
        Withdrawn
    }

     event JobOpenForProposals(
        bytes32 indexed jobId,
        address indexed client,
        uint256 maxBudget,
        uint256 deadline
    );

    event ProposalSubmitted(
        bytes32 indexed proposalId,
        bytes32 indexed jobId,
        address indexed provider,
        uint256 amount
    );

    event ProposalAccepted(
        bytes32 indexed proposalId,
        bytes32 indexed jobId,
        address indexed provider,
        uint256 finalAmount
    );

    event ProposalRejected(
        bytes32 indexed proposalId,
        bytes32 indexed jobId,
        address indexed provider
    );

    event ProposalWithdrawn(
        bytes32 indexed proposalId,
        bytes32 indexed jobId,
        address indexed provider
    );

    // ========== EVENTOS ==========
    event JobCreated(
        bytes32 indexed jobId,
        address indexed client,
        address indexed provider,
        uint256 amount,
        uint256 deadline
    );
    event JobAccepted(bytes32 indexed jobId, address indexed provider, uint256 timestamp);
    event JobCompleted(bytes32 indexed jobId, address indexed provider, uint256 timestamp);
    event JobApproved(bytes32 indexed jobId, address indexed client, uint256 amount, uint256 platformFee);
    event JobCancelled(bytes32 indexed jobId, address indexed client);
    event JobDisputed(bytes32 indexed jobId, address indexed disputer);
    event RatingGiven(bytes32 indexed jobId, address indexed rater, uint8 rating);

    // ========== FUNÇÕES DELEGADAS ==========
    function createJobFor(
        address _sender,
        address _provider,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable returns (bytes32);

    function createOpenJob(
        address _sender,
        uint256 _maxBudget,
        uint256 _deadline,
        string memory _serviceType,
        string memory _ipfsHash
    ) external payable returns (bytes32);

    function submitProposal(
        address _sender,
        bytes32 _jobId,
        uint256 _amount,
        uint256 _estimatedTime,
        string memory _ipfsHash
    ) external returns (bytes32);

    function acceptProposal(bytes32 _proposalId, address _sender) external payable;
    function rejectProposal(bytes32 _proposalId, address _sender) external;
    function withdrawProposal(bytes32 _proposalId, address _sender) external;

    function acceptJobFor(bytes32 _jobId, address _sender) external;
    function completeJobFor(bytes32 _jobId, address _sender) external;
    function approveJobFor(bytes32 _jobId, address _sender, uint8 _rating) external;
    function cancelJobFor(bytes32 _jobId, address _sender) external;

    // ========== FUNÇÕES DE ATUALIZAÇÃO (para contratos confiáveis) ==========
    function updateJobStatus(bytes32 _jobId, JobStatus _newStatus) external;
    function updateJobClientRating(bytes32 _jobId, uint8 _rating) external;
    function updateJobProviderRating(bytes32 _jobId, uint8 _rating) external;

    // ========== FUNÇÕES DE CONSULTA ==========
    function getJob(bytes32 _jobId) external view returns (Job memory);
    function getJobClient(bytes32 _jobId) external view returns (address);
    function getJobProvider(bytes32 _jobId) external view returns (address);
    function getJobAmount(bytes32 _jobId) external view returns (uint256);
    function getJobPlatformFee(bytes32 _jobId) external view returns (uint256);
    function getJobStatus(bytes32 _jobId) external view returns (JobStatus);
    function getJobCompletedAt(bytes32 _jobId) external view returns (uint256);
    function getUserJobs(address _user) external view returns (bytes32[] memory);

    function getProposal(bytes32 _proposalId) external view returns (Proposal memory);
    function getJobProposals(bytes32 _jobId) external view returns (bytes32[] memory);
    function getProviderProposals(address _provider) external view returns (bytes32[] memory);
    function getOpenJobs() external view returns (bytes32[] memory);
    function getActiveProposalsForJob(bytes32 _jobId) external view returns (Proposal[] memory);

}